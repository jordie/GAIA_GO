#!/usr/bin/env python3
"""
Confirm Mutex - Shared lock for auto-confirm workers
Ensures only ONE worker confirms at a time, preventing race conditions.

Both auto-confirm workers use this to coordinate:
- Acquire lock before confirming
- Hold lock during confirmation
- Release lock after confirmation
"""

import fcntl
import time
from pathlib import Path
from datetime import datetime

LOCK_FILE = Path("/tmp/auto_confirm_shared.lock")

class ConfirmMutex:
    """Mutex lock for shared confirmation work"""

    def __init__(self, timeout=5):
        """Initialize mutex with timeout"""
        self.lock_file = LOCK_FILE
        self.timeout = timeout
        self.fd = None
        self.acquired_at = None

    def acquire(self, block=True):
        """
        Acquire lock for confirmation work.

        Returns:
            True if lock acquired, False if timeout
        """
        try:
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            self.fd = open(str(self.lock_file), 'w')

            start_time = time.time()
            while True:
                try:
                    # Try non-blocking lock
                    fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.acquired_at = datetime.now()
                    return True
                except IOError:
                    # Lock held by other worker
                    if not block:
                        return False

                    elapsed = time.time() - start_time
                    if elapsed > self.timeout:
                        self.fd.close()
                        return False

                    time.sleep(0.1)  # Brief wait before retry

        except Exception as e:
            print(f"❌ Error acquiring lock: {e}")
            if self.fd:
                self.fd.close()
            return False

    def release(self):
        """Release lock"""
        try:
            if self.fd:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
                self.fd.close()
                self.fd = None
                return True
        except Exception as e:
            print(f"❌ Error releasing lock: {e}")
        return False

    def __enter__(self):
        """Context manager entry"""
        if not self.acquire():
            raise TimeoutError("Could not acquire confirmation lock")
        return self

    def __exit__(self, *args):
        """Context manager exit"""
        self.release()

    def is_locked(self):
        """Check if lock is held"""
        return self.fd is not None


# Global instance for easy use
_mutex = None

def get_mutex():
    """Get global mutex instance"""
    global _mutex
    if _mutex is None:
        _mutex = ConfirmMutex(timeout=5)
    return _mutex


# Usage example:
# ```python
# from confirm_mutex import get_mutex
#
# mutex = get_mutex()
# if mutex.acquire(block=True):
#     try:
#         # Do confirmation work here
#         tmux_send_keys(session, prompt_response)
#     finally:
#         mutex.release()
#
# # Or with context manager:
# with get_mutex():
#     # Confirmation work happens here
#     tmux_send_keys(session, prompt_response)
# ```
