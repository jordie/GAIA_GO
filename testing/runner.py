"""
Data-Driven Test Runner

Executes tests based on data definitions.
Code is GENERIC - all test specifics come from data.
"""

import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from .models import (
    StepResult,
    StepType,
    SuiteResult,
    TestCase,
    TestResult,
    TestStatus,
    TestStep,
    TestSuite,
)

logger = logging.getLogger(__name__)

# Vault configuration
VAULT_URL = os.environ.get("VAULT_URL", "http://100.112.58.92:9000")


class TestRunner:
    """
    Generic test runner that executes tests from data definitions.

    The runner itself has NO knowledge of what it's testing.
    All specifics come from the test data.
    """

    def __init__(
        self,
        vault_url: str = None,
        vault_token: str = None,
        headless: bool = True,
        screenshot_dir: str = None,
    ):
        self.vault_url = vault_url or VAULT_URL
        self.vault_token = vault_token
        self.headless = headless
        self.screenshot_dir = screenshot_dir

        # Runtime state
        self._variables: Dict[str, Any] = {}
        self._browser = None
        self._page = None
        self._http_client = None

        # Step handlers - map step types to execution functions
        self._handlers: Dict[StepType, Callable] = {
            # Browser actions
            StepType.NAVIGATE: self._handle_navigate,
            StepType.CLICK: self._handle_click,
            StepType.FILL: self._handle_fill,
            StepType.SELECT: self._handle_select,
            StepType.WAIT: self._handle_wait,
            StepType.SCREENSHOT: self._handle_screenshot,
            # Assertions
            StepType.ASSERT_TEXT: self._handle_assert_text,
            StepType.ASSERT_ELEMENT: self._handle_assert_element,
            StepType.ASSERT_URL: self._handle_assert_url,
            StepType.ASSERT_VISIBLE: self._handle_assert_visible,
            # API actions
            StepType.API_GET: self._handle_api_get,
            StepType.API_POST: self._handle_api_post,
            StepType.ASSERT_STATUS: self._handle_assert_status,
            StepType.ASSERT_JSON: self._handle_assert_json,
            # Data operations
            StepType.EXTRACT: self._handle_extract,
            StepType.STORE: self._handle_store,
            # Vault operations
            StepType.VAULT_GET: self._handle_vault_get,
            StepType.VAULT_INJECT: self._handle_vault_inject,
            # Control flow
            StepType.WAIT_FOR: self._handle_wait_for,
        }

    def _interpolate(self, value: Any) -> Any:
        """Replace ${variable} placeholders with values."""
        if isinstance(value, str):
            pattern = r"\$\{(\w+)\}"
            matches = re.findall(pattern, value)
            for var_name in matches:
                if var_name in self._variables:
                    var_value = self._variables[var_name]
                    if value == f"${{{var_name}}}":
                        return var_value  # Return actual type
                    value = value.replace(f"${{{var_name}}}", str(var_value))
            return value
        return value

    async def _ensure_browser(self):
        """Ensure browser is started."""
        if self._browser is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._page = await self._browser.new_page()

    async def _close_browser(self):
        """Close browser."""
        if self._browser:
            await self._browser.close()
            await self._playwright.stop()
            self._browser = None
            self._page = None

    async def _ensure_http_client(self):
        """Ensure HTTP client is available."""
        if self._http_client is None:
            import aiohttp

            self._http_client = aiohttp.ClientSession()

    async def _close_http_client(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.close()
            self._http_client = None

    # =========================================================================
    # Step Handlers - Browser
    # =========================================================================

    async def _handle_navigate(self, step: TestStep) -> StepResult:
        """Navigate to URL."""
        await self._ensure_browser()
        url = self._interpolate(step.target)
        await self._page.goto(url, timeout=step.timeout * 1000)
        return StepResult(step=step, status=TestStatus.PASSED)

    async def _handle_click(self, step: TestStep) -> StepResult:
        """Click element."""
        await self._ensure_browser()
        selector = self._interpolate(step.target)
        await self._page.click(selector, timeout=step.timeout * 1000)
        return StepResult(step=step, status=TestStatus.PASSED)

    async def _handle_fill(self, step: TestStep) -> StepResult:
        """Fill form field."""
        await self._ensure_browser()
        selector = self._interpolate(step.target)
        value = self._interpolate(step.value)
        await self._page.fill(selector, str(value), timeout=step.timeout * 1000)
        return StepResult(step=step, status=TestStatus.PASSED)

    async def _handle_select(self, step: TestStep) -> StepResult:
        """Select dropdown option."""
        await self._ensure_browser()
        selector = self._interpolate(step.target)
        value = self._interpolate(step.value)
        await self._page.select_option(selector, value, timeout=step.timeout * 1000)
        return StepResult(step=step, status=TestStatus.PASSED)

    async def _handle_wait(self, step: TestStep) -> StepResult:
        """Wait for specified time."""
        duration = float(step.value or 1)
        await asyncio.sleep(duration)
        return StepResult(step=step, status=TestStatus.PASSED)

    async def _handle_screenshot(self, step: TestStep) -> StepResult:
        """Take screenshot."""
        await self._ensure_browser()
        filename = (
            self._interpolate(step.value)
            or f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        if self.screenshot_dir:
            filename = os.path.join(self.screenshot_dir, filename)
        await self._page.screenshot(path=filename)
        return StepResult(step=step, status=TestStatus.PASSED, screenshot=filename)

    # =========================================================================
    # Step Handlers - Assertions
    # =========================================================================

    async def _handle_assert_text(self, step: TestStep) -> StepResult:
        """Assert text is present on page or in element."""
        await self._ensure_browser()
        expected = self._interpolate(step.value)

        if step.target:
            selector = self._interpolate(step.target)
            element = await self._page.wait_for_selector(selector, timeout=step.timeout * 1000)
            actual = await element.text_content()
        else:
            actual = await self._page.content()

        if expected in actual:
            return StepResult(step=step, status=TestStatus.PASSED)
        else:
            return StepResult(
                step=step, status=TestStatus.FAILED, error=f"Expected text '{expected}' not found"
            )

    async def _handle_assert_element(self, step: TestStep) -> StepResult:
        """Assert element exists."""
        await self._ensure_browser()
        selector = self._interpolate(step.target)
        try:
            await self._page.wait_for_selector(selector, timeout=step.timeout * 1000)
            return StepResult(step=step, status=TestStatus.PASSED)
        except Exception:
            return StepResult(
                step=step, status=TestStatus.FAILED, error=f"Element not found: {selector}"
            )

    async def _handle_assert_url(self, step: TestStep) -> StepResult:
        """Assert current URL matches pattern."""
        await self._ensure_browser()
        expected = self._interpolate(step.value)
        actual = self._page.url

        if expected in actual or re.match(expected, actual):
            return StepResult(step=step, status=TestStatus.PASSED)
        else:
            return StepResult(
                step=step,
                status=TestStatus.FAILED,
                error=f"URL mismatch. Expected: {expected}, Actual: {actual}",
            )

    async def _handle_assert_visible(self, step: TestStep) -> StepResult:
        """Assert element is visible."""
        await self._ensure_browser()
        selector = self._interpolate(step.target)
        try:
            element = await self._page.wait_for_selector(
                selector, state="visible", timeout=step.timeout * 1000
            )
            if element:
                return StepResult(step=step, status=TestStatus.PASSED)
        except Exception:
            pass
        return StepResult(
            step=step, status=TestStatus.FAILED, error=f"Element not visible: {selector}"
        )

    # =========================================================================
    # Step Handlers - API
    # =========================================================================

    async def _handle_api_get(self, step: TestStep) -> StepResult:
        """Make GET request."""
        await self._ensure_http_client()
        url = self._interpolate(step.target)
        headers = {k: self._interpolate(v) for k, v in step.options.get("headers", {}).items()}

        async with self._http_client.get(url, headers=headers) as resp:
            self._variables["_response"] = resp
            self._variables["_status"] = resp.status
            self._variables["_body"] = await resp.text()
            try:
                self._variables["_json"] = await resp.json()
            except:
                pass

        return StepResult(step=step, status=TestStatus.PASSED)

    async def _handle_api_post(self, step: TestStep) -> StepResult:
        """Make POST request."""
        await self._ensure_http_client()
        url = self._interpolate(step.target)
        headers = {k: self._interpolate(v) for k, v in step.options.get("headers", {}).items()}
        data = self._interpolate(step.value)

        async with self._http_client.post(url, json=data, headers=headers) as resp:
            self._variables["_response"] = resp
            self._variables["_status"] = resp.status
            self._variables["_body"] = await resp.text()
            try:
                self._variables["_json"] = await resp.json()
            except:
                pass

        return StepResult(step=step, status=TestStatus.PASSED)

    async def _handle_assert_status(self, step: TestStep) -> StepResult:
        """Assert HTTP status code."""
        expected = int(self._interpolate(step.value))
        actual = self._variables.get("_status")

        if actual == expected:
            return StepResult(step=step, status=TestStatus.PASSED)
        else:
            return StepResult(
                step=step,
                status=TestStatus.FAILED,
                error=f"Status mismatch. Expected: {expected}, Actual: {actual}",
            )

    async def _handle_assert_json(self, step: TestStep) -> StepResult:
        """Assert JSON response matches."""
        json_data = self._variables.get("_json", {})
        path = step.target  # e.g., "data.user.name"
        expected = self._interpolate(step.value)

        # Navigate JSON path
        current = json_data
        for key in path.split("."):
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and key.isdigit():
                current = current[int(key)]
            else:
                return StepResult(
                    step=step, status=TestStatus.FAILED, error=f"JSON path not found: {path}"
                )

        if current == expected:
            return StepResult(step=step, status=TestStatus.PASSED)
        else:
            return StepResult(
                step=step,
                status=TestStatus.FAILED,
                error=f"JSON value mismatch at {path}. Expected: {expected}, Actual: {current}",
            )

    # =========================================================================
    # Step Handlers - Data Operations
    # =========================================================================

    async def _handle_extract(self, step: TestStep) -> StepResult:
        """Extract data from page into variable."""
        await self._ensure_browser()
        selector = self._interpolate(step.target)
        var_name = step.value

        try:
            element = await self._page.wait_for_selector(selector, timeout=step.timeout * 1000)
            text = await element.text_content()
            self._variables[var_name] = text.strip()
            return StepResult(
                step=step, status=TestStatus.PASSED, extracted_data={var_name: text.strip()}
            )
        except Exception as e:
            return StepResult(step=step, status=TestStatus.FAILED, error=str(e))

    async def _handle_store(self, step: TestStep) -> StepResult:
        """Store value in variable."""
        var_name = step.target
        value = self._interpolate(step.value)
        self._variables[var_name] = value
        return StepResult(step=step, status=TestStatus.PASSED)

    # =========================================================================
    # Step Handlers - Vault
    # =========================================================================

    async def _handle_vault_get(self, step: TestStep) -> StepResult:
        """Get credential from vault."""
        import aiohttp

        service_id = self._interpolate(step.target)
        cred_name = self._interpolate(step.options.get("name"))

        try:
            async with aiohttp.ClientSession() as session:
                headers = {"X-Vault-Token": self.vault_token}
                async with session.get(
                    f"{self.vault_url}/api/credentials/service/{service_id}", headers=headers
                ) as resp:
                    if resp.status == 200:
                        creds = await resp.json()
                        for cred in creds:
                            if not cred_name or cred["name"] == cred_name:
                                # Store credential parts in variables
                                prefix = step.value or service_id
                                self._variables[f"{prefix}_username"] = cred.get("username")
                                self._variables[f"{prefix}_password"] = cred.get("password")
                                return StepResult(step=step, status=TestStatus.PASSED)

            return StepResult(step=step, status=TestStatus.FAILED, error="Credential not found")
        except Exception as e:
            return StepResult(step=step, status=TestStatus.FAILED, error=str(e))

    async def _handle_vault_inject(self, step: TestStep) -> StepResult:
        """Inject credential into form fields."""
        username_selector = step.options.get("username_field")
        password_selector = step.options.get("password_field")
        prefix = self._interpolate(step.target)

        if username_selector and f"{prefix}_username" in self._variables:
            await self._page.fill(username_selector, self._variables[f"{prefix}_username"])

        if password_selector and f"{prefix}_password" in self._variables:
            await self._page.fill(password_selector, self._variables[f"{prefix}_password"])

        return StepResult(step=step, status=TestStatus.PASSED)

    # =========================================================================
    # Step Handlers - Control Flow
    # =========================================================================

    async def _handle_wait_for(self, step: TestStep) -> StepResult:
        """Wait for element or condition."""
        await self._ensure_browser()
        selector = self._interpolate(step.target)
        state = step.options.get("state", "visible")

        try:
            await self._page.wait_for_selector(selector, state=state, timeout=step.timeout * 1000)
            return StepResult(step=step, status=TestStatus.PASSED)
        except Exception as e:
            return StepResult(step=step, status=TestStatus.FAILED, error=str(e))

    # =========================================================================
    # Execution
    # =========================================================================

    async def execute_step(self, step: TestStep) -> StepResult:
        """Execute a single test step."""
        handler = self._handlers.get(step.type)
        if not handler:
            return StepResult(
                step=step, status=TestStatus.ERROR, error=f"No handler for step type: {step.type}"
            )

        try:
            start = datetime.now()
            result = await handler(step)
            result.duration = (datetime.now() - start).total_seconds()
            return result
        except Exception as e:
            return StepResult(
                step=step,
                status=TestStatus.FAILED if step.optional else TestStatus.ERROR,
                error=str(e),
            )

    async def execute_test_case(self, test_case: TestCase) -> TestResult:
        """Execute a single test case."""
        logger.info(f"Running test: {test_case.name}")

        result = TestResult(
            test_case=test_case, status=TestStatus.RUNNING, started_at=datetime.now().isoformat()
        )

        # Merge variables
        self._variables.update(test_case.variables)

        # Load credentials from vault
        for var_prefix, cred_ref in test_case.credentials.items():
            parts = cred_ref.split("/")
            service_id = parts[0]
            cred_name = parts[1] if len(parts) > 1 else None
            step = TestStep(
                type=StepType.VAULT_GET,
                target=service_id,
                value=var_prefix,
                options={"name": cred_name},
            )
            await self.execute_step(step)

        # Execute setup
        for step in test_case.setup:
            step_result = await self.execute_step(step)
            result.step_results.append(step_result)
            if step_result.status in [TestStatus.FAILED, TestStatus.ERROR] and not step.optional:
                result.status = TestStatus.FAILED
                result.error = f"Setup failed: {step_result.error}"
                result.completed_at = datetime.now().isoformat()
                return result

        # Execute steps
        for step in test_case.steps:
            step_result = await self.execute_step(step)
            result.step_results.append(step_result)

            if step_result.status in [TestStatus.FAILED, TestStatus.ERROR] and not step.optional:
                result.status = TestStatus.FAILED
                result.error = step_result.error
                break

        # Execute teardown (always)
        for step in test_case.teardown:
            step_result = await self.execute_step(step)
            result.step_results.append(step_result)

        # Set final status
        if result.status == TestStatus.RUNNING:
            result.status = TestStatus.PASSED

        result.completed_at = datetime.now().isoformat()
        result.duration = sum(s.duration for s in result.step_results)
        result.variables = dict(self._variables)

        logger.info(f"Test {test_case.name}: {result.status.value}")
        return result

    async def execute_suite(self, suite: TestSuite) -> SuiteResult:
        """Execute a test suite."""
        logger.info(f"Running suite: {suite.name}")

        result = SuiteResult(
            suite=suite, status=TestStatus.RUNNING, started_at=datetime.now().isoformat()
        )

        # Initialize global variables
        self._variables = dict(suite.global_variables)
        if suite.target_url:
            self._variables["base_url"] = suite.target_url

        try:
            # Execute global setup
            for step in suite.global_setup:
                await self.execute_step(step)

            # Execute test cases
            for test_case in suite.test_cases:
                test_result = await self.execute_test_case(test_case)
                result.test_results.append(test_result)

                if test_result.status == TestStatus.FAILED and suite.stop_on_failure:
                    break

            # Execute global teardown
            for step in suite.global_teardown:
                await self.execute_step(step)

        finally:
            await self._close_browser()
            await self._close_http_client()

        # Set final status
        if result.failed > 0:
            result.status = TestStatus.FAILED
        else:
            result.status = TestStatus.PASSED

        result.completed_at = datetime.now().isoformat()
        result.duration = sum(r.duration for r in result.test_results)

        logger.info(f"Suite {suite.name}: {result.passed}/{result.total} passed")
        return result
