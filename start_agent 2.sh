#!/bin/bash
# Start a functioning agent with Claude/Gemini

AGENT_NAME="$1"
AGENT_TOOL="$2"  # claude, gemini, or codex

if [ -z "$AGENT_NAME" ] || [ -z "$AGENT_TOOL" ]; then
    echo "Usage: $0 <agent-name> <tool> [ai_backend]"
    echo "  tool: claude, gemini, codex, openclaw, playwright, or ai-browser"
    echo "  ai_backend (for ai-browser): ollama, claude, grok, or gemini"
    echo ""
    echo "Examples:"
    echo "  $0 dev-1 claude"
    echo "  $0 browser-1 ai-browser ollama"
    echo "  $0 browser-2 ai-browser grok"
    exit 1
fi

echo "🚀 Starting agent: $AGENT_NAME with tool: $AGENT_TOOL"

# Source Gemini API key
source /Users/jgirmay/Desktop/gitrepo/pyWork/architect/.env.gemini

# Create tmux session with actual LLM running
case $AGENT_TOOL in
    gemini)
        echo "Starting Gemini agent..."
        tmux new-session -d -s "$AGENT_NAME" "
            echo '=================================='
            echo 'Agent: $AGENT_NAME'
            echo 'Tool: Gemini'
            echo 'File Locking: ENABLED'
            echo '=================================='
            echo ''
            echo 'Ready to receive tasks!'
            echo 'When you receive a task:'
            echo '1. Use file_lock_manager.py to acquire lock'
            echo '2. Perform the work'
            echo '3. Release the lock'
            echo ''
            export GEMINI_API_KEY='$GEMINI_API_KEY'
            export GEMINI_MODEL='${GEMINI_MODEL:-gemini-1.5-flash}'
            gemini --model \$GEMINI_MODEL
        "
        ;;
    claude|codex)
        echo "Starting Claude agent..."
        tmux new-session -d -s "$AGENT_NAME" "
            echo '=================================='
            echo 'Agent: $AGENT_NAME'
            echo 'Tool: Claude'
            echo 'File Locking: ENABLED'
            echo '=================================='
            echo ''
            echo 'Ready to receive tasks!'
            echo 'When you receive a task:'
            echo '1. Use file_lock_manager.py to acquire lock'
            echo '2. Perform the work'
            echo '3. Release the lock'
            echo ''
            claude
        "
        ;;
    openclaw)
        echo "Starting OpenClaw browser automation agent..."
        tmux new-session -d -s "$AGENT_NAME" "
            echo '=================================='
            echo 'Agent: $AGENT_NAME'
            echo 'Tool: OpenClaw (Browser Automation)'
            echo 'File Locking: ENABLED'
            echo '=================================='
            echo ''
            echo 'Ready to receive browser automation tasks!'
            echo 'When you receive a task:'
            echo '1. Use file_lock_manager.py to acquire lock'
            echo '2. Execute browser automation'
            echo '3. Release the lock'
            echo ''
            # Check if openclaw is installed
            if command -v openclaw &> /dev/null; then
                openclaw
            elif command -v claw &> /dev/null; then
                claw
            else
                echo '⚠️  OpenClaw not found. Please install OpenClaw first.'
                echo 'Falling back to Claude for now...'
                claude
            fi
        "
        ;;
    playwright)
        echo "Starting Playwright browser automation agent..."
        tmux new-session -d -s "$AGENT_NAME" "
            echo '=========================================='
            echo '🎭 Playwright Browser Automation Agent'
            echo 'Agent: $AGENT_NAME'
            echo 'Tool: Playwright (Real Browser)'
            echo 'File Locking: ENABLED'
            echo '=========================================='
            echo ''
            echo '✅ Capabilities:'
            echo '  • Authenticated logins'
            echo '  • Form filling'
            echo '  • Dynamic content extraction'
            echo '  • Screenshot capture'
            echo '  • JavaScript execution'
            echo ''
            echo 'Ready to receive tasks!'
            echo ''
            echo 'This agent waits for tasks from agent_task_router.py'
            echo 'Tasks are executed via workers/browser_agent.py'
            echo ''
            bash
        "
        ;;
    ai-browser)
        AI_BACKEND="${3:-ollama}"  # Default to ollama, or use 3rd arg
        echo "Starting AI Browser agent with $AI_BACKEND backend..."
        tmux new-session -d -s "$AGENT_NAME" "
            echo '=========================================='
            echo '🤖 AI Browser Automation Agent'
            echo 'Agent: $AGENT_NAME'
            echo 'AI Backend: $AI_BACKEND'
            echo 'File Locking: ENABLED'
            echo '=========================================='
            echo ''
            echo '✅ Capabilities:'
            echo '  • AI-powered navigation decisions'
            echo '  • Screenshot analysis'
            echo '  • Intelligent form filling'
            echo '  • Goal-oriented browsing'
            echo '  • Multi-model support (Ollama, Claude, Grok, Gemini)'
            echo ''
            echo 'Ready to receive tasks!'
            echo ''
            echo 'Usage: multi_ai_browser.py <ai_backend> <goal> [url]'
            echo 'Example: python3 multi_ai_browser.py $AI_BACKEND \"Find pricing\" https://example.com'
            echo ''
            bash
        "
        ;;
    *)
        echo "Unknown tool: $AGENT_TOOL"
        exit 1
        ;;
esac

echo "✅ Agent $AGENT_NAME started"
echo "📺 Attach with: tmux attach -t $AGENT_NAME"
