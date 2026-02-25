#!/bin/bash
# Verify all prerequisites for development team setup

echo "🔍 Verifying Prerequisites for Development Team Setup"
echo "======================================================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# 1. Check tmux
echo ""
echo "1️⃣  Checking tmux..."
if command -v tmux &> /dev/null; then
    VERSION=$(tmux -V)
    echo -e "   ${GREEN}✓${NC} tmux is installed: $VERSION"
else
    echo -e "   ${RED}✗${NC} tmux is NOT installed"
    echo "      Install with: brew install tmux"
    ERRORS=$((ERRORS + 1))
fi

# 2. Check Go
echo ""
echo "2️⃣  Checking Go..."
if command -v go &> /dev/null; then
    VERSION=$(go version)
    echo -e "   ${GREEN}✓${NC} Go is installed: $VERSION"
else
    echo -e "   ${RED}✗${NC} Go is NOT installed"
    echo "      Install with: brew install go"
    ERRORS=$((ERRORS + 1))
fi

# 3. Check wrapper binaries
echo ""
echo "3️⃣  Checking Go Wrapper binaries..."
WRAPPER="/Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper/wrapper"
APISERVER="/Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper/apiserver"

if [ -f "$WRAPPER" ]; then
    echo -e "   ${GREEN}✓${NC} wrapper binary exists"
else
    echo -e "   ${YELLOW}⚠${NC} wrapper binary not found"
    echo "      Build with: cd go_wrapper && go build -o wrapper main.go"
fi

if [ -f "$APISERVER" ]; then
    echo -e "   ${GREEN}✓${NC} apiserver binary exists"
else
    echo -e "   ${YELLOW}⚠${NC} apiserver binary not found"
    echo "      Build with: cd go_wrapper && go build -o apiserver cmd/apiserver/main.go"
fi

# 4. Check Gemini CLI
echo ""
echo "4️⃣  Checking Gemini CLI..."
if command -v gemini &> /dev/null; then
    VERSION=$(gemini --version 2>&1)
    echo -e "   ${GREEN}✓${NC} gemini CLI is installed: $VERSION"
else
    echo -e "   ${RED}✗${NC} gemini CLI is NOT installed"
    echo "      Install from: https://github.com/google-gemini/generative-ai-go"
    ERRORS=$((ERRORS + 1))
fi

# 5. Check Gemini API Key
echo ""
echo "5️⃣  Checking Gemini API Key..."
if [ -n "$GEMINI_API_KEY" ]; then
    MASKED_KEY="${GEMINI_API_KEY:0:8}...${GEMINI_API_KEY: -4}"
    echo -e "   ${GREEN}✓${NC} GEMINI_API_KEY is set: $MASKED_KEY"
else
    echo -e "   ${RED}✗${NC} GEMINI_API_KEY is NOT set"
    echo "      Set with: export GEMINI_API_KEY='your-api-key'"
    echo "      Or add to .env.local or ~/.zshrc"
    ERRORS=$((ERRORS + 1))
fi

# 6. Check Python
echo ""
echo "6️⃣  Checking Python..."
if command -v python3 &> /dev/null; then
    VERSION=$(python3 --version)
    echo -e "   ${GREEN}✓${NC} Python is installed: $VERSION"
else
    echo -e "   ${RED}✗${NC} Python 3 is NOT installed"
    ERRORS=$((ERRORS + 1))
fi

# 7. Check port 8151
echo ""
echo "7️⃣  Checking port 8151..."
if lsof -Pi :8151 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "   ${YELLOW}⚠${NC} Port 8151 is already in use (API server may be running)"
    echo "      Check with: lsof -i :8151"
else
    echo -e "   ${GREEN}✓${NC} Port 8151 is available"
fi

# 8. Check Tailscale
echo ""
echo "8️⃣  Checking Tailscale..."
if command -v tailscale &> /dev/null; then
    TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "")
    if [ -n "$TAILSCALE_IP" ]; then
        echo -e "   ${GREEN}✓${NC} Tailscale is running: $TAILSCALE_IP"
        echo "      Dashboards will be accessible at: http://$TAILSCALE_IP:8151"
    else
        echo -e "   ${YELLOW}⚠${NC} Tailscale installed but not connected"
        echo "      Connect with: tailscale up"
    fi
else
    echo -e "   ${YELLOW}⚠${NC} Tailscale not installed (optional but recommended)"
    echo "      Install from: https://tailscale.com/download"
fi

# 9. Check disk space
echo ""
echo "9️⃣  Checking disk space..."
AVAILABLE=$(df -h . | awk 'NR==2 {print $4}')
echo -e "   ${GREEN}✓${NC} Available disk space: $AVAILABLE"

# Summary
echo ""
echo "======================================================================"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ All prerequisites met! Ready to setup development team.${NC}"
    echo ""
    echo "Next steps:"
    echo "  python3 setup_dev_team.py"
    exit 0
else
    echo -e "${RED}❌ $ERRORS error(s) found. Please fix the issues above.${NC}"
    exit 1
fi
