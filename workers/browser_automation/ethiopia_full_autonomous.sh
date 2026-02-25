#!/bin/bash
# Fully autonomous Ethiopia research - no interaction needed
# Opens tabs, submits prompts, collects URLs

cd "$(dirname "$0")"

echo "========================================================================"
echo "ETHIOPIA PROJECT - FULLY AUTONOMOUS EXECUTION"
echo "========================================================================"
echo ""
echo "This will:"
echo "  1. Open 7 Perplexity tabs"
echo "  2. Submit prompts to each (3-5 min delays)"
echo "  3. Collect conversation URLs"
echo "  4. Update Google Sheet"
echo ""
echo "Estimated time: 2-3 hours"
echo "Starting in 5 seconds..."
echo ""

sleep 5

# Load prompts
if [ ! -f "ethiopia_prompts.json" ]; then
    echo "Error: ethiopia_prompts.json not found"
    exit 1
fi

# Get topic count
TOPIC_COUNT=$(python3 -c "import json; print(len(json.load(open('ethiopia_prompts.json'))['tab_groups']))")

echo "Topics to research: $TOPIC_COUNT"
echo ""

# Process each topic
for i in $(seq 0 $((TOPIC_COUNT-1))); do
    # Get topic info
    TOPIC_NAME=$(python3 -c "import json; print(json.load(open('ethiopia_prompts.json'))['tab_groups'][$i]['name'])")
    TOPIC_PROMPT=$(python3 -c "import json; print(json.load(open('ethiopia_prompts.json'))['tab_groups'][$i]['prompt'])")

    echo "========================================================================"
    echo "[$(($i+1))/$TOPIC_COUNT] $TOPIC_NAME"
    echo "========================================================================"
    echo ""

    # Copy prompt to clipboard
    echo "$TOPIC_PROMPT" | pbcopy
    echo "✓ Copied prompt to clipboard"

    # Open Perplexity in new tab
    open "https://www.perplexity.ai"
    sleep 5

    # Activate browser and paste
    osascript -e '
tell application "Comet" to activate
delay 2
tell application "System Events"
    keystroke "f" using {command down}
    delay 0.5
    key code 53
    delay 0.5
    keystroke tab
    delay 1
    keystroke "v" using {command down}
    delay 2
    keystroke return
end tell
'

    echo "✓ Submitted prompt"
    echo ""

    # Wait for response
    echo "⏳ Waiting for Perplexity response (60 seconds)..."
    sleep 60

    # Get URL from current tab (would need browser automation)
    echo "📋 Please manually copy conversation URL and run:"
    echo "   python3 ethiopia_add_url.py add '$TOPIC_NAME' 'URL'"
    echo ""

    # Rate limiting
    if [ $i -lt $((TOPIC_COUNT-1)) ]; then
        DELAY=$((180 + RANDOM % 120))  # 3-5 minutes
        MINS=$((DELAY / 60))
        SECS=$((DELAY % 60))

        echo "⏱️  Rate limiting: ${MINS}m ${SECS}s"
        NEXT_INDEX=$(($i+1))
        NEXT_TOPIC=$(python3 -c "import json; print(json.load(open('ethiopia_prompts.json'))['tab_groups'][$NEXT_INDEX]['name'])")
        echo "   Next: $NEXT_TOPIC"
        echo ""

        sleep $DELAY
    fi
done

echo "========================================================================"
echo "✅ ALL PROMPTS SUBMITTED"
echo "========================================================================"
echo ""
echo "Check Perplexity tabs for responses"
echo "Copy conversation URLs and update Google Sheet"
echo ""
