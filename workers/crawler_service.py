#!/usr/bin/env python3
"""
Web Crawler Service

An async worker that processes web_crawl tasks from the task queue.
Connects to Chrome (with Comet extension) via CDP and uses AI (Claude/Ollama)
to interpret prompts and execute browser actions.

Usage:
    python3 crawler_service.py                # Run in foreground
    python3 crawler_service.py --daemon       # Run as daemon
    python3 crawler_service.py --stop         # Stop daemon
    python3 crawler_service.py --status       # Check status
"""

import asyncio
import json
import logging
import os
import re
import signal
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from session_state_manager import SessionStateManager

# Setup paths
WORKER_DIR = Path(__file__).parent
BASE_DIR = WORKER_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from db import get_connection
from workers.crawler_config import SYSTEM_PROMPTS, CrawlerConfig

# Worker files
PID_FILE = Path("/tmp/architect_crawler.pid")
STATE_FILE = Path("/tmp/architect_crawler_state.json")
LOG_FILE = Path("/tmp/architect_crawler.log")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger("CrawlerService")


@dataclass
class PageState:
    """Current state of the browser page."""

    url: str
    title: str
    html: str = ""
    text: str = ""
    elements: List[Dict] = None

    def __post_init__(self):
        if self.elements is None:
            self.elements = []


@dataclass
class BrowserAction:
    """A browser action to execute."""

    action: str
    params: Dict[str, Any]
    reasoning: str = ""

    @classmethod
    def from_dict(cls, data: Dict) -> "BrowserAction":
        return cls(
            action=data.get("action", "wait"),
            params=data.get("params", {}),
            reasoning=data.get("reasoning", ""),
        )


@dataclass
class CrawlResult:
    """Result of a crawl task."""

    task_id: int
    prompt: str
    start_url: str = ""
    final_url: str = ""
    success: bool = False
    extracted_data: Dict = None
    action_history: List[Dict] = None
    screenshots: List[str] = None
    error_message: str = ""
    duration_seconds: float = 0
    llm_provider: str = ""

    def __post_init__(self):
        if self.extracted_data is None:
            self.extracted_data = {}
        if self.action_history is None:
            self.action_history = []
        if self.screenshots is None:
            self.screenshots = []

    def to_dict(self) -> Dict:
        return asdict(self)


class LLMClient:
    """Client for LLM providers with automatic failover, delegation, and throttling support."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.provider = config.llm.get_provider()

        # Session ID for throttling
        self.session_id = os.environ.get("SESSION_ID", "crawler_service")

        # Check if failover is enabled
        self.failover_enabled = os.environ.get("LLM_FAILOVER_ENABLED", "true").lower() == "true"

        # Check if delegation is enabled
        self.delegation_enabled = os.environ.get("LLM_DELEGATION_ENABLED", "true").lower() == "true"

        if self.failover_enabled:
            # Use unified client with failover
            try:
                from services.llm_provider import UnifiedLLMClient

                self.unified_client = UnifiedLLMClient()
                logger.info("LLM failover enabled: using UnifiedLLMClient")
            except Exception as e:
                logger.warning(
                    f"Failed to initialize UnifiedLLMClient, falling back to direct provider: {e}"
                )
                self.unified_client = None
                self.failover_enabled = False
        else:
            self.unified_client = None
            logger.info("LLM failover disabled: using direct provider")

        # Initialize delegator if enabled
        if self.delegation_enabled:
            try:
                from services.task_delegator import get_delegator

                self.delegator = get_delegator()
                logger.info("Task delegation enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize delegator: {e}")
                self.delegator = None
                self.delegation_enabled = False
        else:
            self.delegator = None

    async def generate(self, prompt: str, system: str = None, priority: str = "normal") -> str:
        """
        Generate a response from the LLM with automatic failover, delegation, and throttling.

        Args:
            prompt: The prompt to send to the LLM
            system: Optional system prompt
            priority: Request priority (low, normal, high, critical) for throttling

        Returns:
            Generated text response
        """
        if self.failover_enabled and self.unified_client:
            return await self._generate_with_failover(prompt, system, priority)
        elif self.provider == "claude":
            return await self._generate_claude(prompt, system)
        elif self.provider == "ollama":
            return await self._generate_ollama(prompt, system)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

    async def _generate_with_failover(
        self, prompt: str, system: str = None, priority: str = "normal"
    ) -> str:
        """Generate using UnifiedLLMClient with automatic failover, delegation, and throttling."""
        try:
            messages = [{"role": "user", "content": prompt}]

            # Use delegation to determine optimal model if enabled
            model = self.config.llm.claude_model
            if self.delegation_enabled and self.delegator:
                # Crawler tasks are typically UI-related (browser automation)
                # So we delegate as UI tasks by default, but can be overridden
                from services.task_delegator import TaskType

                delegation_result = self.delegator.delegate_task(
                    task=prompt[:200],  # Use first 200 chars for classification
                    task_type=TaskType.UI,  # Crawler is primarily UI automation
                    priority=priority,
                )
                model = delegation_result.model
                logger.info(
                    f"Delegated task: {delegation_result.task_type.value} → "
                    f"{delegation_result.agent.value} ({delegation_result.model})"
                )

            # Call unified client (synchronous, but wrapped in async)
            # Includes automatic throttling
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.unified_client.messages.create(
                    model=model,
                    max_tokens=self.config.llm.claude_max_tokens,
                    messages=messages,
                    temperature=self.config.llm.temperature,
                    session_id=self.session_id,
                    priority=priority,
                ),
            )

            # Extract text from response
            if response.content and len(response.content) > 0:
                text = response.content[0].get("text", "")
                logger.info(
                    f"LLM response from {response.provider}: "
                    f"{len(text)} chars, ${response.cost:.4f}, "
                    f"{response.usage.total_tokens} tokens"
                )
                return text
            else:
                raise RuntimeError("Empty response from LLM")

        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            raise

    async def _generate_claude(self, prompt: str, system: str = None) -> str:
        """Generate using Claude API directly (legacy fallback)."""
        try:
            import anthropic

            client = anthropic.Anthropic()
            messages = [{"role": "user", "content": prompt}]

            response = client.messages.create(
                model=self.config.llm.claude_model,
                max_tokens=self.config.llm.claude_max_tokens,
                system=system or "",
                messages=messages,
            )

            return response.content[0].text

        except ImportError:
            raise RuntimeError("anthropic package not installed. Run: pip install anthropic")
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    async def _generate_ollama(self, prompt: str, system: str = None) -> str:
        """Generate using Ollama directly (legacy fallback)."""
        try:
            import aiohttp

            url = f"{self.config.llm.ollama_host}/api/generate"
            payload = {
                "model": self.config.llm.ollama_model,
                "prompt": prompt,
                "system": system or "",
                "stream": False,
                "options": {"temperature": self.config.llm.temperature},
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=60) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", "")
                    else:
                        raise RuntimeError(f"Ollama error: {response.status}")

        except ImportError:
            raise RuntimeError("aiohttp package not installed. Run: pip install aiohttp")


class BrowserAgent:
    """Browser automation agent using Playwright and LLM."""

    def __init__(self, config: CrawlerConfig, llm: LLMClient):
        self.config = config
        self.llm = llm
        self.browser = None
        self.context = None
        self.page = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to Chrome via CDP or launch new browser."""
        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()

            if self.config.connection_mode == "cdp":
                # Connect to existing Chrome with debug port
                cdp_url = f"http://localhost:{self.config.chrome.debug_port}"
                logger.info(f"Connecting to Chrome at {cdp_url}")

                self.browser = await self._playwright.chromium.connect_over_cdp(cdp_url)

                # Get existing context and page
                contexts = self.browser.contexts
                if contexts:
                    self.context = contexts[0]
                    pages = self.context.pages
                    if pages:
                        self.page = pages[0]
                    else:
                        self.page = await self.context.new_page()
                else:
                    self.context = await self.browser.new_context()
                    self.page = await self.context.new_page()

            elif self.config.connection_mode == "persistent":
                # Launch with user profile
                self.context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=self.config.chrome.get_profile_path(),
                    headless=self.config.chrome.headless,
                    args=[f"--remote-debugging-port={self.config.chrome.debug_port}"],
                )
                self.page = (
                    self.context.pages[0] if self.context.pages else await self.context.new_page()
                )
                self.browser = self.context.browser

            else:  # fresh
                # Launch fresh browser
                self.browser = await self._playwright.chromium.launch(
                    headless=self.config.chrome.headless
                )
                self.context = await self.browser.new_context()
                self.page = await self.context.new_page()

            self._connected = True
            logger.info("Browser connected successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to browser: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from browser."""
        try:
            if self.config.connection_mode == "cdp":
                # Don't close browser when using CDP, just disconnect
                if self._playwright:
                    await self._playwright.stop()
            else:
                if self.context:
                    await self.context.close()
                if self.browser:
                    await self.browser.close()
                if self._playwright:
                    await self._playwright.stop()

            self._connected = False
            logger.info("Browser disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")

    async def get_page_state(self) -> PageState:
        """Get current page state."""
        if not self.page:
            return PageState(url="", title="")

        url = self.page.url
        title = await self.page.title()

        # Get simplified page content
        try:
            text = await self.page.evaluate(
                """() => {
                return document.body.innerText.substring(0, 5000);
            }"""
            )
        except Exception:
            text = ""

        # Get interactive elements
        elements = []
        try:
            elements = await self.page.evaluate(
                """() => {
                const results = [];
                const selectors = ['a', 'button', 'input', 'select', 'textarea', '[onclick]', '[role="button"]'];
                selectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach((el, i) => {
                        if (i < 20) {  // Limit per selector
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                results.push({
                                    tag: el.tagName.toLowerCase(),
                                    id: el.id || null,
                                    class: el.className || null,
                                    text: (el.innerText || el.value || '').substring(0, 100),
                                    type: el.type || null,
                                    href: el.href || null,
                                    placeholder: el.placeholder || null,
                                });
                            }
                        }
                    });
                });
                return results.slice(0, 50);  // Total limit
            }"""
            )
        except Exception:
            pass

        return PageState(url=url, title=title, text=text, elements=elements)

    async def execute_action(self, action: BrowserAction) -> Dict[str, Any]:
        """Execute a browser action."""
        action_name = action.action
        params = action.params
        result = {"success": False, "action": action_name}

        try:
            if action_name == "navigate":
                url = params.get("url", "")
                await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                result["success"] = True
                result["url"] = url

            elif action_name == "click":
                selector = params.get("selector", "")
                text = params.get("text", "")

                if text:
                    # Click by text content
                    await self.page.click(f"text={text}", timeout=10000)
                elif selector:
                    await self.page.click(selector, timeout=10000)

                result["success"] = True
                # Wait for navigation or content change
                await asyncio.sleep(1)

            elif action_name == "type":
                selector = params.get("selector", "")
                text = params.get("text", "")

                if selector:
                    await self.page.fill(selector, text, timeout=10000)
                else:
                    await self.page.keyboard.type(text)

                result["success"] = True

            elif action_name == "press":
                key = params.get("key", "Enter")
                await self.page.keyboard.press(key)
                result["success"] = True

            elif action_name == "scroll":
                direction = params.get("direction", "down")
                amount = params.get("amount", 500)

                if direction == "down":
                    await self.page.evaluate(f"window.scrollBy(0, {amount})")
                else:
                    await self.page.evaluate(f"window.scrollBy(0, -{amount})")

                result["success"] = True

            elif action_name == "wait":
                selector = params.get("selector")
                seconds = params.get("seconds", 2)

                if selector:
                    await self.page.wait_for_selector(selector, timeout=seconds * 1000)
                else:
                    await asyncio.sleep(seconds)

                result["success"] = True

            elif action_name == "screenshot":
                path = params.get("path", "")
                if not path:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    path = str(Path(self.config.screenshot_dir) / f"screenshot_{timestamp}.png")

                Path(path).parent.mkdir(parents=True, exist_ok=True)
                await self.page.screenshot(path=path, full_page=False)
                result["success"] = True
                result["path"] = path

            elif action_name == "extract":
                selector = params.get("selector", "body")
                attribute = params.get("attribute", "text")

                elements = await self.page.query_selector_all(selector)
                data = []
                for el in elements[:20]:  # Limit extraction
                    if attribute == "text":
                        data.append(await el.inner_text())
                    elif attribute == "html":
                        data.append(await el.inner_html())
                    else:
                        data.append(await el.get_attribute(attribute))

                result["success"] = True
                result["data"] = data

            elif action_name == "evaluate":
                script = params.get("script", "")
                eval_result = await self.page.evaluate(script)
                result["success"] = True
                result["data"] = eval_result

            elif action_name == "done":
                result["success"] = True
                result["data"] = params.get("result", {})
                result["done"] = True

            else:
                result["error"] = f"Unknown action: {action_name}"

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Action {action_name} failed: {e}")

        return result

    async def determine_next_action(
        self, objective: str, page_state: PageState, history: List[Dict]
    ) -> BrowserAction:
        """Use LLM to determine the next action."""
        # Build context for LLM
        context = f"""Current page:
URL: {page_state.url}
Title: {page_state.title}

Page content (excerpt):
{page_state.text[:2000]}

Interactive elements:
{json.dumps(page_state.elements[:30], indent=2)}

Action history:
{json.dumps(history[-5:], indent=2) if history else "None yet"}

User objective: {objective}

What is the next action to accomplish this objective?
Respond with a JSON object containing: action, params, reasoning
"""

        response = await self.llm.generate(context, system=SYSTEM_PROMPTS["browser_agent"])

        # Parse JSON from response
        try:
            # Try to extract JSON from response (handle markdown code blocks and nested objects)
            # First try to find JSON in code blocks
            code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
            if code_block_match:
                action_data = json.loads(code_block_match.group(1))
                return BrowserAction.from_dict(action_data)

            # Try to find a complete JSON object by matching braces
            # Find the first { and then find its matching }
            start = response.find("{")
            if start != -1:
                depth = 0
                for i, char in enumerate(response[start:], start):
                    if char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            json_str = response[start : i + 1]
                            action_data = json.loads(json_str)
                            return BrowserAction.from_dict(action_data)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response: {response[:200]}... Error: {e}")

        # Default to wait if parsing fails
        return BrowserAction(
            action="wait", params={"seconds": 2}, reasoning="Failed to parse LLM response"
        )

    async def run_task(self, task_data: Dict) -> CrawlResult:
        """Run a web crawl task."""
        prompt = task_data.get("prompt", "")
        start_url = task_data.get("url", "")
        extract_fields = task_data.get("extract_fields", [])
        take_screenshots = task_data.get("screenshot", True)
        timeout = task_data.get("timeout", 60)
        task_id = task_data.get("task_id", 0)

        result = CrawlResult(
            task_id=task_id, prompt=prompt, start_url=start_url, llm_provider=self.llm.provider
        )

        start_time = time.time()

        try:
            # Navigate to start URL if provided
            if start_url:
                await self.page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
                result.action_history.append(
                    {
                        "action": "navigate",
                        "params": {"url": start_url},
                        "success": True,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # Main automation loop
            max_actions = 20
            action_count = 0

            while action_count < max_actions:
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    result.error_message = f"Task timeout after {timeout} seconds"
                    break

                # Get current page state
                page_state = await self.get_page_state()

                # Determine next action
                action = await self.determine_next_action(prompt, page_state, result.action_history)

                logger.info(f"Action {action_count + 1}: {action.action} - {action.reasoning}")

                # Execute action
                action_result = await self.execute_action(action)

                # Record action
                result.action_history.append(
                    {
                        "action": action.action,
                        "params": action.params,
                        "reasoning": action.reasoning,
                        **action_result,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                # Check if done
                if action_result.get("done"):
                    result.success = True
                    result.extracted_data = action_result.get("data", {})
                    break

                # Take screenshot if enabled
                if take_screenshots and action.action in ["navigate", "click", "type"]:
                    try:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        screenshot_path = str(
                            Path(self.config.screenshot_dir)
                            / f"task_{task_id}_{action_count}_{timestamp}.png"
                        )
                        Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
                        await self.page.screenshot(path=screenshot_path)
                        result.screenshots.append(screenshot_path)
                    except Exception as e:
                        logger.warning(f"Screenshot failed: {e}")

                action_count += 1

            # Get final URL
            result.final_url = self.page.url

            # If we hit max actions without completing
            if action_count >= max_actions and not result.success:
                result.error_message = "Reached maximum action limit without completing"

        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Task failed: {e}")

        result.duration_seconds = time.time() - start_time
        return result


class CrawlerService:
    """Main crawler service that processes tasks from the queue."""

    def __init__(self, config: CrawlerConfig = None):
        self.config = config or CrawlerConfig.from_env()
        self.worker_id = self.config.worker_id or str(uuid.uuid4())
        self._running = False
        self._current_task = None
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._start_time = None

        # Initialize SessionStateManager with unique worker_id
        self.state_manager = SessionStateManager(f"crawler-{self.worker_id}")
        self.state_manager.set_tool_info("crawler_service", "browser+llm")
        self.state_manager.set_status("idle")

        # Track operation counters
        self.operation_counts = {
            "tasks_claimed": 0,
            "tasks_completed": 0,
            "actions_executed": 0,
            "llm_calls": 0,
        }

        self.llm = LLMClient(self.config)
        self.agent = BrowserAgent(self.config, self.llm)

    def _update_operation_counts(self) -> None:
        """Sync operation counters to state manager."""
        for key, value in self.operation_counts.items():
            self.state_manager.set_metadata(key, value)

    async def _async_heartbeat(self) -> None:
        """Async-safe heartbeat that updates state manager."""
        self.state_manager.heartbeat()
        self._update_operation_counts()

    def _register_with_server(self):
        """Register this worker with the dashboard server."""
        try:
            import requests

            response = requests.post(
                f"{self.config.dashboard_url}/api/workers/register",
                json={
                    "id": self.worker_id,
                    "node_id": self.config.node_id,
                    "worker_type": self.config.worker_type,
                },
                timeout=5,
            )

            if response.status_code == 200:
                logger.info(f"Registered with server as {self.worker_id}")
                return True
            else:
                logger.warning(f"Failed to register: {response.status_code}")
                return False

        except Exception as e:
            logger.warning(f"Could not register with server: {e}")
            return False

    def _send_heartbeat(self):
        """Send heartbeat to the dashboard server."""
        try:
            import requests

            requests.post(
                f"{self.config.dashboard_url}/api/workers/{self.worker_id}/heartbeat",
                json={
                    "status": "busy" if self._current_task else "idle",
                    "current_task_id": self._current_task.get("id") if self._current_task else None,
                    "tasks_completed": self._tasks_completed,
                    "tasks_failed": self._tasks_failed,
                },
                timeout=5,
            )
        except Exception as e:
            logger.debug(f"Heartbeat failed: {e}")

    def _claim_task(self) -> Optional[Dict]:
        """Claim a pending web_crawl task from the queue."""
        try:
            import requests

            response = requests.post(
                f"{self.config.dashboard_url}/api/tasks/claim",
                json={"worker_id": self.worker_id, "task_types": ["web_crawl"]},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                task = data.get("task")
                if task:
                    self.operation_counts["tasks_claimed"] += 1
                    self.state_manager.set_task(f"Crawling task #{task.get('id')}")
                    self.state_manager.set_status("working")
                    self.state_manager.set_metadata("current_task_id", task.get("id"))
                return task

        except Exception as e:
            logger.debug(f"Could not claim task from server: {e}")

        # Fallback to direct database access
        task = self._claim_task_from_db()
        if task:
            self.operation_counts["tasks_claimed"] += 1
            self.state_manager.set_task(f"Crawling task #{task.get('id')}")
            self.state_manager.set_status("working")
            self.state_manager.set_metadata("current_task_id", task.get("id"))
        return task

    def _claim_task_from_db(self) -> Optional[Dict]:
        """Claim a task directly from the database."""
        try:
            with get_connection() as conn:
                # Find pending web_crawl task
                task = conn.execute(
                    """
                    SELECT * FROM task_queue
                    WHERE status = 'pending'
                      AND retries < max_retries
                      AND task_type = 'web_crawl'
                    ORDER BY priority DESC, created_at
                    LIMIT 1
                """
                ).fetchone()

                if task:
                    # Claim it
                    conn.execute(
                        """
                        UPDATE task_queue SET
                            status = 'running',
                            assigned_worker = ?,
                            started_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND status = 'pending'
                    """,
                        (self.worker_id, task["id"]),
                    )

                    return dict(task)

        except Exception as e:
            logger.error(f"Database error: {e}")

        return None

    def _complete_task(self, task_id: int, result: CrawlResult):
        """Mark a task as completed and store result."""
        try:
            import requests

            requests.post(
                f"{self.config.dashboard_url}/api/tasks/{task_id}/complete",
                json={"worker_id": self.worker_id, "result": result.to_dict()},
                timeout=5,
            )
        except Exception:
            pass

        # Store result in database
        try:
            with get_connection() as conn:
                # Update task status
                conn.execute(
                    """
                    UPDATE task_queue SET
                        status = 'completed',
                        completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (task_id,),
                )

                # Store crawl result
                conn.execute(
                    """
                    INSERT INTO crawl_results
                    (task_id, prompt, start_url, final_url, success, extracted_data,
                     action_history, screenshots, error_message, duration_seconds, llm_provider)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        task_id,
                        result.prompt,
                        result.start_url,
                        result.final_url,
                        result.success,
                        json.dumps(result.extracted_data),
                        json.dumps(result.action_history),
                        json.dumps(result.screenshots),
                        result.error_message,
                        result.duration_seconds,
                        result.llm_provider,
                    ),
                )

        except Exception as e:
            logger.error(f"Failed to store result: {e}")

    def _fail_task(self, task_id: int, error: str):
        """Mark a task as failed."""
        try:
            import requests

            requests.post(
                f"{self.config.dashboard_url}/api/tasks/{task_id}/fail",
                json={"worker_id": self.worker_id, "error": error},
                timeout=5,
            )
        except Exception:
            pass

        # Fallback to direct DB
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE task_queue SET
                        status = CASE WHEN retries + 1 >= max_retries THEN 'failed' ELSE 'pending' END,
                        retries = retries + 1,
                        error_message = ?,
                        assigned_worker = NULL,
                        started_at = NULL
                    WHERE id = ?
                """,
                    (error, task_id),
                )
        except Exception as e:
            logger.error(f"Failed to update task: {e}")

    async def _process_task(self, task: Dict) -> bool:
        """Process a single crawl task."""
        task_id = task["id"]
        task_data = json.loads(task.get("task_data", "{}"))
        task_data["task_id"] = task_id

        logger.info(f"Processing web_crawl task {task_id}")
        self._current_task = task
        start_time = time.time()

        try:
            # Connect to browser if not connected
            if not self.agent._connected:
                if not await self.agent.connect():
                    raise RuntimeError("Failed to connect to browser")

            # Run the task
            result = await self.agent.run_task(task_data)

            # Track result metrics
            duration_seconds = time.time() - start_time
            self.state_manager.set_metadata("last_task_duration", duration_seconds)
            self.state_manager.set_metadata("last_task_success", result.success)
            self.state_manager.set_metadata("llm_provider_used", result.llm_provider)
            self.operation_counts["tasks_completed"] += 1

            # Store result
            self._complete_task(task_id, result)
            self._tasks_completed += 1

            if result.success:
                logger.info(f"Task {task_id} completed successfully")
            else:
                logger.warning(f"Task {task_id} completed with errors: {result.error_message}")

            return result.success

        except Exception as e:
            error_msg = str(e)
            duration_seconds = time.time() - start_time
            self.state_manager.increment_errors()
            self.state_manager.set_metadata("last_error", error_msg)
            self.state_manager.set_metadata("last_task_duration", duration_seconds)

            self._fail_task(task_id, error_msg)
            self._tasks_failed += 1
            logger.error(f"Task {task_id} failed: {error_msg}")
            return False

        finally:
            self._current_task = None
            self.state_manager.clear_task()
            self._update_operation_counts()

    def _save_state(self):
        """Save worker state to file."""
        state = {
            "worker_id": self.worker_id,
            "node_id": self.config.node_id,
            "worker_type": self.config.worker_type,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "tasks_completed": self._tasks_completed,
            "tasks_failed": self._tasks_failed,
            "current_task": self._current_task,
            "running": self._running,
            "llm_provider": self.llm.provider,
            "timestamp": datetime.now().isoformat(),
        }

        STATE_FILE.write_text(json.dumps(state, indent=2))

    async def start_async(self):
        """Start the crawler service (async version)."""
        self._running = True
        self._start_time = datetime.now()
        self.state_manager.set_status("initializing")

        logger.info(f"Starting crawler service {self.worker_id}")
        logger.info(f"LLM Provider: {self.llm.provider}")
        logger.info(f"Connection mode: {self.config.connection_mode}")

        # Register with server
        self._register_with_server()

        # Connect to browser
        if not await self.agent.connect():
            logger.error(
                "Could not connect to browser. Make sure Chrome is running with --remote-debugging-port"
            )
            logger.error("Run: scripts/start_chrome_debug.sh")
            self._running = False
            self.state_manager.set_status("idle")
            return

        # Main loop
        heartbeat_counter = 0
        self.state_manager.set_status("idle")

        try:
            while self._running:
                task = self._claim_task()

                if task:
                    # Status already set to "working" in _claim_task
                    await self._process_task(task)
                    self.state_manager.set_status("idle")
                else:
                    self.state_manager.set_status("idle")
                    await asyncio.sleep(self.config.poll_interval)

                # Send heartbeat periodically using executor for non-blocking updates
                heartbeat_counter += self.config.poll_interval
                if heartbeat_counter >= self.config.heartbeat_interval:
                    self._send_heartbeat()
                    # Use executor to avoid blocking event loop
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self._async_heartbeat)
                    heartbeat_counter = 0

                self._save_state()

        except KeyboardInterrupt:
            logger.info("Crawler interrupted")
            self.state_manager.set_status("stopped")
        finally:
            self._running = False
            await self.agent.disconnect()
            self._save_state()
            self.state_manager.cleanup()
            logger.info("Crawler stopped")

    def start(self):
        """Start the crawler service."""
        asyncio.run(self.start_async())

    def stop(self):
        """Stop the crawler service."""
        self._running = False


def run_daemon():
    """Run crawler as a daemon."""
    # Check if already running
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"Crawler already running (PID {pid})")
            return
        except ProcessLookupError:
            PID_FILE.unlink()

    # Fork
    pid = os.fork()
    if pid > 0:
        print(f"Crawler started (PID {pid})")
        return

    # Daemon setup
    os.setsid()
    os.chdir("/")

    # Write PID file
    PID_FILE.write_text(str(os.getpid()))

    # Start service
    service = CrawlerService()

    def signal_handler(sig, frame):
        service.stop()
        PID_FILE.unlink()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    service.start()


def stop_daemon():
    """Stop the daemon."""
    if not PID_FILE.exists():
        print("Crawler not running")
        return

    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Sent stop signal to crawler (PID {pid})")

        # Wait for process to stop
        for _ in range(10):
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                print("Crawler stopped")
                PID_FILE.unlink()
                return

        print("Crawler did not stop, sending SIGKILL")
        os.kill(pid, signal.SIGKILL)
        PID_FILE.unlink()

    except ProcessLookupError:
        print("Crawler not running")
        PID_FILE.unlink()


def show_status():
    """Show crawler status."""
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())

        print(
            f"""
Crawler Status
==============
ID:              {state.get('worker_id', 'N/A')}
Node:            {state.get('node_id', 'N/A')}
Type:            {state.get('worker_type', 'N/A')}
Running:         {state.get('running', False)}
LLM Provider:    {state.get('llm_provider', 'N/A')}
Started:         {state.get('start_time', 'N/A')}
Tasks Completed: {state.get('tasks_completed', 0)}
Tasks Failed:    {state.get('tasks_failed', 0)}
Current Task:    {state.get('current_task', {}).get('id', 'None') if state.get('current_task') else 'None'}
Last Update:     {state.get('timestamp', 'N/A')}
"""
        )
    else:
        print("No crawler state found")

    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"Process: Running (PID {pid})")
        except ProcessLookupError:
            print("Process: Not running (stale PID file)")
    else:
        print("Process: Not running")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Web Crawler Service")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--worker-id", help="Worker ID")
    parser.add_argument("--node-id", default="local", help="Node ID")
    parser.add_argument(
        "--dashboard",
        "--dashboard-url",
        dest="dashboard_url",
        default="http://100.112.58.92:8080",
        help="Dashboard URL",
    )
    parser.add_argument("--chrome-port", type=int, default=9222, help="Chrome debug port")
    parser.add_argument(
        "--llm", choices=["claude", "ollama", "auto"], default="auto", help="LLM provider to use"
    )
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument(
        "--connection-mode",
        choices=["cdp", "persistent", "fresh"],
        default="cdp",
        help="Browser connection mode",
    )

    args = parser.parse_args()

    if args.stop:
        stop_daemon()
    elif args.status:
        show_status()
    elif args.daemon:
        run_daemon()
    else:
        # Run in foreground
        config = CrawlerConfig.from_env()
        config.worker_id = args.worker_id
        config.node_id = args.node_id
        config.dashboard_url = args.dashboard_url
        config.chrome.debug_port = args.chrome_port
        config.chrome.headless = args.headless
        config.llm.provider = args.llm
        config.connection_mode = args.connection_mode

        service = CrawlerService(config)
        service.start()


if __name__ == "__main__":
    main()
