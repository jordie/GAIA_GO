#!/usr/bin/env python3
"""
Web Crawler Configuration

Configuration settings for the web crawler service including:
- Chrome profile paths by platform
- Default settings (timeout, headless, LLM provider)
- Connection modes (CDP, persistent, fresh)
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

# Platform detection
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
IS_WINDOWS = sys.platform == "win32"


@dataclass
class ChromeConfig:
    """Chrome browser configuration."""

    # Default Chrome paths by platform
    CHROME_PATHS: Dict[str, str] = field(
        default_factory=lambda: {
            "darwin": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "linux": "/usr/bin/google-chrome",
            "win32": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        }
    )

    # User data directories by platform
    USER_DATA_DIRS: Dict[str, str] = field(
        default_factory=lambda: {
            "darwin": str(Path.home() / "Library/Application Support/Google/Chrome"),
            "linux": str(Path.home() / ".config/google-chrome"),
            "win32": str(Path.home() / "AppData/Local/Google/Chrome/User Data"),
        }
    )

    # Default profile name
    profile: str = "Default"

    # Remote debugging port
    debug_port: int = 9222

    # Headless mode
    headless: bool = False

    # Connection timeout in seconds
    timeout: int = 30

    def get_chrome_path(self) -> str:
        """Get Chrome executable path for current platform."""
        return self.CHROME_PATHS.get(sys.platform, self.CHROME_PATHS["linux"])

    def get_user_data_dir(self) -> str:
        """Get Chrome user data directory for current platform."""
        return self.USER_DATA_DIRS.get(sys.platform, self.USER_DATA_DIRS["linux"])

    def get_profile_path(self) -> str:
        """Get full path to Chrome profile."""
        return str(Path(self.get_user_data_dir()) / self.profile)


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    # Provider: 'claude', 'ollama', 'auto'
    provider: str = "auto"

    # Claude settings
    claude_model: str = "claude-sonnet-4-20250514"
    claude_max_tokens: int = 4096

    # Ollama settings
    ollama_model: str = "llama3.2"
    ollama_host: str = "http://100.112.58.92:11434"

    # Temperature for generation
    temperature: float = 0.7

    def get_provider(self) -> str:
        """Get the actual provider to use (resolve 'auto')."""
        if self.provider != "auto":
            return self.provider

        # Check for Anthropic API key
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "claude"

        # Check if Ollama is available
        try:
            import requests

            response = requests.get(f"{self.ollama_host}/api/tags", timeout=2)
            if response.status_code == 200:
                return "ollama"
        except:
            pass

        # Default to Claude (will fail if no API key)
        return "claude"


@dataclass
class CrawlerConfig:
    """Main crawler configuration."""

    # Chrome configuration
    chrome: ChromeConfig = field(default_factory=ChromeConfig)

    # LLM configuration
    llm: LLMConfig = field(default_factory=LLMConfig)

    # Worker settings
    worker_id: Optional[str] = None
    node_id: str = "local"
    worker_type: str = "crawler"

    # Dashboard connection
    dashboard_url: str = os.environ.get("DASHBOARD_URL", "http://100.112.58.92:8080")

    # Task processing
    poll_interval: int = 5
    heartbeat_interval: int = 30
    max_task_timeout: int = 300  # 5 minutes max per task

    # Screenshot settings
    screenshot_dir: str = field(
        default_factory=lambda: str(Path(__file__).parent.parent / "data" / "screenshots")
    )
    save_screenshots: bool = True

    # Connection mode: 'cdp' (connect to running), 'persistent' (use profile), 'fresh' (clean browser)
    connection_mode: str = "cdp"

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0

    @classmethod
    def from_env(cls) -> "CrawlerConfig":
        """Create configuration from environment variables."""
        config = cls()

        # Chrome settings
        if os.environ.get("CHROME_DEBUG_PORT"):
            config.chrome.debug_port = int(os.environ["CHROME_DEBUG_PORT"])
        if os.environ.get("CHROME_HEADLESS"):
            config.chrome.headless = os.environ["CHROME_HEADLESS"].lower() in ("true", "1", "yes")
        if os.environ.get("CHROME_PROFILE"):
            config.chrome.profile = os.environ["CHROME_PROFILE"]

        # LLM settings
        if os.environ.get("LLM_PROVIDER"):
            config.llm.provider = os.environ["LLM_PROVIDER"]
        if os.environ.get("OLLAMA_HOST"):
            config.llm.ollama_host = os.environ["OLLAMA_HOST"]
        if os.environ.get("OLLAMA_MODEL"):
            config.llm.ollama_model = os.environ["OLLAMA_MODEL"]

        # Dashboard settings
        if os.environ.get("DASHBOARD_URL"):
            config.dashboard_url = os.environ["DASHBOARD_URL"]

        # Worker settings
        if os.environ.get("WORKER_ID"):
            config.worker_id = os.environ["WORKER_ID"]
        if os.environ.get("NODE_ID"):
            config.node_id = os.environ["NODE_ID"]

        return config

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "chrome": {
                "debug_port": self.chrome.debug_port,
                "headless": self.chrome.headless,
                "profile": self.chrome.profile,
                "timeout": self.chrome.timeout,
            },
            "llm": {
                "provider": self.llm.get_provider(),
                "claude_model": self.llm.claude_model,
                "ollama_model": self.llm.ollama_model,
                "ollama_host": self.llm.ollama_host,
                "temperature": self.llm.temperature,
            },
            "worker": {
                "id": self.worker_id,
                "node_id": self.node_id,
                "type": self.worker_type,
            },
            "dashboard_url": self.dashboard_url,
            "connection_mode": self.connection_mode,
            "poll_interval": self.poll_interval,
            "max_task_timeout": self.max_task_timeout,
        }


# Action types the crawler can perform
BROWSER_ACTIONS = [
    "click",  # Click on an element
    "type",  # Type text into an input
    "navigate",  # Go to a URL
    "scroll",  # Scroll the page
    "wait",  # Wait for element/time
    "screenshot",  # Take a screenshot
    "extract",  # Extract data from page
    "select",  # Select from dropdown
    "hover",  # Hover over element
    "press",  # Press keyboard key
    "evaluate",  # Run JavaScript
]

# Default system prompts for browser automation
SYSTEM_PROMPTS = {
    "browser_agent": """You are a browser automation agent. Your task is to help users accomplish web browsing tasks by generating precise actions.

Given the current page state (URL, title, visible elements), determine the next best action to accomplish the user's goal.

Available actions:
- click(selector): Click on an element
- type(selector, text): Type text into an input field
- navigate(url): Navigate to a URL
- scroll(direction, amount): Scroll the page (up/down, pixels)
- wait(selector or seconds): Wait for element or time
- extract(selector, attribute): Extract data from elements
- screenshot(): Take a screenshot
- done(result): Task is complete, return result

Always respond with a single action in JSON format:
{
    "action": "action_name",
    "params": {"param1": "value1"},
    "reasoning": "Brief explanation of why this action"
}

If the task is complete, use the "done" action with the result.
""",
    "extraction_agent": """You are a data extraction agent. Analyze the page content and extract the requested information.

Given the page HTML/text and the user's extraction request, identify and return the relevant data in structured JSON format.

Be precise and only extract what is explicitly requested. If data is not found, indicate it clearly.

Response format:
{
    "found": true/false,
    "data": { extracted data },
    "confidence": 0.0-1.0,
    "notes": "any relevant observations"
}
""",
}


if __name__ == "__main__":
    # Print current configuration
    config = CrawlerConfig.from_env()
    import json

    print(json.dumps(config.to_dict(), indent=2))
