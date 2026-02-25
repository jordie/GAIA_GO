#!/bin/bash
# Setup fast local LLM models for browser automation

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║        Fast Local AI Models for Browser Automation                   ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama is not installed"
    echo "   Install from: https://ollama.ai"
    exit 1
fi

echo "✅ Ollama is installed"
echo ""

# Show current models
echo "📦 Currently installed models:"
ollama list
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Recommended Fast Models"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Model             | Size  | Speed      | Vision | Best For"
echo "------------------|-------|------------|--------|------------------"
echo "llama3.2-vision   | 11B   | Fast       | Yes    | Balance (recommended)"
echo "moondream         | 1.6B  | Very Fast  | Yes    | Speed-critical"
echo "phi3              | 3.8B  | Very Fast  | No     | Text-only (fastest)"
echo "llava-phi3        | 3.8B  | Fast       | Yes    | Small vision model"
echo ""

# Ask which models to install
echo "Which models would you like to install?"
echo ""
echo "1) llama3.2-vision (11GB) - Recommended for best balance"
echo "2) moondream (1.7GB) - Fastest vision model"
echo "3) phi3 (2.3GB) - Fastest text-only"
echo "4) All three (15GB total)"
echo "5) Skip installation"
echo ""
read -p "Enter choice (1-5): " choice

case $choice in
    1)
        echo ""
        echo "📥 Installing llama3.2-vision..."
        ollama pull llama3.2-vision
        INSTALLED="llama3.2-vision"
        ;;
    2)
        echo ""
        echo "📥 Installing moondream..."
        ollama pull moondream
        INSTALLED="moondream"
        ;;
    3)
        echo ""
        echo "📥 Installing phi3..."
        ollama pull phi3
        INSTALLED="phi3"
        ;;
    4)
        echo ""
        echo "📥 Installing all three models..."
        ollama pull llama3.2-vision &
        PID1=$!
        ollama pull moondream &
        PID2=$!
        ollama pull phi3 &
        PID3=$!

        wait $PID1 $PID2 $PID3
        INSTALLED="llama3.2-vision, moondream, phi3"
        ;;
    5)
        echo "⏭️  Skipped installation"
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "✅ Installation complete!"
echo ""

# Test the installed model
if [ -n "$INSTALLED" ]; then
    PRIMARY_MODEL=$(echo $INSTALLED | cut -d',' -f1)

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🧪 Quick Speed Test"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Testing $PRIMARY_MODEL response time..."
    echo ""

    START=$(date +%s)
    ollama run $PRIMARY_MODEL "Say 'hello' in one word" --verbose false 2>/dev/null
    END=$(date +%s)
    DURATION=$((END - START))

    echo ""
    echo "⏱️  Response time: ${DURATION}s"

    if [ $DURATION -lt 5 ]; then
        echo "✅ Excellent! Model is fast and ready."
    elif [ $DURATION -lt 10 ]; then
        echo "✅ Good! Model is ready for use."
    else
        echo "⚠️  Slower than expected. May need optimization."
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Usage Examples"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "# Use llama3.2-vision (best balance):"
echo "python3 fast_local_ai_browser.py llama3.2-vision \"Find pricing\" https://example.com"
echo ""
echo "# Use moondream (fastest vision):"
echo "python3 fast_local_ai_browser.py moondream \"Navigate and click\" https://example.com"
echo ""
echo "# Use phi3 (fastest text-only, no screenshots):"
echo "python3 fast_local_ai_browser.py llama3.2 \"Extract data\" https://example.com"
echo ""
echo "# Compare speeds:"
echo "./compare_local_models.sh"
echo ""

# Show installed models
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Installed Models"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
ollama list
echo ""
