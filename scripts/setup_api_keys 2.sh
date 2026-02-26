#!/bin/bash

# Setup API Keys for LLM Provider Comparison
# This script configures environment variables for all LLM providers

set -e

echo "=================================="
echo "API Keys Configuration Setup"
echo "=================================="
echo ""

# Check if keys are already set
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "✓ ANTHROPIC_API_KEY is set"
else
    echo "❌ ANTHROPIC_API_KEY is not set"
fi

if [ -n "$GOOGLE_API_KEY" ]; then
    echo "✓ GOOGLE_API_KEY is set"
else
    echo "❌ GOOGLE_API_KEY is not set"
fi

if [ -n "$OPENAI_API_KEY" ]; then
    echo "✓ OPENAI_API_KEY is set"
else
    echo "❌ OPENAI_API_KEY is not set"
fi

echo ""
echo "To set keys, export them in your current shell:"
echo ""
echo "  export ANTHROPIC_API_KEY='your-anthropic-key'"
echo "  export GOOGLE_API_KEY='your-google-key'"
echo "  export OPENAI_API_KEY='your-openai-key'"
echo ""
echo "Then run this script again to verify."
echo ""

# If all keys are set, proceed with setup
if [ -n "$ANTHROPIC_API_KEY" ] && [ -n "$GOOGLE_API_KEY" ] && [ -n "$OPENAI_API_KEY" ]; then
    echo "✓ All keys are configured!"
    echo ""
    echo "Next steps:"
    echo "1. Kill old gaia sessions: pkill -f 'gaia.py'"
    echo "2. Start new sessions: ./scripts/start_provider_sessions.sh"
    echo "3. Run comparison: python3 tools/provider_comparison_simple.py"
else
    echo "⚠️  Please set missing API keys first"
    exit 1
fi
