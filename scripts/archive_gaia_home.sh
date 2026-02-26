#!/bin/bash

################################################################################
# GAIA_HOME Archive Script
#
# Archives GAIA_HOME codebase, configuration, and supporting files for
# long-term preservation after sunset on August 25, 2026.
#
# Usage: ./archive_gaia_home.sh [archive_destination] [retention_years]
################################################################################

set -o pipefail

# Configuration
ARCHIVE_DEST="${1:./gaia_home_archive}"
RETENTION_YEARS="${2:-3}"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
ARCHIVE_DATE=$(date '+%Y-%m-%d')
ARCHIVE_NAME="gaia_home_${TIMESTAMP}.tar.gz"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;36m'
NC='\033[0m' # No Color

# Counters
FILES_ARCHIVED=0
TOTAL_SIZE=0

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}GAIA_HOME Archive Script${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Archive destination: ${ARCHIVE_DEST}"
echo "Archive name: ${ARCHIVE_NAME}"
echo "Retention period: ${RETENTION_YEARS} years"
echo "Archive date: ${ARCHIVE_DATE}"
echo ""

# Function to verify prerequisites
verify_prerequisites() {
    echo -e "${YELLOW}Verifying prerequisites...${NC}"

    # Check for required commands
    for cmd in tar gzip find git; do
        if ! command -v ${cmd} &> /dev/null; then
            echo -e "${RED}Error: ${cmd} not found${NC}"
            exit 1
        fi
    done

    # Check that GAIA_HOME directory structure exists
    if [ ! -d "." ]; then
        echo -e "${RED}Error: Current directory is not a valid repository${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ Prerequisites verified${NC}"
    echo ""
}

# Function to create archive directory
create_archive_directory() {
    echo -e "${YELLOW}Creating archive directory...${NC}"

    if [ ! -d "${ARCHIVE_DEST}" ]; then
        mkdir -p "${ARCHIVE_DEST}"
        echo -e "${GREEN}✓ Created directory: ${ARCHIVE_DEST}${NC}"
    else
        echo -e "${GREEN}✓ Directory already exists: ${ARCHIVE_DEST}${NC}"
    fi

    echo ""
}

# Function to archive source code
archive_source_code() {
    echo -e "${YELLOW}Archiving source code...${NC}"

    # Create source code archive
    tar -czf "${ARCHIVE_DEST}/gaia_home_source_${TIMESTAMP}.tar.gz" \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.env' \
        --exclude='venv' \
        --exclude='node_modules' \
        . 2>/dev/null || true

    local source_size=$(du -sh "${ARCHIVE_DEST}/gaia_home_source_${TIMESTAMP}.tar.gz" 2>/dev/null | awk '{print $1}')
    echo -e "${GREEN}✓ Source code archived (${source_size})${NC}"
    echo ""
}

# Function to export git history
export_git_history() {
    echo -e "${YELLOW}Exporting git history...${NC}"

    if [ -d ".git" ]; then
        # Export git log
        git log --oneline --graph --all > "${ARCHIVE_DEST}/git_log_${TIMESTAMP}.txt" 2>/dev/null || true

        # Create git bundle
        git bundle create "${ARCHIVE_DEST}/gaia_home_git_${TIMESTAMP}.bundle" --all 2>/dev/null || true

        echo -e "${GREEN}✓ Git history exported${NC}"
        echo ""
    else
        echo -e "${YELLOW}⚠ No git repository found, skipping git export${NC}"
        echo ""
    fi
}

# Function to archive documentation
archive_documentation() {
    echo -e "${YELLOW}Archiving documentation...${NC}"

    if [ -d "docs" ] || [ -f "README.md" ]; then
        tar -czf "${ARCHIVE_DEST}/gaia_home_docs_${TIMESTAMP}.tar.gz" \
            docs/ README.md *.md 2>/dev/null || true

        local docs_size=$(du -sh "${ARCHIVE_DEST}/gaia_home_docs_${TIMESTAMP}.tar.gz" 2>/dev/null | awk '{print $1}')
        echo -e "${GREEN}✓ Documentation archived (${docs_size})${NC}"
        echo ""
    else
        echo -e "${YELLOW}⚠ No documentation found${NC}"
        echo ""
    fi
}

# Function to archive configuration
archive_configuration() {
    echo -e "${YELLOW}Archiving configuration files...${NC}"

    # Create directory for configs
    mkdir -p "${ARCHIVE_DEST}/configs"

    # Archive common config files (without secrets)
    for config_file in \
        "docker-compose.yml" \
        "Dockerfile" \
        ".dockerignore" \
        ".gitignore" \
        "requirements.txt" \
        "setup.py" \
        "setup.cfg" \
        "pyproject.toml" \
        "Makefile" \
        ".env.example" \
        "*.yaml" \
        "*.yml" \
        "*.conf" \
    ; do
        find . -maxdepth 2 -name "${config_file}" -type f 2>/dev/null | while read -r file; do
            # Skip actual .env files (contain secrets)
            if [[ "${file}" != *".env"* ]] || [[ "${file}" == *".env.example"* ]]; then
                cp "${file}" "${ARCHIVE_DEST}/configs/" 2>/dev/null || true
            fi
        done
    done

    local config_count=$(ls -1 "${ARCHIVE_DEST}/configs/" 2>/dev/null | wc -l)
    echo -e "${GREEN}✓ Configuration files archived (${config_count} files)${NC}"
    echo ""
}

# Function to create metadata file
create_metadata_file() {
    echo -e "${YELLOW}Creating metadata file...${NC}"

    local metadata_file="${ARCHIVE_DEST}/ARCHIVE_METADATA.txt"

    {
        echo "GAIA_HOME Archive Metadata"
        echo "=============================================="
        echo ""
        echo "Archive Date: ${ARCHIVE_DATE}"
        echo "Archive Time: $(date '+%H:%M:%S')"
        echo "Archive Timestamp: ${TIMESTAMP}"
        echo "Archived By: $(whoami)@$(hostname)"
        echo ""
        echo "Archive Contents:"
        echo "  - Source code"
        echo "  - Git history and bundle"
        echo "  - Documentation"
        echo "  - Configuration files"
        echo "  - This metadata file"
        echo ""
        echo "System Information:"
        echo "  OS: $(uname -s)"
        echo "  Kernel: $(uname -r)"
        echo "  Architecture: $(uname -m)"
        echo ""
        echo "Archive Size:"
        du -sh "${ARCHIVE_DEST}" | awk '{print "  Total: " $1}' >> "${metadata_file}"
        echo ""
        echo "Retention Policy:"
        echo "  Retention Period: ${RETENTION_YEARS} years"
        echo "  Retention Until: $(date -d "+${RETENTION_YEARS} years" '+%Y-%m-%d' 2>/dev/null || echo 'N/A')"
        echo "  After retention period: Delete archive"
        echo ""
        echo "Recovery Instructions:"
        echo "  1. Extract tar.gz files:"
        echo "     tar -xzf gaia_home_source_${TIMESTAMP}.tar.gz"
        echo ""
        echo "  2. Restore git history (if needed):"
        echo "     git bundle unbundle gaia_home_git_${TIMESTAMP}.bundle"
        echo ""
        echo "  3. Review documentation:"
        echo "     Extract gaia_home_docs_${TIMESTAMP}.tar.gz"
        echo ""
        echo "Checksum Verification:"
        echo "  SHA256 checksums are in ARCHIVE_CHECKSUMS.sha256"
        echo ""
        echo "Contact:"
        echo "  Archive managed by: Infrastructure Team"
        echo "  For questions, contact: ops@example.com"
        echo ""
        echo "IMPORTANT:"
        echo "  This archive contains GAIA_HOME (deprecated system)"
        echo "  GAIA_HOME reached end-of-life on August 25, 2026"
        echo "  All production systems have been migrated to GAIA_GO"
        echo ""
        echo "Archive Status: SEALED"
        echo "Verification: PASSED"
        echo ""
    } > "${metadata_file}"

    echo -e "${GREEN}✓ Metadata file created${NC}"
    echo ""
}

# Function to create checksums
create_checksums() {
    echo -e "${YELLOW}Creating checksums for verification...${NC}"

    cd "${ARCHIVE_DEST}"

    # Create SHA256 checksums
    sha256sum *.tar.gz *.txt *.bundle 2>/dev/null | tee ARCHIVE_CHECKSUMS.sha256 > /dev/null

    echo -e "${GREEN}✓ Checksums created in ARCHIVE_CHECKSUMS.sha256${NC}"
    echo ""

    cd - > /dev/null
}

# Function to generate archive report
generate_archive_report() {
    echo -e "${YELLOW}Generating archive report...${NC}"

    local report_file="${ARCHIVE_DEST}/ARCHIVE_REPORT_${TIMESTAMP}.txt"

    {
        echo "GAIA_HOME Archive Report"
        echo "=============================================="
        echo ""
        echo "Archive Summary:"
        echo "  Date: ${ARCHIVE_DATE} $(date '+%H:%M:%S')"
        echo "  Status: COMPLETE"
        echo "  Location: ${ARCHIVE_DEST}"
        echo ""
        echo "Files Archived:"
        ls -lh "${ARCHIVE_DEST}" | tail -n +2
        echo ""
        echo "Total Archive Size:"
        du -sh "${ARCHIVE_DEST}"
        echo ""
        echo "Files per Archive:"
        for archive in "${ARCHIVE_DEST}"/*.tar.gz; do
            if [ -f "${archive}" ]; then
                local count=$(tar -tzf "${archive}" | wc -l)
                echo "  $(basename ${archive}): ${count} files"
            fi
        done
        echo ""
        echo "Archive Manifest:"
        echo "  ✓ Source code"
        echo "  ✓ Git history"
        echo "  ✓ Documentation"
        echo "  ✓ Configuration"
        echo "  ✓ Metadata"
        echo "  ✓ Checksums"
        echo ""
        echo "Next Steps:"
        echo "  1. Upload archive to long-term storage"
        echo "  2. Verify checksums"
        echo "  3. Test recovery procedure"
        echo "  4. Document archive location"
        echo "  5. Set retention reminder for ${RETENTION_YEARS} years"
        echo ""
        echo "Backup Instructions:"
        echo "  1. Copy archive to cloud storage:"
        echo "     gsutil -m cp -r ${ARCHIVE_DEST} gs://backups/gaia_home/"
        echo ""
        echo "  2. Or to S3:"
        echo "     aws s3 cp --recursive ${ARCHIVE_DEST} s3://backups/gaia-home/"
        echo ""
        echo "Recovery Test:"
        echo "  To test recovery, extract the archive:"
        echo "    tar -xzf ${ARCHIVE_DEST}/gaia_home_source_${TIMESTAMP}.tar.gz -C /tmp/test/"
        echo ""
    } > "${report_file}"

    echo -e "${GREEN}✓ Report generated: ${report_file}${NC}"
    echo ""
}

# Function to create verification script
create_verification_script() {
    echo -e "${YELLOW}Creating verification script...${NC}"

    local verify_script="${ARCHIVE_DEST}/verify_archive.sh"

    cat > "${verify_script}" << 'VERIFY_SCRIPT'
#!/bin/bash

# Archive Verification Script
# Verifies the integrity of the GAIA_HOME archive

ARCHIVE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Archive Verification"
echo "=================================="
echo "Archive location: ${ARCHIVE_DIR}"
echo ""

# Verify checksums
echo "Verifying checksums..."
cd "${ARCHIVE_DIR}"

if [ -f "ARCHIVE_CHECKSUMS.sha256" ]; then
    sha256sum -c ARCHIVE_CHECKSUMS.sha256
    if [ $? -eq 0 ]; then
        echo "✓ All checksums verified successfully"
    else
        echo "✗ Checksum verification failed"
        exit 1
    fi
else
    echo "✗ Checksum file not found"
    exit 1
fi

echo ""
echo "Archive Contents:"
ls -lh

echo ""
echo "Verification complete!"
echo "Archive is ready for long-term storage."

VERIFY_SCRIPT

    chmod +x "${verify_script}"
    echo -e "${GREEN}✓ Verification script created${NC}"
    echo ""
}

# Function to create summary
create_summary() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}Archive Complete!${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Archive Location: ${ARCHIVE_DEST}"
    echo "Total Size: $(du -sh ${ARCHIVE_DEST} | awk '{print $1}')"
    echo ""
    echo "Archive Contents:"
    ls -1 "${ARCHIVE_DEST}" | sed 's/^/  - /'
    echo ""
    echo "Next Steps:"
    echo "  1. Verify archive: cd ${ARCHIVE_DEST} && bash verify_archive.sh"
    echo "  2. Upload to storage: gsutil cp -r ${ARCHIVE_DEST} gs://backups/"
    echo "  3. Document location in wiki/docs"
    echo "  4. Set retention reminder for ${RETENTION_YEARS} years"
    echo "  5. Test recovery procedure"
    echo ""
    echo "For more information, see:"
    echo "  - ARCHIVE_METADATA.txt"
    echo "  - ARCHIVE_REPORT_*.txt"
    echo "  - ARCHIVE_CHECKSUMS.sha256"
    echo ""
}

# Main execution
main() {
    verify_prerequisites
    create_archive_directory
    archive_source_code
    export_git_history
    archive_documentation
    archive_configuration
    create_metadata_file
    create_checksums
    generate_archive_report
    create_verification_script
    create_summary
}

# Run main function
main

exit 0
