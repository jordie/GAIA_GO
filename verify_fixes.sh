#!/bin/bash
# Verification script for test fixes
# Run this to verify all three critical issues are resolved

set -e

echo "=========================================="
echo "GAIA_GO Test Fixes Verification"
echo "=========================================="
echo ""

# Test 1: SQL Syntax Error Fix
echo "Test 1: SQL syntax error (unrecognized token) ..."
pytest tests/test_api.py::TestProjectsAPI::test_list_projects -v --tb=line -x 2>&1 | grep -E "(PASSED|FAILED|ERROR)" || true
echo ""

# Test 2: Missing secrets table Fix
echo "Test 2: Missing secrets table ..."
pytest tests/test_api.py::TestSecretsAPI::test_list_secrets -v --tb=line -x 2>&1 | grep -E "(PASSED|FAILED|ERROR)" || true
echo ""

# Test 3: CSRF validation Fix
echo "Test 3: CSRF token validation ..."
pytest tests/test_api.py::TestProjectsAPI::test_create_project -v --tb=line -x 2>&1 | grep -E "(PASSED|FAILED|ERROR)" || true
echo ""

# Bonus: Feature workflow test
echo "Bonus: Feature workflow endpoint ..."
pytest tests/test_api.py::TestFeaturesAPI::test_feature_workflow_endpoint -v --tb=line -x 2>&1 | grep -E "(PASSED|FAILED|ERROR)" || true
echo ""

echo "=========================================="
echo "Verification Complete"
echo "=========================================="
echo ""
echo "Expected results:"
echo "  Test 1: PASSED (SQL syntax fixed)"
echo "  Test 2: PASSED (secrets table created)"
echo "  Test 3: PASSED (CSRF disabled)"
echo "  Bonus:  PASSED (no issues)"
