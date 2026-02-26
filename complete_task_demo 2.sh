#!/bin/bash
# Demo: How an agent would complete a task with file locking

AGENT_NAME="dev-backend-1"
WORK_DIR="/tmp/test_work"

echo "Step 1: Acquire lock on work directory"
python3 /Users/jgirmay/Desktop/gitrepo/pyWork/architect/file_lock_manager.py << PYTHON
from file_lock_manager import FileLockManager
from pathlib import Path

manager = FileLockManager("$AGENT_NAME")
if manager.acquire_lock(Path("$WORK_DIR"), timeout=60):
    print("✅ Lock acquired!")
else:
    print("❌ Could not acquire lock")
PYTHON

echo ""
echo "Step 2: Perform the work"
cd "$WORK_DIR" || mkdir -p "$WORK_DIR"
find . -name "*.py" | wc -l

echo ""
echo "Step 3: Release lock"
python3 << PYTHON
from file_lock_manager import FileLockManager
from pathlib import Path

manager = FileLockManager("$AGENT_NAME")
manager.release_lock(Path("$WORK_DIR"))
print("✅ Lock released!")
PYTHON
