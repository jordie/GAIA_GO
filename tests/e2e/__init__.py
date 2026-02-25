"""
Architect Dashboard E2E Test Suite

End-to-end browser tests using Playwright.

Structure:
    conftest.py      - Fixtures and configuration
    pages/           - Page Object Models
    test_auth.py     - Authentication tests
    test_dashboard.py - Dashboard UI tests
    test_workflows.py - Complete workflow tests

Running Tests:
    # Install dependencies
    pip install -r tests/e2e/requirements.txt
    playwright install

    # Run all tests
    pytest tests/e2e/

    # Run with visible browser
    pytest tests/e2e/ --headed

    # Run specific browser
    pytest tests/e2e/ --browser firefox

    # Run smoke tests only
    pytest tests/e2e/ -m smoke

    # Generate HTML report
    pytest tests/e2e/ --html=report.html

    # Or use the run script
    ./tests/e2e/run_tests.sh --help
"""
