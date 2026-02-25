"""
Data-Driven Testing Framework

Tests are defined in data files, NOT in code.
The test runner executes tests based on data instructions.

Test Data Structure:
- test_suites/: Directory containing test suite definitions
- Each suite is a JSON/YAML file with test cases
- Test cases specify steps, assertions, and expected results
"""

from .loader import load_all_suites, load_test_suite
from .models import TestCase, TestResult, TestStep, TestSuite
from .runner import TestRunner

__all__ = [
    "TestRunner",
    "TestSuite",
    "TestCase",
    "TestStep",
    "TestResult",
    "load_test_suite",
    "load_all_suites",
]
