#!/bin/bash
# Quick agent comparison - send simple task to all working agents

echo "🏆 Quick Agent Comparison Test"
echo "================================"
echo ""
echo "Task: Write a Python function to reverse a string"
echo ""

# Create results directory
mkdir -p agent_comparison_results

# Task description
TASK="Write a Python function called reverse_string(s) that reverses a string. Include 2 test cases. Save to solution.py"

# Test distributed agents
echo "📋 Testing distributed agents..."
python3 distributed_task_router.py assign "$TASK" /tmp/test_dev_backend dev-backend-1
python3 distributed_task_router.py assign "$TASK" /tmp/test_dev_fullstack dev-fullstack-1
python3 distributed_task_router.py assign "$TASK" /tmp/test_pink_dev1 pink-dev-1

# Test Ollama (quick model)
echo ""
echo "📋 Testing Ollama (llama3.2 - fastest model)..."
timeout 60s ollama run llama3.2 "Write a Python function called reverse_string(s) that reverses a string. Include 2 test cases. Show only the Python code." > agent_comparison_results/ollama_llama3.2.py 2>&1 &

echo ""
echo "✅ Tasks assigned! Results will appear in:"
echo "   - /tmp/test_dev_backend/solution.py (Claude)"
echo "   - /tmp/test_dev_fullstack/solution.py (Gemini local)"
echo "   - /tmp/test_pink_dev1/solution.py (Gemini remote)"
echo "   - agent_comparison_results/ollama_llama3.2.py (Ollama)"
echo ""
echo "Wait 60-120 seconds, then check results with:"
echo "   ./check_agent_results.sh"
