#!/bin/bash
# Setup script for multi-AI browser automation

echo "🤖 Multi-AI Browser Setup"
echo "=" | tr '=' '-' | head -c 70 && echo

# Check Python dependencies
echo "📦 Checking dependencies..."
python3 -c "import anthropic" 2>/dev/null || {
    echo "⚠️  anthropic package not found"
    echo "   Install: pip install anthropic"
}

python3 -c "import selenium" 2>/dev/null || {
    echo "⚠️  selenium package not found"
    echo "   Install: pip install selenium webdriver-manager"
}

echo ""
echo "🔑 API Key Configuration"
echo "=" | tr '=' '-' | head -c 70 && echo

# Check API keys
check_key() {
    local key_name=$1
    local key_var=$2

    if [ -n "${!key_var}" ]; then
        echo "✅ $key_name is configured"
    else
        echo "❌ $key_name is NOT configured"
        echo "   Set: export $key_var='your-key-here'"
    fi
}

check_key "Anthropic (Claude)" "ANTHROPIC_API_KEY"
check_key "xAI (Grok)" "XAI_API_KEY"
check_key "Google (Gemini)" "GOOGLE_API_KEY"

echo ""
echo "🔧 Ollama Setup"
echo "=" | tr '=' '-' | head -c 70 && echo

# Check Ollama
if command -v ollama &> /dev/null; then
    echo "✅ Ollama is installed"

    # Check if llava model is available
    if ollama list | grep -q llava; then
        echo "✅ llava model is installed"
    else
        echo "⚠️  llava model not found"
        echo "   Install: ollama pull llava"
    fi
else
    echo "❌ Ollama is NOT installed"
    echo "   Install: https://ollama.ai"
fi

echo ""
echo "📝 Environment Setup"
echo "=" | tr '=' '-' | head -c 70 && echo

# Create .env file template if doesn't exist
if [ ! -f .env.ai_browser ]; then
    cat > .env.ai_browser << 'EOF'
# AI Browser Automation API Keys
# Copy this to .env and fill in your keys

# Anthropic Claude (Codex)
# Get from: https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-...

# xAI Grok
# Get from: https://console.x.ai/
XAI_API_KEY=xai-...

# Google Gemini
# Get from: https://makersuite.google.com/app/apikey
GOOGLE_API_KEY=AIza...

# Ollama endpoint (local)
OLLAMA_URL=http://localhost:11434
EOF
    echo "✅ Created .env.ai_browser template"
    echo "   Edit this file with your API keys"
else
    echo "✅ .env.ai_browser already exists"
fi

echo ""
echo "🚀 Usage Examples"
echo "=" | tr '=' '-' | head -c 70 && echo
echo ""
echo "# Using Ollama (free, local):"
echo "python3 multi_ai_browser.py ollama \"Find pricing\" https://example.com"
echo ""
echo "# Using Claude (fast, accurate):"
echo "python3 multi_ai_browser.py claude \"Login and get account info\" https://example.com"
echo ""
echo "# Using Grok (fastest):"
echo "python3 multi_ai_browser.py grok \"Navigate and find information\" https://example.com"
echo ""
echo "# Using Gemini (cost-effective):"
echo "python3 multi_ai_browser.py gemini \"Extract data from page\" https://example.com"
echo ""

echo "=" | tr '=' '-' | head -c 70 && echo
echo "✅ Setup check complete!"
