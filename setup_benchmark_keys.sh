#!/bin/bash
# Quick setup for AI browser benchmark API keys

echo "🔑 AI Browser Benchmark - API Key Setup"
echo "=" | tr '=' '-' | head -c 70 && echo
echo ""
echo "This script helps you configure API keys for speed testing."
echo "You only need to set up the backends you want to test."
echo ""
echo "Ollama is already configured (free, local)."
echo ""

# Function to set key
set_key() {
    local service=$1
    local var_name=$2
    local example=$3
    local url=$4

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔐 $service Setup"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    if [ -n "${!var_name}" ]; then
        echo "✅ $var_name is already set"
        read -p "Update it? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return
        fi
    fi

    echo "Get your API key from: $url"
    echo "Example format: $example"
    echo ""
    read -p "Enter your $service API key (or press Enter to skip): " key

    if [ -n "$key" ]; then
        echo "export $var_name='$key'" >> ~/.bash_profile
        echo "export $var_name='$key'" >> ~/.zshrc
        export "$var_name=$key"
        echo "✅ $var_name configured"
        echo "   (Added to ~/.bash_profile and ~/.zshrc)"
    else
        echo "⏭️  Skipped $service"
    fi
}

# Setup each service
set_key "Anthropic Claude (Codex)" \
        "ANTHROPIC_API_KEY" \
        "sk-ant-api03-..." \
        "https://console.anthropic.com/settings/keys"

set_key "xAI Grok" \
        "XAI_API_KEY" \
        "xai-..." \
        "https://console.x.ai/"

set_key "Google Gemini" \
        "GOOGLE_API_KEY" \
        "AIza..." \
        "https://makersuite.google.com/app/apikey"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Current Configuration:"
[ -n "$ANTHROPIC_API_KEY" ] && echo "  ✅ Claude (Codex)" || echo "  ⚠️  Claude (Codex) - Not configured"
[ -n "$XAI_API_KEY" ] && echo "  ✅ Grok Code Fast 1" || echo "  ⚠️  Grok Code Fast 1 - Not configured"
[ -n "$GOOGLE_API_KEY" ] && echo "  ✅ Google Gemini" || echo "  ⚠️  Google Gemini - Not configured"
echo "  ✅ Ollama (local)"
echo ""
echo "🚀 Next Steps:"
echo "  1. Reload your shell: source ~/.bash_profile  (or restart terminal)"
echo "  2. Run benchmark: ./run_full_benchmark.sh"
echo "  3. Or direct: python3 benchmark_ai_browsers.py"
echo ""
echo "💡 Tip: Start a new terminal session for API keys to take effect"
echo ""
