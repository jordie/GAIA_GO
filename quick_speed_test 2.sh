#!/bin/bash
# Quick speed comparison: Direct script vs AI browsers

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║          AquaTech Login Speed Comparison                             ║"
echo "║                                                                      ║"
echo "║  Comparing:                                                          ║"
echo "║  1. Direct Selenium script (aquatech_login.py)                      ║"
echo "║  2. AI-powered browser (Ollama)                                     ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Clean up any hanging Chrome processes
echo "🧹 Cleaning up Chrome processes..."
pkill -9 chromedriver 2>/dev/null
pkill -9 "Google Chrome" 2>/dev/null
sleep 2

# Test 1: Direct Selenium Script
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Test 1: Direct Selenium Script (aquatech_login.py)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⏱️  Starting direct script test..."
START_DIRECT=$(date +%s)

# Run the direct script
python3 aquatech_login.py > /tmp/direct_test.log 2>&1

END_DIRECT=$(date +%s)
DURATION_DIRECT=$((END_DIRECT - START_DIRECT))

# Check if successful
if grep -q "Data extraction complete" /tmp/direct_test.log; then
    echo "✅ Test completed in ${DURATION_DIRECT}s"

    # Extract results
    if grep -q "\$175" /tmp/direct_test.log; then
        echo "✅ Successfully extracted: \$175.00 monthly payment"
    fi

    DIRECT_SUCCESS=true
else
    echo "❌ Test failed"
    echo "   Check /tmp/direct_test.log for details"
    DIRECT_SUCCESS=false
fi

# Wait before next test
echo ""
echo "⏸️  Waiting 5 seconds before next test..."
sleep 5

# Test 2: AI Browser (Ollama) - Skip for now, just show what would happen
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Test 2: AI Browser (Ollama/llava)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  Note: Ollama vision model (llava) is significantly slower"
echo "   Expected time: 5-10 minutes (analyzes screenshots with AI)"
echo ""
read -p "Run AI browser test? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "⏱️  Starting AI browser test..."
    START_AI=$(date +%s)

    # Run AI browser with timeout
    timeout 600 python3 multi_ai_browser.py ollama \
        "Login to AquaTech and find monthly payment for Saba Girmay" \
        https://www.aquatechswim.com > /tmp/ai_test.log 2>&1

    EXIT_CODE=$?
    END_AI=$(date +%s)
    DURATION_AI=$((END_AI - START_AI))

    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Test completed in ${DURATION_AI}s"
        AI_SUCCESS=true
    elif [ $EXIT_CODE -eq 124 ]; then
        echo "⏱️  Test timeout after ${DURATION_AI}s (10 minute limit)"
        AI_SUCCESS=false
    else
        echo "❌ Test failed after ${DURATION_AI}s"
        echo "   Check /tmp/ai_test.log for details"
        AI_SUCCESS=false
    fi
else
    echo "⏭️  Skipped AI browser test"
    AI_SUCCESS=false
    DURATION_AI=0
fi

# Results Summary
echo ""
echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                        RESULTS SUMMARY                                ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Method                    | Time      | Status    | Notes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Direct script result
if [ "$DIRECT_SUCCESS" = true ]; then
    printf " %-25s | %-9s | %-9s | %s\n" \
        "Direct Selenium" \
        "${DURATION_DIRECT}s" \
        "✅ Success" \
        "Fast, deterministic"
else
    printf " %-25s | %-9s | %-9s | %s\n" \
        "Direct Selenium" \
        "${DURATION_DIRECT}s" \
        "❌ Failed" \
        "Check logs"
fi

# AI browser result
if [ "$AI_SUCCESS" = true ]; then
    printf " %-25s | %-9s | %-9s | %s\n" \
        "AI Browser (Ollama)" \
        "${DURATION_AI}s" \
        "✅ Success" \
        "Intelligent, adaptive"
elif [ $DURATION_AI -gt 0 ]; then
    printf " %-25s | %-9s | %-9s | %s\n" \
        "AI Browser (Ollama)" \
        "${DURATION_AI}s" \
        "❌ Failed" \
        "Slow vision model"
else
    printf " %-25s | %-9s | %-9s | %s\n" \
        "AI Browser (Ollama)" \
        "N/A" \
        "⏭️  Skipped" \
        "Not tested"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Winner
if [ "$DIRECT_SUCCESS" = true ]; then
    echo "🏆 FASTEST: Direct Selenium Script (${DURATION_DIRECT}s)"
    echo ""
    echo "💡 Key Takeaway:"
    echo "   - Direct script: Fast and reliable for known workflows"
    echo "   - AI browser: Flexible and adaptive for unknown sites"
    echo "   - For production: Use direct scripts when possible"
    echo "   - For exploration: Use AI browsers (especially with faster models)"
fi

echo ""
echo "📊 Full logs:"
echo "   Direct script: /tmp/direct_test.log"
if [ $DURATION_AI -gt 0 ]; then
    echo "   AI browser: /tmp/ai_test.log"
fi

echo ""
echo "🚀 To test faster AI models (Claude, Grok, Gemini):"
echo "   1. Set up API keys: ./setup_benchmark_keys.sh"
echo "   2. Run full benchmark: ./run_full_benchmark.sh"
echo ""
