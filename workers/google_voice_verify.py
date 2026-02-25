#!/usr/bin/env python3
"""
Google Voice Account Verification
Checks if Google Voice is activated and shows current status.
"""

import logging
import sys
from pathlib import Path

from google_voice_sms import GoogleVoiceSMS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GoogleVoiceVerify")


def verify_account():
    """Verify Google Voice account status."""
    sms = GoogleVoiceSMS(headless=False)

    try:
        # Get credentials
        creds = sms.get_credentials()
        if not creds:
            print("❌ Failed to get credentials from vault")
            return False

        print(f"✓ Found credentials for: {creds['email']}")

        # Initialize browser
        if not sms.init_browser():
            print("❌ Failed to initialize browser")
            return False

        print("✓ Browser initialized")

        # Navigate to Google Voice
        sms.driver.get("https://voice.google.com")
        import time

        time.sleep(5)

        current_url = sms.driver.current_url
        print(f"\n📍 Current URL: {current_url}")

        # Check status
        if "workspace.google.com" in current_url:
            print("\n❌ Google Voice NOT ACTIVATED")
            print("   The account is redirecting to Google Workspace signup.")
            print("\n   To fix:")
            print("   1. Log into https://voice.google.com manually")
            print(f"   2. Use account: {creds['email']}")
            print("   3. Complete Google Voice setup (choose a phone number)")
            print("   4. Re-run this script to verify\n")
            status = False

        elif (
            "voice.google.com/u/0/messages" in current_url
            or "voice.google.com/messages" in current_url
        ):
            print("\n✅ Google Voice IS ACTIVATED!")
            print("   SMS automation is ready to use.")

            # Try to detect phone number
            try:
                page_source = sms.driver.page_source
                if "gv-number" in page_source or "phone" in page_source.lower():
                    print("   ✓ Google Voice number detected")
            except:
                pass

            status = True

        elif "accounts.google.com" in current_url:
            print("\n⚠️  Stuck on login page")
            print("   Login may have failed or requires 2FA")
            status = False

        else:
            print(f"\n⚠️  Unknown status - at: {current_url}")
            status = False

        # Take screenshot
        screenshot_path = "/tmp/google_voice_verify.png"
        sms.driver.save_screenshot(screenshot_path)
        print(f"\n📸 Screenshot saved: {screenshot_path}")

        input("\nPress Enter to close browser...")
        return status

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return False
    finally:
        sms.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Google Voice Account Verification")
    print("=" * 60 + "\n")

    if verify_account():
        print("\n✅ Verification successful - SMS automation ready!")
        sys.exit(0)
    else:
        print("\n❌ Verification failed - manual setup required")
        sys.exit(1)
