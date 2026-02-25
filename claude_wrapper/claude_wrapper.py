#!/usr/bin/env python3
"""
Claude Code Wrapper - Thin shell with hot-reloadable modules.

This script is a minimal wrapper that:
1. Manages the PTY session with Claude
2. Loads functionality from wrapper_core/ modules
3. Supports hot-reloading modules without restarting

The actual logic (prompt detection, logging, etc.) lives in wrapper_core/
and can be updated while the wrapper is running.

Usage:
    ./claude_wrapper.py                    # Start with prompt logging
    ./claude_wrapper.py --no-log           # Run without logging
    ./claude_wrapper.py --reload           # Signal running wrapper to reload

Hot Reload:
    touch /tmp/claude_wrapper_reload       # Trigger reload
    # Or from another terminal:
    ./claude_wrapper.py --reload
"""

import argparse
import os
import pty
import select
import signal
import sys
from pathlib import Path
from threading import Thread

# Thin shell version (not module versions)
__version__ = "2.0.0"

SCRIPT_DIR = Path(__file__).parent
RELOAD_SIGNAL_PATH = Path("/tmp/claude_wrapper_reload")


def signal_reload():
    """Signal a running wrapper to reload its modules."""
    RELOAD_SIGNAL_PATH.touch()
    print("Reload signal sent. Running wrapper will reload modules.")
    return 0


class ThinWrapper:
    """
    Minimal wrapper shell that delegates to wrapper_core modules.

    This class handles only:
    - PTY/terminal management
    - Module loading and reloading
    - Signal handling
    - Auto-response coordination

    All prompt detection, logging, etc. is in wrapper_core.
    """

    def __init__(self, log_file=None, no_log=False, auto_respond=False):
        self.log_file = log_file
        self.no_log = no_log
        self.auto_respond = auto_respond
        self.running = True
        self.output_handler = None
        self.input_handler = None
        self.reload_handler = None
        self.master_fd = None  # Set when PTY is created

    def _load_modules(self):
        """Load or reload wrapper_core modules."""
        try:
            # Add parent dir to path if needed
            if str(SCRIPT_DIR) not in sys.path:
                sys.path.insert(0, str(SCRIPT_DIR))

            # Import wrapper_core
            import wrapper_core
            from wrapper_core import state
            from wrapper_core.handlers import InputHandler, OutputHandler, ReloadHandler

            # Initialize handlers
            self.output_handler = OutputHandler(
                log_file=self.log_file,
                no_log=self.no_log,
                master_fd=self.master_fd,
                auto_respond=self.auto_respond,
            )
            self.input_handler = InputHandler()
            self.reload_handler = ReloadHandler()

            # Initialize session state
            state.init_session()

            if self.auto_respond:
                print("[Wrapper] Auto-response mode ENABLED", file=sys.stderr)

            return True
        except Exception as e:
            print(f"[Wrapper] Failed to load modules: {e}", file=sys.stderr)
            return False

    def _reload_modules(self):
        """Hot-reload wrapper_core modules."""
        try:
            import wrapper_core

            success, message = wrapper_core.reload_all()

            if success:
                # Reinitialize handlers with new module code
                from wrapper_core.handlers import InputHandler, OutputHandler

                # Preserve state
                old_buffer = self.output_handler.output_buffer if self.output_handler else []
                old_prompts = self.output_handler.prompts_found if self.output_handler else []

                # Create new handlers with preserved settings
                self.output_handler = OutputHandler(
                    log_file=self.log_file,
                    no_log=self.no_log,
                    master_fd=self.master_fd,
                    auto_respond=self.auto_respond,
                )
                self.output_handler.output_buffer = old_buffer
                self.output_handler.prompts_found = old_prompts

                self.input_handler = InputHandler()

                print(f"\n[Wrapper] {message}", file=sys.stderr)
            else:
                print(f"\n[Wrapper] Reload failed: {message}", file=sys.stderr)

            return success
        except Exception as e:
            print(f"\n[Wrapper] Reload error: {e}", file=sys.stderr)
            return False

    def _background_tasks(self):
        """Background thread for periodic tasks."""
        import time

        while self.running:
            time.sleep(1.0)

            # Check for reload signal
            if self.reload_handler and self.reload_handler.check_reload_signal():
                self._reload_modules()

            # Periodic prompt check
            if self.output_handler:
                self.output_handler._check_for_prompts()

    def run(self, claude_args=None):
        """Run Claude Code with wrapper functionality."""
        claude_args = claude_args or []

        # Create pseudo-terminal first so we can pass master_fd to handlers
        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd

        # Load modules (now with master_fd available)
        if not self._load_modules():
            print("[Wrapper] Cannot start without wrapper_core modules", file=sys.stderr)
            os.close(master_fd)
            os.close(slave_fd)
            return 1

        # Start background thread
        bg_thread = Thread(target=self._background_tasks, daemon=True)
        bg_thread.start()

        # Fork process
        pid = os.fork()

        if pid == 0:
            # Child process - run claude
            os.close(master_fd)
            os.setsid()
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            os.close(slave_fd)
            os.execvp("claude", ["claude"] + claude_args)
        else:
            # Parent process - relay I/O
            os.close(slave_fd)

            # Handle window resize
            def handle_winch(signum, frame):
                import fcntl
                import struct
                import termios

                try:
                    ws = struct.pack("HHHH", 0, 0, 0, 0)
                    ws = fcntl.ioctl(0, termios.TIOCGWINSZ, ws)
                    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, ws)
                except:
                    pass

            signal.signal(signal.SIGWINCH, handle_winch)
            handle_winch(None, None)

            # Set stdin to raw mode
            import termios
            import tty

            old_settings = termios.tcgetattr(0)

            try:
                tty.setraw(0)

                while True:
                    rlist, _, _ = select.select([0, master_fd], [], [], 0.1)

                    if 0 in rlist:
                        # User input -> send to claude
                        data = os.read(0, 1024)
                        if data:
                            if self.input_handler:
                                self.input_handler.process_input(data)
                            os.write(master_fd, data)

                    if master_fd in rlist:
                        # Claude output -> display and capture
                        try:
                            data = os.read(master_fd, 1024)
                            if data:
                                os.write(1, data)
                                if self.output_handler:
                                    self.output_handler.process_output(data)
                            else:
                                break
                        except OSError:
                            break

                    # Process any pending auto-responses
                    if self.output_handler and self.auto_respond:
                        self.output_handler.process_pending_response()

                    # Check if child process is still running
                    result = os.waitpid(pid, os.WNOHANG)
                    if result[0] != 0:
                        break

            finally:
                self.running = False
                termios.tcsetattr(0, termios.TCSADRAIN, old_settings)

                # Final cleanup
                if self.output_handler:
                    self.output_handler._check_for_prompts()
                    self.output_handler.save_buffer_to_file()

                # Update state
                try:
                    from wrapper_core import state

                    state.end_session()
                except:
                    pass

                # Wait for child
                try:
                    os.waitpid(pid, 0)
                except:
                    pass

        # Print summary
        prompts_count = len(self.output_handler.prompts_found) if self.output_handler else 0
        print(f"\n[Wrapper] Session ended. {prompts_count} prompt(s) logged.", file=sys.stderr)

        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Claude Code wrapper with hot-reloadable modules",
        epilog="All other arguments are passed to claude",
    )
    parser.add_argument("--log-file", "-l", type=str, help="Custom log file path")
    parser.add_argument("--no-log", action="store_true", help="Disable prompt logging")
    parser.add_argument(
        "--reload", action="store_true", help="Signal running wrapper to reload modules"
    )
    parser.add_argument("--version", "-v", action="store_true", help="Show version info")
    parser.add_argument(
        "--auto-respond",
        "-a",
        action="store_true",
        help="Enable auto-response to permission prompts",
    )
    parser.add_argument(
        "--approve-all", action="store_true", help="Auto-approve ALL prompts (use with caution)"
    )

    args, claude_args = parser.parse_known_args()

    if args.version:
        print(f"Claude Wrapper Shell v{__version__}")
        try:
            import wrapper_core

            info = wrapper_core.get_version()
            print(f"Core v{info['core_version']} (reloaded {info['reload_count']} times)")
        except:
            print("Core: not loaded")
        return 0

    if args.reload:
        return signal_reload()

    # Set approve-all config if requested
    if args.approve_all:
        import wrapper_core.config as cfg

        cfg.AUTO_APPROVE_ALL = True

    wrapper = ThinWrapper(
        log_file=args.log_file,
        no_log=args.no_log,
        auto_respond=args.auto_respond or args.approve_all,
    )

    return wrapper.run(claude_args)


if __name__ == "__main__":
    sys.exit(main())
