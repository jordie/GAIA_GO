#!/bin/bash
# Compare speed of different local LLM models

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║        Local AI Models Speed Comparison                              ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Models to test
MODELS=(
    "llama3.2-vision:11B vision model"
    "moondream:1.6B tiny vision"
    "llama3.2:Text-only (fastest)"
)

# Test prompt
TEST_PROMPT="What's on this page? Answer in 5 words."

echo "🧪 Testing model response times..."
echo "Test prompt: \"$TEST_PROMPT\""
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

RESULTS_FILE="/tmp/model_comparison_$$.txt"
> "$RESULTS_FILE"

for model_info in "${MODELS[@]}"; do
    MODEL=$(echo "$model_info" | cut -d':' -f1)
    DESC=$(echo "$model_info" | cut -d':' -f2)

    # Check if model is installed
    if ! ollama list | grep -q "^$MODEL"; then
        echo "⏭️  $MODEL ($DESC) - Not installed"
        echo "$MODEL|N/A|Not installed" >> "$RESULTS_FILE"
        continue
    fi

    echo "Testing $MODEL ($DESC)..."

    # Warm up (first run is always slower)
    ollama run "$MODEL" "test" --verbose false > /dev/null 2>&1

    # Actual test
    START=$(date +%s%3N)  # milliseconds
    ollama run "$MODEL" "$TEST_PROMPT" --verbose false > /dev/null 2>&1
    END=$(date +%s%3N)

    DURATION=$((END - START))
    SECONDS=$(echo "scale=2; $DURATION/1000" | bc)

    echo "  ⏱️  ${SECONDS}s"
    echo ""

    echo "$MODEL|$SECONDS|$DESC" >> "$RESULTS_FILE"
done

# Show results table
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Results Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
printf "%-20s | %-10s | %s\n" "Model" "Time" "Description"
echo "---------------------+------------+--------------------------------"

# Sort results by time
sort -t'|' -k2 -n "$RESULTS_FILE" | while IFS='|' read -r model time desc; do
    if [ "$time" = "N/A" ]; then
        printf "%-20s | %-10s | %s\n" "$model" "$time" "$desc"
    else
        printf "%-20s | %8.2fs | %s\n" "$model" "$time" "$desc"
    fi
done

echo ""

# Find fastest
FASTEST=$(sort -t'|' -k2 -n "$RESULTS_FILE" | grep -v "N/A" | head -1)
if [ -n "$FASTEST" ]; then
    FASTEST_MODEL=$(echo "$FASTEST" | cut -d'|' -f1)
    FASTEST_TIME=$(echo "$FASTEST" | cut -d'|' -f2)

    echo "🏆 FASTEST: $FASTEST_MODEL (${FASTEST_TIME}s)"
    echo ""
    echo "💡 Recommendation:"

    if [ "$FASTEST_MODEL" = "llama3.2" ]; then
        echo "   Use: python3 fast_local_ai_browser.py llama3.2 \"task\" url"
        echo "   Note: Text-only (no vision), but fastest"
    elif [ "$FASTEST_MODEL" = "moondream" ]; then
        echo "   Use: python3 fast_local_ai_browser.py moondream \"task\" url"
        echo "   Note: Tiny model with vision support"
    else
        echo "   Use: python3 fast_local_ai_browser.py $FASTEST_MODEL \"task\" url"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 Notes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  • First run is always slower (model loading)"
echo "  • Vision models analyze screenshots (slower but flexible)"
echo "  • Text models use HTML only (faster but no visual understanding)"
echo "  • Smaller models = faster inference"
echo ""
echo "To install missing models: ./setup_fast_local_models.sh"
echo ""

rm "$RESULTS_FILE"
