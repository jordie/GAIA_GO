#!/usr/bin/env python3
"""
OS-level automation for Comet browser Perplexity sidebar using AppleScript
"""

import subprocess
import time
import sys


def run_applescript(script):
    """Execute AppleScript and return output."""
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            print(f"AppleScript error: {result.stderr}")
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print("AppleScript timed out")
        return None
    except Exception as e:
        print(f"Error running AppleScript: {e}")
        return None


def activate_comet():
    """Activate Comet browser window."""
    script = '''
        tell application "Comet"
            activate
        end tell
    '''
    print("Activating Comet browser...")
    result = run_applescript(script)
    time.sleep(0.5)
    return result is not None


def send_keystroke(key, modifiers=None):
    """Send a keystroke to the frontmost application."""
    if modifiers:
        modifier_str = ' using {' + ', '.join(f'{m} down' for m in modifiers) + '}'
    else:
        modifier_str = ''

    script = f'''
        tell application "System Events"
            keystroke "{key}"{modifier_str}
        end tell
    '''
    return run_applescript(script)


def send_text(text):
    """Type text character by character."""
    # Escape special characters for AppleScript
    text = text.replace('\\', '\\\\').replace('"', '\\"')

    script = f'''
        tell application "System Events"
            keystroke "{text}"
        end tell
    '''
    return run_applescript(script)


def open_perplexity_sidebar():
    """Open Perplexity sidebar with Option+A."""
    print("Opening Perplexity sidebar (Option+A)...")
    send_keystroke("a", ["option"])
    time.sleep(1.5)  # Wait for sidebar to open


def submit_question():
    """Submit the question with Enter."""
    print("Submitting question (Enter)...")
    send_keystroke("\\n")  # Return key


def ask_perplexity(question, wait_for_response=5):
    """
    Ask Perplexity a question via OS automation.

    Args:
        question: The question to ask
        wait_for_response: Seconds to wait for response

    Returns:
        True if successful, False otherwise
    """
    print("=" * 70)
    print("PERPLEXITY OS AUTOMATION")
    print("=" * 70)
    print(f"\nQuestion: {question}\n")

    # Step 1: Activate Comet
    if not activate_comet():
        print("❌ Failed to activate Comet browser")
        print("   Make sure Comet browser is running!")
        return False

    # Step 2: Open Perplexity sidebar
    open_perplexity_sidebar()

    # Step 3: Type the question
    print(f"Typing question...")
    if not send_text(question):
        print("❌ Failed to type question")
        return False

    time.sleep(0.5)

    # Step 4: Submit
    submit_question()

    # Step 5: Wait for response
    print(f"⏳ Waiting {wait_for_response} seconds for response...")
    time.sleep(wait_for_response)

    print("\n✅ Question submitted!")
    print("=" * 70)
    print("\n💡 The response should now be visible in the Perplexity sidebar")
    print("   You can read it in the browser window.\n")

    return True


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        question = ' '.join(sys.argv[1:])
    else:
        question = "What is this page used for?"

    success = ask_perplexity(question, wait_for_response=5)

    if not success:
        print("\n❌ Automation failed!")
        print("\nTroubleshooting:")
        print("   1. Make sure Comet browser is running")
        print("   2. Make sure you're on a webpage (not a blank tab)")
        print("   3. Try opening Perplexity manually (Option+A) to verify it works")
        print("   4. Grant permissions if macOS asks for accessibility access")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
