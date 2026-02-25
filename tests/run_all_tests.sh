#!/bin/bash
# Run all LLM provider tests with comprehensive reporting

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TESTS_DIR="$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}LLM PROVIDER COMPREHENSIVE TEST SUITE${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}\n"

# Test files
echo -e "${YELLOW}📋 Test Configuration:${NC}"
echo "  Project Directory: $PROJECT_DIR"
echo "  Tests Directory: $TESTS_DIR"
echo ""

# Install test dependencies
echo -e "${YELLOW}📦 Checking dependencies...${NC}"
pip install -q pytest pytest-cov 2>/dev/null || echo "  ⚠️  Some packages may already be installed"
echo ""

# Run unit tests
echo -e "${YELLOW}🧪 UNIT TESTS${NC}"
echo "─────────────────────────────────────────────────────────────────"
python3 -m pytest "$TESTS_DIR/test_llm_providers_complete.py::TestProviderInitialization" -v --tb=short 2>&1 || true
python3 -m pytest "$TESTS_DIR/test_llm_providers_complete.py::TestCostCalculation" -v --tb=short 2>&1 || true
python3 -m pytest "$TESTS_DIR/test_llm_providers_complete.py::TestTokenCounting" -v --tb=short 2>&1 || true
python3 -m pytest "$TESTS_DIR/test_llm_providers_complete.py::TestProviderTypeEnum" -v --tb=short 2>&1 || true
echo ""

# Run integration tests
echo -e "${YELLOW}🔗 INTEGRATION TESTS${NC}"
echo "─────────────────────────────────────────────────────────────────"
python3 -m pytest "$TESTS_DIR/test_llm_providers_complete.py::TestUnifiedLLMClient" -v --tb=short 2>&1 || true
python3 -m pytest "$TESTS_DIR/test_llm_providers_complete.py::TestProviderMetrics" -v --tb=short 2>&1 || true
python3 -m pytest "$TESTS_DIR/test_llm_providers_complete.py::TestLLMResponseFormat" -v --tb=short 2>&1 || true
echo ""

# Run end-to-end tests
echo -e "${YELLOW}🚀 END-TO-END TESTS${NC}"
echo "─────────────────────────────────────────────────────────────────"
python3 -m pytest "$TESTS_DIR/test_llm_providers_complete.py::TestSystemIntegration" -v --tb=short 2>&1 || true
python3 -m pytest "$TESTS_DIR/test_llm_providers_complete.py::TestProviderConfiguration" -v --tb=short 2>&1 || true
python3 -m pytest "$TESTS_DIR/test_llm_providers_complete.py::TestProviderComparison" -v --tb=short 2>&1 || true
python3 -m pytest "$TESTS_DIR/test_llm_providers_complete.py::TestAPICompatibility" -v --tb=short 2>&1 || true
echo ""

# Run all tests with coverage
echo -e "${YELLOW}📊 COMPLETE TEST RUN WITH COVERAGE${NC}"
echo "─────────────────────────────────────────────────────────────────"
python3 -m pytest "$TESTS_DIR/test_llm_providers_complete.py" -v --cov=services.llm_provider --cov-report=term-missing 2>&1 | tee test_results.txt

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Test Suite Complete${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}\n"

# Summary
if grep -q "FAILED" test_results.txt; then
    echo -e "${RED}❌ Some tests failed. Review output above.${NC}"
    exit 1
else
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
fi
