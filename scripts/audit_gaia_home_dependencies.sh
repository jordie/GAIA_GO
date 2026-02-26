#!/bin/bash

################################################################################
# GAIA_HOME Dependency Audit Script
#
# Scans the codebase for GAIA_HOME references and generates a report
# identifying all applications and services that depend on GAIA_HOME.
#
# Usage: ./audit_gaia_home_dependencies.sh [output_file]
################################################################################

set -o pipefail

# Configuration
OUTPUT_FILE="${1:gaia_home_audit_report.txt}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
SCAN_DIRS=(
    "."
    "../"
    "../.."
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;36m'
NC='\033[0m' # No Color

# Counters
FILES_SCANNED=0
GAIA_HOME_REFS=0
IMPORT_STATEMENTS=0
HTTP_CALLS=0
CRITICAL_REFS=0

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}GAIA_HOME Dependency Audit${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Starting scan at ${TIMESTAMP}"
echo "Output will be written to: ${OUTPUT_FILE}"
echo ""

# Initialize output file
{
    echo "GAIA_HOME Dependency Audit Report"
    echo "Generated: ${TIMESTAMP}"
    echo "========================================"
    echo ""
} > "${OUTPUT_FILE}"

# Function to search for GAIA_HOME references
search_gaia_home_references() {
    local search_dir="$1"
    local file_type="$2"
    local description="$3"

    echo -e "${YELLOW}Searching for ${description}...${NC}"

    local pattern=""
    case "${file_type}" in
        "python")
            pattern="gaia.*home\|GAIA_HOME\|gaia_home\|from gaia"
            ;;
        "go")
            pattern="gaia.*home\|GAIA_HOME\|gaia_home\|github.com/gaia"
            ;;
        "config")
            pattern="gaia.*home\|GAIA_HOME\|gaia_home\|gaia-home"
            ;;
        "all")
            pattern="gaia.*home\|GAIA_HOME\|gaia_home\|gaia-home\|gaia.home"
            ;;
    esac

    # Search for references
    local matches=$(grep -r --include="*${file_type}" -i "${pattern}" "${search_dir}" 2>/dev/null | grep -v "Binary file" || true)

    if [ -n "${matches}" ]; then
        echo -e "${RED}Found ${description}:${NC}"
        echo "${matches}" | while IFS= read -r line; do
            echo "  ${line}"
            GAIA_HOME_REFS=$((GAIA_HOME_REFS + 1))
        done
        echo ""
    fi

    return 0
}

# Function to analyze Python files
analyze_python_files() {
    echo -e "${BLUE}Analyzing Python files...${NC}"

    {
        echo "=== Python Files with GAIA_HOME References ==="
        echo ""
    } >> "${OUTPUT_FILE}"

    find . -name "*.py" -type f 2>/dev/null | while read -r file; do
        FILES_SCANNED=$((FILES_SCANNED + 1))

        # Check for GAIA_HOME imports
        if grep -q -i "from gaia_home\|import gaia_home\|from.*gaia.*home" "${file}" 2>/dev/null; then
            echo "${file}"
            {
                echo "File: ${file}"
                grep -n -i "gaia_home\|gaia.*home" "${file}" 2>/dev/null || true
                echo ""
            } >> "${OUTPUT_FILE}"
            IMPORT_STATEMENTS=$((IMPORT_STATEMENTS + 1))
        fi

        # Check for HTTP calls to GAIA_HOME
        if grep -q -i "gaia.home\|gaia-home\|gaia_home.*:5000\|gaia.example.com" "${file}" 2>/dev/null; then
            {
                echo "HTTP References in: ${file}"
                grep -n -i "gaia.home\|gaia-home" "${file}" 2>/dev/null || true
                echo ""
            } >> "${OUTPUT_FILE}"
            HTTP_CALLS=$((HTTP_CALLS + 1))
        fi

        # Check for critical references (hardcoded URLs)
        if grep -q -E "http[s]?://.*gaia.*home|http[s]?://.*gaia_home" "${file}" 2>/dev/null; then
            CRITICAL_REFS=$((CRITICAL_REFS + 1))
            echo -e "${RED}CRITICAL: Hardcoded GAIA_HOME URL in ${file}${NC}"
        fi
    done
}

# Function to analyze Go files
analyze_go_files() {
    echo -e "${BLUE}Analyzing Go files...${NC}"

    {
        echo "=== Go Files with GAIA_HOME References ==="
        echo ""
    } >> "${OUTPUT_FILE}"

    find . -name "*.go" -type f 2>/dev/null | while read -r file; do
        FILES_SCANNED=$((FILES_SCANNED + 1))

        # Check for GAIA_HOME references
        if grep -q -i "gaia.*home\|gaia_home" "${file}" 2>/dev/null; then
            {
                echo "File: ${file}"
                grep -n -i "gaia.*home\|gaia_home" "${file}" 2>/dev/null || true
                echo ""
            } >> "${OUTPUT_FILE}"
        fi
    done
}

# Function to analyze configuration files
analyze_config_files() {
    echo -e "${BLUE}Analyzing configuration files...${NC}"

    {
        echo "=== Configuration Files with GAIA_HOME References ==="
        echo ""
    } >> "${OUTPUT_FILE}"

    find . \( -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name ".env*" -o -name "*.conf" \) -type f 2>/dev/null | while read -r file; do
        FILES_SCANNED=$((FILES_SCANNED + 1))

        if grep -q -i "gaia.*home\|GAIA_HOME\|gaia_home" "${file}" 2>/dev/null; then
            {
                echo "File: ${file}"
                grep -n -i "gaia.*home\|GAIA_HOME\|gaia_home" "${file}" 2>/dev/null || true
                echo ""
            } >> "${OUTPUT_FILE}"
        fi
    done
}

# Function to generate dependency graph
generate_dependency_graph() {
    echo -e "${BLUE}Generating dependency graph...${NC}"

    {
        echo "=== Dependency Graph ==="
        echo ""
        echo "Applications → GAIA_HOME"
        echo ""
    } >> "${OUTPUT_FILE}"

    # Find applications/services that depend on GAIA_HOME
    grep -r "import.*gaia_home\|from gaia_home" . --include="*.py" 2>/dev/null | cut -d: -f1 | sort | uniq | while read -r file; do
        app_name=$(dirname "${file}" | sed 's|./||' | cut -d/ -f1)
        echo "  ${app_name} → GAIA_HOME" >> "${OUTPUT_FILE}"
    done

    echo "" >> "${OUTPUT_FILE}"
}

# Function to generate migration recommendations
generate_recommendations() {
    echo -e "${BLUE}Generating migration recommendations...${NC}"

    {
        echo "=== Migration Recommendations ==="
        echo ""
        echo "Based on the audit, here are recommended migration actions:"
        echo ""

        if [ ${CRITICAL_REFS} -gt 0 ]; then
            echo "CRITICAL (Migrate Immediately):"
            echo "- ${CRITICAL_REFS} files have hardcoded GAIA_HOME URLs"
            echo "- Action: Replace with GAIA_GO URLs, use configuration instead"
            echo ""
        fi

        if [ ${IMPORT_STATEMENTS} -gt 0 ]; then
            echo "HIGH PRIORITY:"
            echo "- ${IMPORT_STATEMENTS} files import GAIA_HOME modules"
            echo "- Action: Update to use GAIA_GO client library"
            echo ""
        fi

        if [ ${HTTP_CALLS} -gt 0 ]; then
            echo "MEDIUM PRIORITY:"
            echo "- ${HTTP_CALLS} files make direct HTTP calls to GAIA_HOME"
            echo "- Action: Update to use GAIA_GO endpoints"
            echo ""
        fi

        echo "Migration Timeline Suggestion:"
        case $((CRITICAL_REFS + IMPORT_STATEMENTS)) in
            0)
                echo "- Timeline: 1-2 weeks (low impact)"
                echo "- Complexity: Low"
                ;;
            1-5)
                echo "- Timeline: 2-4 weeks (medium impact)"
                echo "- Complexity: Medium"
                ;;
            *)
                echo "- Timeline: 4-8 weeks (high impact)"
                echo "- Complexity: High"
                ;;
        esac

        echo ""
    } >> "${OUTPUT_FILE}"
}

# Function to generate summary
generate_summary() {
    echo -e "${BLUE}Generating summary...${NC}"

    {
        echo "=== SUMMARY ==="
        echo ""
        echo "Audit Statistics:"
        echo "  Files Scanned: ${FILES_SCANNED}"
        echo "  GAIA_HOME References: ${GAIA_HOME_REFS}"
        echo "  Import Statements: ${IMPORT_STATEMENTS}"
        echo "  HTTP Calls: ${HTTP_CALLS}"
        echo "  Critical References: ${CRITICAL_REFS}"
        echo ""
        echo "Risk Assessment:"

        if [ ${CRITICAL_REFS} -eq 0 ] && [ ${IMPORT_STATEMENTS} -eq 0 ]; then
            echo "  ✓ LOW RISK - Few hardcoded dependencies"
            echo "  ✓ Migration should be straightforward"
        elif [ ${CRITICAL_REFS} -gt 0 ]; then
            echo "  ✗ HIGH RISK - Critical hardcoded dependencies found"
            echo "  ✗ Immediate action required"
        else
            echo "  ! MEDIUM RISK - Some code dependencies exist"
            echo "  ! Plan migration carefully"
        fi

        echo ""
        echo "Recommendation: Review all flagged files and plan migration accordingly."
        echo ""
        echo "Deadline: August 25, 2026"
        echo ""
        echo "For more information, see: DEPRECATION_NOTICE.md"
        echo "For migration help, see: docs/GAIA_HOME_MIGRATION_GUIDE.md"
        echo ""
    } >> "${OUTPUT_FILE}"
}

# Main execution
main() {
    # Perform analysis
    analyze_python_files
    analyze_go_files
    analyze_config_files

    # Generate report sections
    generate_dependency_graph
    generate_recommendations
    generate_summary

    echo ""
    echo -e "${GREEN}Audit complete!${NC}"
    echo ""
    echo "Report written to: ${OUTPUT_FILE}"
    echo ""
    echo "Summary:"
    echo "  Files Scanned: ${FILES_SCANNED}"
    echo "  GAIA_HOME References: ${GAIA_HOME_REFS}"
    echo "  Critical References: ${CRITICAL_REFS}"
    echo ""

    if [ ${CRITICAL_REFS} -gt 0 ]; then
        echo -e "${RED}⚠ WARNING: ${CRITICAL_REFS} critical references found!${NC}"
        echo -e "${RED}Action required to migrate applications.${NC}"
    else
        echo -e "${GREEN}✓ No critical references found.${NC}"
    fi

    echo ""
    echo "Next steps:"
    echo "1. Review the audit report: ${OUTPUT_FILE}"
    echo "2. Prioritize files for migration"
    echo "3. Follow the migration guide: docs/GAIA_HOME_MIGRATION_GUIDE.md"
    echo "4. Test migrations in staging environment"
    echo "5. Plan production cutover before August 25, 2026"
}

# Run main function
main

exit 0
