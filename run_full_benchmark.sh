#!/bin/bash
# Run full AI browser benchmark across all backends

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║          AI Browser Speed Test - Full Benchmark                      ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Check API keys
echo "🔑 Checking API Key Configuration..."
echo ""

BACKENDS_AVAILABLE=0

# Ollama (always available)
echo "✅ Ollama: Available (local)"
BACKENDS_AVAILABLE=$((BACKENDS_AVAILABLE + 1))

# Claude
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "✅ Claude (Codex): Available"
    BACKENDS_AVAILABLE=$((BACKENDS_AVAILABLE + 1))
else
    echo "⚠️  Claude (Codex): Not configured"
    echo "   Set: export ANTHROPIC_API_KEY='sk-ant-...'"
fi

# Grok
if [ -n "$XAI_API_KEY" ]; then
    echo "✅ Grok Code Fast 1: Available"
    BACKENDS_AVAILABLE=$((BACKENDS_AVAILABLE + 1))
else
    echo "⚠️  Grok Code Fast 1: Not configured"
    echo "   Set: export XAI_API_KEY='xai-...'"
fi

# Gemini
if [ -n "$GOOGLE_API_KEY" ]; then
    echo "✅ Google Gemini: Available"
    BACKENDS_AVAILABLE=$((BACKENDS_AVAILABLE + 1))
else
    echo "⚠️  Google Gemini: Not configured"
    echo "   Set: export GOOGLE_API_KEY='AIza...'"
fi

echo ""
echo "📊 Will test $BACKENDS_AVAILABLE backend(s)"
echo ""

# Ask for confirmation
read -p "Continue with benchmark? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Benchmark cancelled"
    exit 0
fi

# Ask for number of iterations
echo ""
read -p "Number of iterations per backend (1-3): " ITERATIONS
ITERATIONS=${ITERATIONS:-1}

echo ""
echo "🚀 Starting benchmark with $ITERATIONS iteration(s)..."
echo "⏱️  Estimated time: $((BACKENDS_AVAILABLE * ITERATIONS * 3)) - $((BACKENDS_AVAILABLE * ITERATIONS * 10)) minutes"
echo ""

# Run benchmark
python3 benchmark_ai_browsers.py "$ITERATIONS"

# Show results
echo ""
echo "✅ Benchmark complete!"
echo ""
echo "Results saved to /tmp/ai_browser_benchmark_*.json"
echo ""
