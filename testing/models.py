"""
Test Framework Models

Data structures for data-driven testing.
All test specifics come from data, NOT code.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class StepType(str, Enum):
    """Types of test steps."""

    # Browser actions
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    WAIT = "wait"
    SCREENSHOT = "screenshot"

    # Assertions
    ASSERT_TEXT = "assert_text"
    ASSERT_ELEMENT = "assert_element"
    ASSERT_URL = "assert_url"
    ASSERT_TITLE = "assert_title"
    ASSERT_VALUE = "assert_value"
    ASSERT_VISIBLE = "assert_visible"
    ASSERT_NOT_VISIBLE = "assert_not_visible"

    # API actions
    API_GET = "api_get"
    API_POST = "api_post"
    API_PUT = "api_put"
    API_DELETE = "api_delete"

    # API assertions
    ASSERT_STATUS = "assert_status"
    ASSERT_JSON = "assert_json"
    ASSERT_HEADER = "assert_header"

    # Data operations
    EXTRACT = "extract"
    STORE = "store"
    COMPARE = "compare"

    # Control flow
    IF = "if"
    LOOP = "loop"
    WAIT_FOR = "wait_for"

    # Credential operations
    VAULT_GET = "vault_get"
    VAULT_INJECT = "vault_inject"


class TestStatus(str, Enum):
    """Test execution status."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestStep:
    """
    A single test step.

    Defined in data, executed by runner.
    """

    type: StepType
    target: Optional[str] = None  # Selector, URL, or variable name
    value: Optional[Any] = None  # Value to use
    options: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None
    timeout: float = 30.0
    optional: bool = False  # If True, failure doesn't stop test
    on_failure: Optional[str] = None  # Action on failure

    @classmethod
    def from_dict(cls, data: Dict) -> "TestStep":
        """Create from dictionary (loaded from data file)."""
        return cls(
            type=StepType(data["type"]),
            target=data.get("target"),
            value=data.get("value"),
            options=data.get("options", {}),
            description=data.get("description"),
            timeout=data.get("timeout", 30.0),
            optional=data.get("optional", False),
            on_failure=data.get("on_failure"),
        )


@dataclass
class TestCase:
    """
    A single test case containing multiple steps.

    All test-specific data comes from the data file.
    """

    id: str
    name: str
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    steps: List[TestStep] = field(default_factory=list)
    setup: List[TestStep] = field(default_factory=list)
    teardown: List[TestStep] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    credentials: Dict[str, str] = field(default_factory=dict)  # {var: "service_id/name"}
    skip_if: Optional[str] = None  # Condition to skip test
    retry: int = 0  # Number of retries on failure

    @classmethod
    def from_dict(cls, data: Dict) -> "TestCase":
        """Create from dictionary (loaded from data file)."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            tags=data.get("tags", []),
            steps=[TestStep.from_dict(s) for s in data.get("steps", [])],
            setup=[TestStep.from_dict(s) for s in data.get("setup", [])],
            teardown=[TestStep.from_dict(s) for s in data.get("teardown", [])],
            variables=data.get("variables", {}),
            credentials=data.get("credentials", {}),
            skip_if=data.get("skip_if"),
            retry=data.get("retry", 0),
        )


@dataclass
class TestSuite:
    """
    A collection of test cases.

    Loaded from a data file (JSON/YAML).
    """

    id: str
    name: str
    description: Optional[str] = None
    target_service: Optional[str] = None  # Service being tested
    target_url: Optional[str] = None  # Base URL
    tags: List[str] = field(default_factory=list)
    test_cases: List[TestCase] = field(default_factory=list)
    global_setup: List[TestStep] = field(default_factory=list)
    global_teardown: List[TestStep] = field(default_factory=list)
    global_variables: Dict[str, Any] = field(default_factory=dict)
    parallel: bool = False  # Run tests in parallel
    stop_on_failure: bool = False  # Stop suite on first failure

    @classmethod
    def from_dict(cls, data: Dict) -> "TestSuite":
        """Create from dictionary (loaded from data file)."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            target_service=data.get("target_service"),
            target_url=data.get("target_url"),
            tags=data.get("tags", []),
            test_cases=[TestCase.from_dict(tc) for tc in data.get("test_cases", [])],
            global_setup=[TestStep.from_dict(s) for s in data.get("global_setup", [])],
            global_teardown=[TestStep.from_dict(s) for s in data.get("global_teardown", [])],
            global_variables=data.get("global_variables", {}),
            parallel=data.get("parallel", False),
            stop_on_failure=data.get("stop_on_failure", False),
        )


@dataclass
class StepResult:
    """Result of a single step execution."""

    step: TestStep
    status: TestStatus
    duration: float = 0.0
    error: Optional[str] = None
    screenshot: Optional[str] = None
    extracted_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    """Result of a test case execution."""

    test_case: TestCase
    status: TestStatus
    step_results: List[StepResult] = field(default_factory=list)
    duration: float = 0.0
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    variables: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage/API."""
        return {
            "test_id": self.test_case.id,
            "test_name": self.test_case.name,
            "status": self.status.value,
            "duration": self.duration,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
            "steps_passed": sum(1 for s in self.step_results if s.status == TestStatus.PASSED),
            "steps_failed": sum(1 for s in self.step_results if s.status == TestStatus.FAILED),
            "steps_total": len(self.step_results),
        }


@dataclass
class SuiteResult:
    """Result of a test suite execution."""

    suite: TestSuite
    status: TestStatus
    test_results: List[TestResult] = field(default_factory=list)
    duration: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    @property
    def passed(self) -> int:
        return sum(1 for r in self.test_results if r.status == TestStatus.PASSED)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.test_results if r.status == TestStatus.FAILED)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.test_results if r.status == TestStatus.SKIPPED)

    @property
    def total(self) -> int:
        return len(self.test_results)

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage/API."""
        return {
            "suite_id": self.suite.id,
            "suite_name": self.suite.name,
            "status": self.status.value,
            "duration": self.duration,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "total": self.total,
            "tests": [r.to_dict() for r in self.test_results],
        }
