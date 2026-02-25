"""
Unit tests for utils module.

E2E Test Feature 1766458534 - Test feature for E2E workflow validation.
"""

import importlib.util
import os
import sys
from datetime import datetime

import pytest

# Add parent directory to path to import from root utils.py
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

# Import from root utils.py, not utils package
spec = importlib.util.spec_from_file_location("utils_module", os.path.join(root_dir, "utils.py"))
utils_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils_module)

ErrorContext = utils_module.ErrorContext
WidgetDataHandler = utils_module.WidgetDataHandler
calculate_progress = utils_module.calculate_progress
chunk_list = utils_module.chunk_list
clamp_value = utils_module.clamp_value
classify_error = utils_module.classify_error
dedupe_list = utils_module.dedupe_list
estimate_completion = utils_module.estimate_completion
flatten_list = utils_module.flatten_list
format_api_response = utils_module.format_api_response
format_error_response = utils_module.format_error_response
format_timestamp = utils_module.format_timestamp
group_by = utils_module.group_by
merge_dicts = utils_module.merge_dicts
normalize_status = utils_module.normalize_status
parse_priority = utils_module.parse_priority
safe_execute = utils_module.safe_execute
safe_get = utils_module.safe_get
sanitize_string = utils_module.sanitize_string
truncate_string = utils_module.truncate_string
validate_entity_data = utils_module.validate_entity_data
validate_lifecycle_state = utils_module.validate_lifecycle_state


class TestValidateEntityData:
    """Tests for validate_entity_data function."""

    def test_valid_data_with_all_required_fields(self):
        """Test validation passes when all required fields present."""
        data = {"name": "Test Project", "status": "active", "description": "A test"}
        result = validate_entity_data(data, ["name", "status"])

        assert result["valid"] is True
        assert result["missing_fields"] == []
        assert result["message"] == "Validation passed"

    def test_missing_single_field(self):
        """Test validation fails when one required field is missing."""
        data = {"name": "Test Project"}
        result = validate_entity_data(data, ["name", "status"])

        assert result["valid"] is False
        assert "status" in result["missing_fields"]
        assert "status" in result["message"]

    def test_missing_multiple_fields(self):
        """Test validation fails when multiple required fields are missing."""
        data = {"description": "Some text"}
        result = validate_entity_data(data, ["name", "status", "priority"])

        assert result["valid"] is False
        assert len(result["missing_fields"]) == 3
        assert "name" in result["missing_fields"]
        assert "status" in result["missing_fields"]
        assert "priority" in result["missing_fields"]

    def test_empty_required_fields_list(self):
        """Test validation passes with empty required fields list."""
        data = {"anything": "value"}
        result = validate_entity_data(data, [])

        assert result["valid"] is True
        assert result["missing_fields"] == []

    def test_empty_data_dict(self):
        """Test validation fails when data is empty but fields required."""
        data = {}
        result = validate_entity_data(data, ["name"])

        assert result["valid"] is False
        assert "name" in result["missing_fields"]

    def test_none_value_treated_as_missing(self):
        """Test that None values are treated as missing fields."""
        data = {"name": "Test", "status": None}
        result = validate_entity_data(data, ["name", "status"])

        assert result["valid"] is False
        assert "status" in result["missing_fields"]

    def test_non_dict_data_returns_invalid(self):
        """Test validation fails gracefully with non-dict input."""
        result = validate_entity_data("not a dict", ["name"])

        assert result["valid"] is False
        assert "Data must be a dictionary" in result["message"]


class TestFormatTimestamp:
    """Tests for format_timestamp function."""

    def test_format_specific_datetime(self):
        """Test formatting a specific datetime."""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = format_timestamp(dt)

        assert result == "2024-01-15 10:30:45"

    def test_custom_format_string(self):
        """Test with custom format string."""
        dt = datetime(2024, 6, 20, 14, 0, 0)
        result = format_timestamp(dt, "%Y/%m/%d")

        assert result == "2024/06/20"

    def test_none_uses_current_time(self):
        """Test that None defaults to current time."""
        result = format_timestamp(None)

        # Should be a valid timestamp string
        assert len(result) == 19  # 'YYYY-MM-DD HH:MM:SS'
        assert result[4] == "-"
        assert result[10] == " "

    def test_iso_format(self):
        """Test ISO format output."""
        dt = datetime(2024, 3, 14, 9, 26, 53)
        result = format_timestamp(dt, "%Y-%m-%dT%H:%M:%S")

        assert result == "2024-03-14T09:26:53"


class TestSanitizeString:
    """Tests for sanitize_string function."""

    def test_strip_whitespace(self):
        """Test stripping leading and trailing whitespace."""
        result = sanitize_string("  hello world  ")

        assert result == "hello world"

    def test_truncate_long_string(self):
        """Test truncating string longer than max_length."""
        long_string = "A" * 300
        result = sanitize_string(long_string, max_length=10)

        assert result == "AAAAAAAAAA"
        assert len(result) == 10

    def test_default_max_length(self):
        """Test default max_length of 255."""
        long_string = "B" * 500
        result = sanitize_string(long_string)

        assert len(result) == 255

    def test_short_string_unchanged(self):
        """Test short strings remain unchanged."""
        result = sanitize_string("short", max_length=100)

        assert result == "short"

    def test_non_string_input(self):
        """Test non-string input is converted."""
        result = sanitize_string(12345, max_length=3)

        assert result == "123"

    def test_empty_string(self):
        """Test empty string returns empty."""
        result = sanitize_string("")

        assert result == ""

    def test_whitespace_only_string(self):
        """Test whitespace-only string returns empty."""
        result = sanitize_string("   ")

        assert result == ""


class TestCalculateProgress:
    """Tests for calculate_progress function.

    E2E Test Feature 1766509045 - Test feature for E2E workflow validation.
    """

    def test_fifty_percent_progress(self):
        """Test 50% progress calculation."""
        result = calculate_progress(5, 10)

        assert result["percentage"] == 50
        assert result["completed"] == 5
        assert result["total"] == 10
        assert result["remaining"] == 5
        assert result["status"] == "in_progress"

    def test_complete_progress(self):
        """Test 100% complete progress."""
        result = calculate_progress(10, 10)

        assert result["percentage"] == 100
        assert result["completed"] == 10
        assert result["remaining"] == 0
        assert result["status"] == "complete"

    def test_not_started(self):
        """Test 0% progress (not started)."""
        result = calculate_progress(0, 5)

        assert result["percentage"] == 0
        assert result["completed"] == 0
        assert result["remaining"] == 5
        assert result["status"] == "not_started"

    def test_almost_done_status(self):
        """Test almost_done status at 75%+."""
        result = calculate_progress(8, 10)

        assert result["percentage"] == 80
        assert result["status"] == "almost_done"

    def test_just_started_status(self):
        """Test just_started status at <25%."""
        result = calculate_progress(1, 10)

        assert result["percentage"] == 10
        assert result["status"] == "just_started"

    def test_zero_total_returns_empty(self):
        """Test zero total returns empty status."""
        result = calculate_progress(0, 0)

        assert result["percentage"] == 0
        assert result["status"] == "empty"

    def test_negative_total_returns_empty(self):
        """Test negative total returns empty status."""
        result = calculate_progress(5, -1)

        assert result["percentage"] == 0
        assert result["status"] == "empty"

    def test_completed_exceeds_total_clamped(self):
        """Test completed value is clamped to total."""
        result = calculate_progress(15, 10)

        assert result["completed"] == 10
        assert result["percentage"] == 100
        assert result["status"] == "complete"

    def test_negative_completed_clamped_to_zero(self):
        """Test negative completed is clamped to zero."""
        result = calculate_progress(-5, 10)

        assert result["completed"] == 0
        assert result["percentage"] == 0
        assert result["status"] == "not_started"


class TestFormatApiResponse:
    """Tests for format_api_response function.

    Claude Test Feature - Test feature for Claude integration testing.
    """

    def test_successful_response_with_data(self):
        """Test successful response includes data."""
        result = format_api_response(True, data={"id": 1, "name": "Test"})

        assert result["success"] is True
        assert result["data"] == {"id": 1, "name": "Test"}
        assert result["error"] is None
        assert "timestamp" in result

    def test_failed_response_with_error(self):
        """Test failed response includes error message."""
        result = format_api_response(False, error="Not found")

        assert result["success"] is False
        assert result["data"] is None
        assert result["error"] == "Not found"
        assert "timestamp" in result

    def test_response_with_metadata(self):
        """Test response includes optional metadata."""
        meta = {"page": 1, "total": 100}
        result = format_api_response(True, data=[], meta=meta)

        assert result["meta"] == meta
        assert result["success"] is True

    def test_timestamp_is_iso_format(self):
        """Test timestamp is in ISO format."""
        result = format_api_response(True)

        # ISO format: YYYY-MM-DDTHH:MM:SS.ffffff
        assert "T" in result["timestamp"]
        assert len(result["timestamp"]) >= 19

    def test_success_ignores_error_param(self):
        """Test successful response ignores error parameter."""
        result = format_api_response(True, data={"ok": True}, error="Should be ignored")

        assert result["success"] is True
        assert result["error"] is None
        assert result["data"] == {"ok": True}

    def test_failure_ignores_data_param(self):
        """Test failed response ignores data parameter."""
        result = format_api_response(False, data={"should": "ignore"}, error="Error occurred")

        assert result["success"] is False
        assert result["data"] is None
        assert result["error"] == "Error occurred"

    def test_empty_success_response(self):
        """Test successful response with no data."""
        result = format_api_response(True)

        assert result["success"] is True
        assert result["data"] is None
        assert result["error"] is None

    def test_list_data_response(self):
        """Test response with list data."""
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = format_api_response(True, data=items)

        assert result["success"] is True
        assert result["data"] == items
        assert len(result["data"]) == 3


class TestWidgetDataHandler:
    """Tests for WidgetDataHandler class.

    Workflow Test Feature - Tests for widget component that:
    - Displays data correctly
    - Updates in real-time
    - Handles errors gracefully
    """

    def test_initialization_with_data(self):
        """Test widget initializes with provided data."""
        widget = WidgetDataHandler("test-widget", {"count": 10})

        assert widget.widget_id == "test-widget"
        assert widget.data == {"count": 10}
        assert widget.status == "ready"
        assert widget.update_count == 0

    def test_initialization_without_data(self):
        """Test widget initializes with empty data when none provided."""
        widget = WidgetDataHandler("empty-widget")

        assert widget.widget_id == "empty-widget"
        assert widget.data == {}
        assert widget.status == "ready"

    def test_update_merges_data(self):
        """Test update merges new data with existing."""
        widget = WidgetDataHandler("test", {"a": 1})
        result = widget.update({"b": 2})

        assert result is True
        assert widget.data == {"a": 1, "b": 2}
        assert widget.update_count == 1

    def test_update_tracks_count(self):
        """Test update increments update counter."""
        widget = WidgetDataHandler("test")
        widget.update({"x": 1})
        widget.update({"y": 2})
        widget.update({"z": 3})

        assert widget.update_count == 3

    def test_update_rejects_non_dict(self):
        """Test update handles non-dict data gracefully."""
        widget = WidgetDataHandler("test")
        result = widget.update("invalid")

        assert result is False
        assert widget.status == "error"
        assert widget.error_state == "Invalid data type: expected dictionary"

    def test_get_display_data_format(self):
        """Test get_display_data returns correct format."""
        widget = WidgetDataHandler("stats", {"value": 42})
        display = widget.get_display_data()

        assert display["widget_id"] == "stats"
        assert display["data"] == {"value": 42}
        assert display["status"] == "ready"
        assert "last_updated" in display
        assert display["update_count"] == 0
        assert display["error"] is None

    def test_set_loading_state(self):
        """Test widget can be set to loading state."""
        widget = WidgetDataHandler("test")
        widget.set_loading()

        assert widget.status == "loading"

    def test_set_error_state(self):
        """Test widget can be set to error state with message."""
        widget = WidgetDataHandler("test")
        widget.set_error("Connection failed")

        assert widget.status == "error"
        assert widget.error_state == "Connection failed"

    def test_clear_error_restores_ready(self):
        """Test clear_error returns widget to ready state."""
        widget = WidgetDataHandler("test")
        widget.set_error("Some error")
        widget.clear_error()

        assert widget.status == "ready"
        assert widget.error_state is None

    def test_reset_clears_all_state(self):
        """Test reset clears data and counters."""
        widget = WidgetDataHandler("test", {"data": "value"})
        widget.update({"more": "data"})
        widget.set_error("Error")
        widget.reset()

        assert widget.data == {}
        assert widget.update_count == 0
        assert widget.status == "ready"
        assert widget.error_state is None

    def test_last_updated_changes_on_update(self):
        """Test last_updated timestamp changes after update."""
        widget = WidgetDataHandler("test")
        initial_time = widget.last_updated

        import time

        time.sleep(0.01)  # Small delay
        widget.update({"new": "data"})

        assert widget.last_updated > initial_time


class TestNormalizeStatus:
    """Tests for normalize_status function.

    E2E Test Feature 1766597951 - Test feature for E2E workflow validation.
    """

    def test_valid_status_lowercase(self):
        """Test valid status is recognized."""
        result = normalize_status("pending")

        assert result["original"] == "pending"
        assert result["normalized"] == "pending"
        assert result["valid"] is True
        assert result["suggested"] is None

    def test_valid_status_uppercase(self):
        """Test uppercase status is normalized."""
        result = normalize_status("COMPLETED")

        assert result["normalized"] == "completed"
        assert result["valid"] is True

    def test_status_with_whitespace(self):
        """Test whitespace is stripped."""
        result = normalize_status("  in_progress  ")

        assert result["normalized"] == "in_progress"
        assert result["valid"] is True

    def test_status_with_spaces_converted(self):
        """Test spaces in status are converted to underscores."""
        result = normalize_status("In Progress")

        assert result["normalized"] == "in_progress"
        assert result["valid"] is True

    def test_status_with_dashes_converted(self):
        """Test dashes are converted to underscores."""
        result = normalize_status("in-progress")

        assert result["normalized"] == "in_progress"
        assert result["valid"] is True

    def test_invalid_status_no_suggestion(self):
        """Test invalid status without mapping returns no suggestion."""
        result = normalize_status("unknown")

        assert result["valid"] is False
        assert result["suggested"] is None

    def test_invalid_status_with_suggestion_done(self):
        """Test 'done' suggests 'completed'."""
        result = normalize_status("DONE")

        assert result["valid"] is False
        assert result["suggested"] == "completed"

    def test_invalid_status_with_suggestion_active(self):
        """Test 'active' suggests 'in_progress'."""
        result = normalize_status("active")

        assert result["valid"] is False
        assert result["suggested"] == "in_progress"

    def test_invalid_status_with_suggestion_error(self):
        """Test 'error' suggests 'failed'."""
        result = normalize_status("error")

        assert result["valid"] is False
        assert result["suggested"] == "failed"

    def test_custom_valid_statuses(self):
        """Test with custom valid statuses list."""
        result = normalize_status("done", valid_statuses=["pending", "done"])

        assert result["valid"] is True
        assert result["suggested"] is None

    def test_custom_valid_statuses_invalid(self):
        """Test custom valid statuses with invalid status."""
        result = normalize_status("completed", valid_statuses=["pending", "done"])

        assert result["valid"] is False

    def test_original_preserved(self):
        """Test original status is preserved in output."""
        result = normalize_status("  Mixed CASE  ")

        assert result["original"] == "  Mixed CASE  "
        assert result["normalized"] == "mixed_case"


class TestValidateLifecycleState:
    """Tests for validate_lifecycle_state function.

    E2E Full Lifecycle 1766629424 - Test feature for lifecycle validation.
    """

    def test_pending_to_in_progress_allowed(self):
        """Test transition from pending to in_progress is allowed."""
        result = validate_lifecycle_state("pending", "in_progress")

        assert result["allowed"] is True
        assert result["current"] == "pending"
        assert result["target"] == "in_progress"
        assert result["message"] == "Transition allowed"

    def test_pending_to_cancelled_allowed(self):
        """Test transition from pending to cancelled is allowed."""
        result = validate_lifecycle_state("pending", "cancelled")

        assert result["allowed"] is True

    def test_in_progress_to_completed_allowed(self):
        """Test transition from in_progress to completed is allowed."""
        result = validate_lifecycle_state("in_progress", "completed")

        assert result["allowed"] is True

    def test_in_progress_to_failed_allowed(self):
        """Test transition from in_progress to failed is allowed."""
        result = validate_lifecycle_state("in_progress", "failed")

        assert result["allowed"] is True

    def test_completed_to_pending_not_allowed(self):
        """Test transition from completed to pending is not allowed."""
        result = validate_lifecycle_state("completed", "pending")

        assert result["allowed"] is False
        assert "Cannot transition" in result["message"]

    def test_completed_to_in_progress_allowed(self):
        """Test reopening completed item is allowed."""
        result = validate_lifecycle_state("completed", "in_progress")

        assert result["allowed"] is True

    def test_failed_to_pending_allowed(self):
        """Test retry from failed to pending is allowed."""
        result = validate_lifecycle_state("failed", "pending")

        assert result["allowed"] is True

    def test_cancelled_to_pending_allowed(self):
        """Test reactivation from cancelled is allowed."""
        result = validate_lifecycle_state("cancelled", "pending")

        assert result["allowed"] is True

    def test_same_state_no_change(self):
        """Test same state transition returns no change message."""
        result = validate_lifecycle_state("in_progress", "in_progress")

        assert result["allowed"] is True
        assert result["message"] == "No state change required"

    def test_normalizes_states(self):
        """Test states are normalized before comparison."""
        result = validate_lifecycle_state("  PENDING  ", "In-Progress")

        assert result["allowed"] is True
        assert result["current"] == "pending"
        assert result["target"] == "in_progress"

    def test_unknown_current_state(self):
        """Test unknown current state has no valid transitions."""
        result = validate_lifecycle_state("unknown", "pending")

        assert result["allowed"] is False


class TestParsePriority:
    """Tests for parse_priority function.

    Claude Test Feature - Test feature for priority parsing.
    """

    def test_valid_string_low(self):
        """Test parsing 'low' priority string."""
        result = parse_priority("low")

        assert result["priority"] == "low"
        assert result["level"] == 1
        assert result["valid"] is True
        assert result["color"] == "gray"

    def test_valid_string_medium(self):
        """Test parsing 'medium' priority string."""
        result = parse_priority("medium")

        assert result["priority"] == "medium"
        assert result["level"] == 2
        assert result["valid"] is True
        assert result["color"] == "blue"

    def test_valid_string_high(self):
        """Test parsing 'high' priority string."""
        result = parse_priority("high")

        assert result["priority"] == "high"
        assert result["level"] == 3
        assert result["valid"] is True
        assert result["color"] == "orange"

    def test_valid_string_critical(self):
        """Test parsing 'critical' priority string."""
        result = parse_priority("critical")

        assert result["priority"] == "critical"
        assert result["level"] == 4
        assert result["valid"] is True
        assert result["color"] == "red"

    def test_valid_integer_levels(self):
        """Test parsing integer priority levels."""
        result = parse_priority(1)
        assert result["priority"] == "low"
        assert result["valid"] is True

        result = parse_priority(4)
        assert result["priority"] == "critical"
        assert result["valid"] is True

    def test_none_uses_default(self):
        """Test None value uses default priority."""
        result = parse_priority(None)

        assert result["priority"] == "medium"
        assert result["valid"] is False

    def test_invalid_string_uses_default(self):
        """Test invalid string uses default priority."""
        result = parse_priority("invalid")

        assert result["priority"] == "medium"
        assert result["valid"] is False

    def test_custom_default(self):
        """Test custom default priority."""
        result = parse_priority(None, default="high")

        assert result["priority"] == "high"
        assert result["level"] == 3

    def test_case_insensitive(self):
        """Test priority parsing is case insensitive."""
        result = parse_priority("HIGH")

        assert result["priority"] == "high"
        assert result["valid"] is True

    def test_whitespace_stripped(self):
        """Test whitespace is stripped from priority."""
        result = parse_priority("  medium  ")

        assert result["priority"] == "medium"
        assert result["valid"] is True

    def test_invalid_integer_uses_default(self):
        """Test invalid integer uses default."""
        result = parse_priority(5)

        assert result["priority"] == "medium"
        assert result["valid"] is False


class TestErrorContext:
    """Tests for ErrorContext class.

    Feature #2: error-handling - Tests for error context manager.
    """

    def test_successful_operation(self):
        """Test context manager with successful operation."""
        with ErrorContext("test_op") as ctx:
            ctx.add_detail("result", "ok")

        assert ctx.success is True
        assert ctx.error is None
        assert ctx.details["result"] == "ok"

    def test_failed_operation(self):
        """Test context manager captures exception."""
        try:
            with ErrorContext("test_op") as ctx:
                raise ValueError("test error")
        except ValueError:
            pass

        assert ctx.success is False
        assert ctx.error_type == "ValueError"
        assert ctx.error_message == "test error"

    def test_context_preserved(self):
        """Test context data is preserved."""
        with ErrorContext("test_op", {"key": "value"}) as ctx:
            pass

        assert ctx.context == {"key": "value"}

    def test_duration_tracked(self):
        """Test operation duration is tracked."""
        import time

        with ErrorContext("test_op") as ctx:
            time.sleep(0.01)

        assert ctx.get_duration_ms() >= 10

    def test_to_dict_format(self):
        """Test to_dict returns correct format."""
        with ErrorContext("test_op", {"x": 1}) as ctx:
            ctx.add_detail("y", 2)

        result = ctx.to_dict()

        assert result["operation"] == "test_op"
        assert result["success"] is True
        assert result["context"] == {"x": 1}
        assert result["details"] == {"y": 2}
        assert "timestamp" in result
        assert "duration_ms" in result


class TestClassifyError:
    """Tests for classify_error function.

    Feature #2: error-handling - Tests for error classification.
    """

    def test_classify_value_error(self):
        """Test ValueError is classified as validation."""
        result = classify_error(ValueError("bad value"))

        assert result["category"] == "validation"
        assert result["severity"] == "low"
        assert result["recoverable"] is True

    def test_classify_connection_error(self):
        """Test ConnectionError is classified as network."""
        result = classify_error(ConnectionError("timeout"))

        assert result["category"] == "network"
        assert result["severity"] == "medium"
        assert result["recoverable"] is True

    def test_classify_file_not_found(self):
        """Test FileNotFoundError is classified as filesystem."""
        result = classify_error(FileNotFoundError("missing"))

        assert result["category"] == "filesystem"
        assert result["severity"] == "medium"

    def test_classify_memory_error(self):
        """Test MemoryError is classified as resource/critical."""
        result = classify_error(MemoryError("out of memory"))

        assert result["category"] == "resource"
        assert result["severity"] == "critical"
        assert result["recoverable"] is False

    def test_classify_database_error_by_message(self):
        """Test database errors classified by message content."""
        result = classify_error(Exception("sqlite database locked"))

        assert result["category"] == "database"
        assert result["severity"] == "high"

    def test_classify_permission_error_by_message(self):
        """Test permission errors classified by message content."""
        result = classify_error(Exception("access denied"))

        assert result["category"] == "permission"

    def test_classify_unknown_error(self):
        """Test unknown errors get default classification."""
        result = classify_error(Exception("something random"))

        assert result["category"] == "unknown"
        assert result["severity"] == "medium"

    def test_user_message_safe(self):
        """Test user messages don't expose internal details."""
        result = classify_error(ValueError("secret password was wrong"))

        assert "password" not in result["user_message"]
        assert result["user_message"] == "Invalid input provided"


class TestFormatErrorResponse:
    """Tests for format_error_response function.

    Feature #2: error-handling - Tests for error response formatting.
    """

    def test_basic_format(self):
        """Test basic error response format."""
        result = format_error_response(ValueError("test"))

        assert result["success"] is False
        assert "error" in result
        assert result["error"]["type"] == "ValueError"
        assert "timestamp" in result

    def test_includes_request_id(self):
        """Test request_id is included when provided."""
        result = format_error_response(ValueError("test"), request_id="abc123")

        assert result["request_id"] == "abc123"

    def test_trace_not_included_by_default(self):
        """Test stack trace not included by default."""
        result = format_error_response(ValueError("test"))

        assert "trace" not in result.get("error", {})

    def test_trace_included_when_requested(self):
        """Test stack trace included when requested."""
        try:
            raise ValueError("test error")
        except ValueError as e:
            result = format_error_response(e, include_trace=True)

        assert "trace" in result["error"]
        assert "detail" in result["error"]

    def test_error_category_included(self):
        """Test error category is included in response."""
        result = format_error_response(ConnectionError("timeout"))

        assert result["error"]["category"] == "network"
        assert "recoverable" in result["error"]


class TestSafeExecute:
    """Tests for safe_execute function.

    Feature #2: error-handling - Tests for safe function execution.
    """

    def test_successful_execution(self):
        """Test successful function execution returns result."""
        result = safe_execute(int, "123")

        assert result == 123

    def test_failed_execution_returns_default(self):
        """Test failed execution returns default value."""
        result = safe_execute(int, "invalid", default=0)

        assert result == 0

    def test_none_default(self):
        """Test default is None when not specified."""
        result = safe_execute(int, "invalid")

        assert result is None

    def test_on_error_callback(self):
        """Test on_error callback is called."""
        errors = []
        safe_execute(int, "invalid", on_error=lambda e: errors.append(e))

        assert len(errors) == 1
        assert isinstance(errors[0], ValueError)

    def test_with_kwargs(self):
        """Test function with keyword arguments."""

        def add(a, b=0):
            return a + b

        result = safe_execute(add, 5, b=3)

        assert result == 8

    def test_division_by_zero(self):
        """Test handling of division by zero."""
        result = safe_execute(lambda x: 10 / x, 0, default=-1)

        assert result == -1


class TestEstimateCompletion:
    """Tests for estimate_completion function.

    E2E Test Feature 1766695304 - Tests for completion time estimation.
    """

    def test_half_complete(self):
        """Test estimation at 50% completion."""
        result = estimate_completion(50, 100, 60.0)

        assert result["percentage"] == 50
        assert result["remaining"] == 50
        assert result["rate"] > 0
        assert result["eta_seconds"] is not None

    def test_complete(self):
        """Test estimation at 100% completion."""
        result = estimate_completion(100, 100, 120.0)

        assert result["percentage"] == 100
        assert result["remaining"] == 0
        assert result["eta_seconds"] == 0 or result["eta_formatted"] == "0s"

    def test_not_started(self):
        """Test estimation with no progress."""
        result = estimate_completion(0, 100, 0)

        assert result["percentage"] == 0
        assert result["remaining"] == 100
        assert result["rate"] == 0
        assert result["eta_formatted"] == "Unknown"

    def test_zero_total(self):
        """Test with zero total items."""
        result = estimate_completion(0, 0, 10.0)

        assert result["percentage"] == 0
        assert result["eta_formatted"] == "N/A"

    def test_eta_seconds_format(self):
        """Test ETA formatted as seconds."""
        result = estimate_completion(90, 100, 90.0)  # 1 item/sec, 10 remaining

        assert "s" in result["eta_formatted"]

    def test_eta_minutes_format(self):
        """Test ETA formatted as minutes."""
        result = estimate_completion(10, 100, 10.0)  # 1 item/sec, 90 remaining

        assert "m" in result["eta_formatted"]

    def test_eta_hours_format(self):
        """Test ETA formatted as hours."""
        result = estimate_completion(1, 10000, 1.0)  # Very slow rate

        assert "h" in result["eta_formatted"]

    def test_rate_calculation(self):
        """Test rate is calculated correctly."""
        result = estimate_completion(60, 100, 30.0)

        assert result["rate"] == 2.0  # 60 items / 30 seconds

    def test_clamps_completed_to_total(self):
        """Test completed is clamped to total."""
        result = estimate_completion(150, 100, 60.0)

        assert result["percentage"] == 100
        assert result["remaining"] == 0

    def test_negative_completed_clamped(self):
        """Test negative completed is clamped to zero."""
        result = estimate_completion(-10, 100, 60.0)

        assert result["percentage"] == 0
        assert result["remaining"] == 100


class TestTruncateString:
    """Tests for truncate_string function.

    E2E Test Feature 1766695630 - Tests for string truncation.
    """

    def test_short_string_unchanged(self):
        """Test short strings are not truncated."""
        result = truncate_string("Hello", max_length=10)
        assert result == "Hello"

    def test_exact_length_unchanged(self):
        """Test strings at exact max_length are unchanged."""
        result = truncate_string("Hello", max_length=5)
        assert result == "Hello"

    def test_long_string_truncated(self):
        """Test long strings are truncated with suffix."""
        result = truncate_string("Hello World", max_length=8)
        assert result == "Hello..."
        assert len(result) == 8

    def test_custom_suffix(self):
        """Test custom suffix is used."""
        result = truncate_string("Hello World", max_length=9, suffix=">")
        assert result == "Hello Wo>"

    def test_empty_suffix(self):
        """Test empty suffix works."""
        result = truncate_string("Hello World", max_length=5, suffix="")
        assert result == "Hello"

    def test_non_string_input(self):
        """Test non-string input is converted."""
        result = truncate_string(12345, max_length=3)
        assert result == "..."

    def test_empty_string(self):
        """Test empty string returns empty."""
        result = truncate_string("", max_length=10)
        assert result == ""

    def test_suffix_longer_than_max(self):
        """Test suffix longer than max_length is handled."""
        result = truncate_string("Hello", max_length=2, suffix="...")
        assert result == ".."
        assert len(result) == 2


class TestMergeDicts:
    """Tests for merge_dicts function.

    E2E Test Feature 1766695896 - Tests for dictionary merging.
    """

    def test_simple_merge(self):
        """Test simple dictionary merge."""
        result = merge_dicts({"a": 1, "b": 2}, {"b": 3, "c": 4})
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_override_takes_precedence(self):
        """Test override values take precedence."""
        result = merge_dicts({"x": "old"}, {"x": "new"})
        assert result["x"] == "new"

    def test_base_unchanged(self):
        """Test base dictionary is not modified."""
        base = {"a": 1}
        merge_dicts(base, {"b": 2})
        assert base == {"a": 1}

    def test_empty_base(self):
        """Test merging with empty base."""
        result = merge_dicts({}, {"a": 1})
        assert result == {"a": 1}

    def test_empty_override(self):
        """Test merging with empty override."""
        result = merge_dicts({"a": 1}, {})
        assert result == {"a": 1}

    def test_shallow_merge_nested(self):
        """Test shallow merge replaces nested dicts."""
        result = merge_dicts({"a": {"x": 1}}, {"a": {"y": 2}}, deep=False)
        assert result == {"a": {"y": 2}}

    def test_deep_merge_nested(self):
        """Test deep merge combines nested dicts."""
        result = merge_dicts({"a": {"x": 1}}, {"a": {"y": 2}}, deep=True)
        assert result == {"a": {"x": 1, "y": 2}}

    def test_deep_merge_multiple_levels(self):
        """Test deep merge works with multiple nesting levels."""
        base = {"a": {"b": {"c": 1}}}
        override = {"a": {"b": {"d": 2}}}
        result = merge_dicts(base, override, deep=True)
        assert result == {"a": {"b": {"c": 1, "d": 2}}}

    def test_deep_merge_non_dict_override(self):
        """Test deep merge with non-dict override replaces."""
        result = merge_dicts({"a": {"x": 1}}, {"a": "string"}, deep=True)
        assert result == {"a": "string"}


class TestChunkList:
    """Tests for chunk_list function."""

    def test_basic_chunking(self):
        """Test basic list chunking."""
        result = chunk_list([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]

    def test_exact_division(self):
        """Test chunking when list divides evenly."""
        result = chunk_list([1, 2, 3, 4], 2)
        assert result == [[1, 2], [3, 4]]

    def test_chunk_size_larger_than_list(self):
        """Test chunk size larger than list."""
        result = chunk_list([1, 2, 3], 10)
        assert result == [[1, 2, 3]]

    def test_chunk_size_equals_list(self):
        """Test chunk size equals list length."""
        result = chunk_list([1, 2, 3], 3)
        assert result == [[1, 2, 3]]

    def test_chunk_size_one(self):
        """Test chunk size of 1."""
        result = chunk_list([1, 2, 3], 1)
        assert result == [[1], [2], [3]]

    def test_empty_list(self):
        """Test chunking empty list."""
        result = chunk_list([], 5)
        assert result == []

    def test_string_list(self):
        """Test chunking list of strings."""
        result = chunk_list(["a", "b", "c", "d"], 2)
        assert result == [["a", "b"], ["c", "d"]]

    def test_invalid_chunk_size_zero(self):
        """Test that zero chunk size raises ValueError."""
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            chunk_list([1, 2, 3], 0)

    def test_invalid_chunk_size_negative(self):
        """Test that negative chunk size raises ValueError."""
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            chunk_list([1, 2, 3], -1)


class TestDedupeList:
    """Tests for dedupe_list function."""

    def test_basic_deduplication(self):
        """Test basic duplicate removal."""
        result = dedupe_list([1, 2, 2, 3, 1, 4])
        assert result == [1, 2, 3, 4]

    def test_preserves_order(self):
        """Test that original order is preserved."""
        result = dedupe_list([3, 1, 2, 1, 3])
        assert result == [3, 1, 2]

    def test_no_duplicates(self):
        """Test list with no duplicates."""
        result = dedupe_list([1, 2, 3])
        assert result == [1, 2, 3]

    def test_all_duplicates(self):
        """Test list with all same values."""
        result = dedupe_list([5, 5, 5, 5])
        assert result == [5]

    def test_empty_list(self):
        """Test empty list."""
        result = dedupe_list([])
        assert result == []

    def test_strings(self):
        """Test deduplication of strings."""
        result = dedupe_list(["a", "b", "a", "c", "b"])
        assert result == ["a", "b", "c"]

    def test_with_key_function(self):
        """Test deduplication with key function."""
        items = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}, {"id": 1, "name": "c"}]
        result = dedupe_list(items, key=lambda x: x["id"])
        assert result == [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]

    def test_key_function_with_tuples(self):
        """Test key function extracting tuple element."""
        items = [(1, "a"), (2, "b"), (1, "c")]
        result = dedupe_list(items, key=lambda x: x[0])
        assert result == [(1, "a"), (2, "b")]

    def test_single_element(self):
        """Test single element list."""
        result = dedupe_list([42])
        assert result == [42]


class TestClampValue:
    """Tests for clamp_value function."""

    def test_value_within_range(self):
        """Test value already within range."""
        assert clamp_value(5, 0, 10) == 5

    def test_value_below_min(self):
        """Test value below minimum."""
        assert clamp_value(-5, 0, 10) == 0

    def test_value_above_max(self):
        """Test value above maximum."""
        assert clamp_value(15, 0, 10) == 10

    def test_value_at_min(self):
        """Test value exactly at minimum."""
        assert clamp_value(0, 0, 10) == 0

    def test_value_at_max(self):
        """Test value exactly at maximum."""
        assert clamp_value(10, 0, 10) == 10

    def test_negative_range(self):
        """Test with negative range."""
        assert clamp_value(0, -10, -5) == -5

    def test_float_values(self):
        """Test with float values."""
        assert clamp_value(3.5, 0.0, 5.0) == 3.5

    def test_invalid_range(self):
        """Test that invalid range raises ValueError."""
        with pytest.raises(ValueError, match="min_val cannot be greater than max_val"):
            clamp_value(5, 10, 0)

    def test_equal_min_max(self):
        """Test when min equals max."""
        assert clamp_value(5, 3, 3) == 3


class TestGroupBy:
    """Tests for group_by function."""

    def test_basic_grouping(self):
        """Test basic grouping by key."""
        items = [{"type": "a", "val": 1}, {"type": "b", "val": 2}, {"type": "a", "val": 3}]
        result = group_by(items, lambda x: x["type"])
        assert result == {
            "a": [{"type": "a", "val": 1}, {"type": "a", "val": 3}],
            "b": [{"type": "b", "val": 2}],
        }

    def test_single_group(self):
        """Test when all items in one group."""
        items = [{"type": "a", "val": 1}, {"type": "a", "val": 2}]
        result = group_by(items, lambda x: x["type"])
        assert result == {"a": [{"type": "a", "val": 1}, {"type": "a", "val": 2}]}

    def test_each_item_own_group(self):
        """Test when each item is its own group."""
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = group_by(items, lambda x: x["id"])
        assert result == {1: [{"id": 1}], 2: [{"id": 2}], 3: [{"id": 3}]}

    def test_empty_list(self):
        """Test grouping empty list."""
        result = group_by([], lambda x: x)
        assert result == {}

    def test_group_by_length(self):
        """Test grouping strings by length."""
        items = ["a", "bb", "c", "dd", "eee"]
        result = group_by(items, len)
        assert result == {1: ["a", "c"], 2: ["bb", "dd"], 3: ["eee"]}

    def test_group_tuples(self):
        """Test grouping tuples by first element."""
        items = [(1, "a"), (2, "b"), (1, "c")]
        result = group_by(items, lambda x: x[0])
        assert result == {1: [(1, "a"), (1, "c")], 2: [(2, "b")]}

    def test_preserves_order(self):
        """Test that item order is preserved within groups."""
        items = [{"g": "x", "v": 1}, {"g": "x", "v": 2}, {"g": "x", "v": 3}]
        result = group_by(items, lambda x: x["g"])
        assert result["x"][0]["v"] == 1
        assert result["x"][1]["v"] == 2
        assert result["x"][2]["v"] == 3


class TestFlattenList:
    """Tests for flatten_list function."""

    def test_basic_flatten(self):
        """Test basic one-level flattening."""
        result = flatten_list([[1, 2], [3, 4]])
        assert result == [1, 2, 3, 4]

    def test_mixed_elements(self):
        """Test flattening with mixed nested and non-nested."""
        result = flatten_list([1, [2, 3], 4])
        assert result == [1, 2, 3, 4]

    def test_empty_list(self):
        """Test flattening empty list."""
        result = flatten_list([])
        assert result == []

    def test_empty_sublists(self):
        """Test flattening with empty sublists."""
        result = flatten_list([[], [1], []])
        assert result == [1]

    def test_depth_two(self):
        """Test flattening with depth 2."""
        result = flatten_list([[[1, 2]], [[3, 4]]], depth=2)
        assert result == [1, 2, 3, 4]

    def test_depth_zero(self):
        """Test depth 0 returns original."""
        nested = [[1, 2], [3, 4]]
        result = flatten_list(nested, depth=0)
        assert result == [[1, 2], [3, 4]]

    def test_unlimited_depth(self):
        """Test unlimited depth flattening."""
        result = flatten_list([[[[1]]]], depth=-1)
        assert result == [1]

    def test_strings_not_flattened(self):
        """Test that strings are not flattened."""
        result = flatten_list([["abc"], ["def"]])
        assert result == ["abc", "def"]

    def test_single_element(self):
        """Test single element list."""
        result = flatten_list([[1]])
        assert result == [1]


class TestSafeGet:
    """Tests for safe_get function."""

    def test_single_key(self):
        """Test getting single key."""
        assert safe_get({"a": 1}, "a") == 1

    def test_nested_keys(self):
        """Test getting nested keys."""
        data = {"a": {"b": {"c": 42}}}
        assert safe_get(data, "a", "b", "c") == 42

    def test_missing_key_returns_default(self):
        """Test missing key returns default."""
        assert safe_get({"a": 1}, "b") is None

    def test_custom_default(self):
        """Test custom default value."""
        assert safe_get({"a": 1}, "b", default="missing") == "missing"

    def test_partial_path_missing(self):
        """Test partial path missing returns default."""
        data = {"a": {"b": 1}}
        assert safe_get(data, "a", "c", "d", default=-1) == -1

    def test_empty_dict(self):
        """Test empty dictionary."""
        assert safe_get({}, "a", default="empty") == "empty"

    def test_no_keys(self):
        """Test no keys returns the dict itself."""
        data = {"a": 1}
        assert safe_get(data) == {"a": 1}

    def test_non_dict_intermediate(self):
        """Test non-dict intermediate value."""
        data = {"a": "string"}
        assert safe_get(data, "a", "b", default="fail") == "fail"

    def test_none_value(self):
        """Test None value is returned correctly."""
        data = {"a": {"b": None}}
        assert safe_get(data, "a", "b") is None
