#!/bin/bash
# Check results from agent comparison test

echo "📊 Agent Comparison Results"
echo "============================"
echo ""

check_result() {
    agent=$1
    file=$2

    if [ -f "$file" ]; then
        size=$(wc -c < "$file")
        lines=$(wc -l < "$file")
        echo "✅ $agent"
        echo "   File: $file"
        echo "   Size: $size bytes, $lines lines"
        echo "   Preview:"
        head -20 "$file" | sed 's/^/   /'
        echo ""
    else
        echo "❌ $agent - No result yet"
        echo "   Expected: $file"
        echo ""
    fi
}

echo "Distributed Agents:"
echo "-------------------"
check_result "dev-backend-1 (Claude)" "/tmp/test_dev_backend/solution.py"
check_result "dev-fullstack-1 (Gemini)" "/tmp/test_dev_fullstack/solution.py"
check_result "pink-dev-1 (Gemini remote)" "/tmp/test_pink_dev1/solution.py"

echo "Ollama:"
echo "-------"
check_result "llama3.2 (Ollama)" "agent_comparison_results/ollama_llama3.2.py"

echo "============================"
echo ""
echo "To see full files:"
echo "  cat /tmp/test_dev_backend/solution.py"
echo "  cat /tmp/test_dev_fullstack/solution.py"
echo "  cat /tmp/test_pink_dev1/solution.py"
echo "  cat agent_comparison_results/ollama_llama3.2.py"
