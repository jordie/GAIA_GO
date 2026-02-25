"""
Test Data Loader

Loads test suites from data files (JSON/YAML).
Tests are defined in data, NOT in code.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from .models import TestCase, TestSuite

logger = logging.getLogger(__name__)

# Default test data directory
TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"


def load_test_suite(file_path: str) -> Optional[TestSuite]:
    """
    Load a test suite from a data file.

    Args:
        file_path: Path to JSON or YAML file

    Returns:
        TestSuite or None if loading fails
    """
    path = Path(file_path)

    if not path.exists():
        logger.error(f"Test file not found: {file_path}")
        return None

    try:
        with open(path) as f:
            if path.suffix in [".yaml", ".yml"]:
                try:
                    import yaml

                    data = yaml.safe_load(f)
                except ImportError:
                    logger.error("PyYAML not installed. Use JSON format.")
                    return None
            else:
                data = json.load(f)

        return TestSuite.from_dict(data)

    except Exception as e:
        logger.error(f"Error loading test suite from {file_path}: {e}")
        return None


def load_all_suites(directory: str = None) -> List[TestSuite]:
    """
    Load all test suites from a directory.

    Args:
        directory: Path to test data directory

    Returns:
        List of TestSuite objects
    """
    dir_path = Path(directory) if directory else TEST_DATA_DIR

    if not dir_path.exists():
        logger.warning(f"Test data directory not found: {dir_path}")
        return []

    suites = []
    for file_path in dir_path.glob("**/*.json"):
        suite = load_test_suite(str(file_path))
        if suite:
            suites.append(suite)

    for file_path in dir_path.glob("**/*.yaml"):
        suite = load_test_suite(str(file_path))
        if suite:
            suites.append(suite)

    for file_path in dir_path.glob("**/*.yml"):
        suite = load_test_suite(str(file_path))
        if suite:
            suites.append(suite)

    return suites


def load_suites_by_tag(tag: str, directory: str = None) -> List[TestSuite]:
    """Load test suites that have a specific tag."""
    all_suites = load_all_suites(directory)
    return [s for s in all_suites if tag in s.tags]


def load_suites_for_service(service_id: str, directory: str = None) -> List[TestSuite]:
    """Load test suites for a specific service."""
    all_suites = load_all_suites(directory)
    return [s for s in all_suites if s.target_service == service_id]


def validate_test_suite(data: Dict) -> List[str]:
    """
    Validate a test suite data structure.

    Returns list of validation errors.
    """
    errors = []

    if "id" not in data:
        errors.append("Missing required field: id")
    if "name" not in data:
        errors.append("Missing required field: name")

    for i, tc in enumerate(data.get("test_cases", [])):
        if "id" not in tc:
            errors.append(f"test_cases[{i}]: Missing required field: id")
        if "name" not in tc:
            errors.append(f"test_cases[{i}]: Missing required field: name")

        for j, step in enumerate(tc.get("steps", [])):
            if "type" not in step:
                errors.append(f"test_cases[{i}].steps[{j}]: Missing required field: type")

    return errors
