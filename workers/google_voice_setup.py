#!/usr/bin/env python3
"""
Google Voice Setup Assistant
Guides user through activating Google Voice for cs@peratlatservices.net
"""

import logging
import sys
import time
from pathlib import Path

from google_voice_sms import GoogleVoiceSMS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GoogleVoiceSetup")


def main():
    print("=" * 70)
    print("Google Voice Setup Assistant")
    print("=" * 70)
    print()
    print("This will help you activate Google Voice for: cs@peratlatservices.net")
    print()

    sms = GoogleVoiceSMS(headless=False)  # Browser visible

    try:
        # Get credentials
        creds = sms.get_credentials()
        if not creds:
            print("❌ Failed to get credentials from vault")
            return False

        print(f"✓ Credentials loaded")
        print(f"  Email: {creds['email']}")
        print(f"  Password: {'*' * 8}")
        print()

        # Initialize browser
        if not sms.init_browser():
            print("❌ Failed to initialize browser")
            return False

        print("✓ Browser opened")
        print()

        # Navigate to Google Voice
        print("📱 Navigating to Google Voice...")
        sms.driver.get("https://voice.google.com")
        time.sleep(3)

        current_url = sms.driver.current_url
        print(f"   Current URL: {current_url}")
        print()

        # Check if login is needed
        if "accounts.google.com" in current_url:
            print("🔐 Logging in...")
            if not sms.login_google(creds["email"], creds["password"]):
                print("❌ Login failed")
                return False
            print("✓ Login successful")
            time.sleep(3)
            current_url = sms.driver.current_url

        # Check current status
        if "workspace.google.com" in current_url:
            print()
            print("=" * 70)
            print("📋 MANUAL SETUP REQUIRED")
            print("=" * 70)
            print()
            print("The browser is now open and showing the Google Voice signup page.")
            print()
            print("FOLLOW THESE STEPS IN THE BROWSER:")
            print()
            print("1. Click 'Get started' or 'Sign In' button")
            print("2. Choose 'For personal use' (if asked)")
            print("3. Click 'Continue' to proceed")
            print("4. Select a phone number:")
            print("   - Enter desired area code (e.g., 510 for Bay Area)")
            print("   - Or search by city name")
            print("   - Select a number from the list")
            print("5. Click 'Select' to choose the number")
            print("6. Enter a forwarding phone number:")
            print("   - This is YOUR real phone for verification")
            print("   - Enter the number: 5103886759")
            print("   - Click 'Send code'")
            print("7. Check your phone for verification code")
            print("8. Enter the code in the browser")
            print("9. Click 'Verify'")
            print("10. Complete any remaining setup steps")
            print()
            print("=" * 70)
            print()

            input("Press Enter AFTER you've completed the setup above...")
            print()

            # Refresh and check again
            print("🔄 Checking if setup is complete...")
            sms.driver.get("https://voice.google.com/u/0/messages")
            time.sleep(3)
            current_url = sms.driver.current_url

            if (
                "voice.google.com/u/0/messages" in current_url
                or "voice.google.com/messages" in current_url
            ):
                print()
                print("=" * 70)
                print("✅ SUCCESS! Google Voice is now activated!")
                print("=" * 70)
                print()

                # Take screenshot
                sms.driver.save_screenshot("/tmp/google_voice_activated.png")
                print("📸 Screenshot saved: /tmp/google_voice_activated.png")
                print()

                # Test SMS
                print("🧪 Testing SMS functionality...")
                test_result = input("Do you want to send a test SMS to +15103886759? (y/n): ")

                if test_result.lower() == "y":
                    print()
                    print("📤 Sending test SMS...")
                    if sms.send_sms(
                        "+15103886759",
                        "🎉 Google Voice SMS is working! Sent from Architect Dashboard.",
                    ):
                        print()
                        print("=" * 70)
                        print("✅ TEST SMS SENT SUCCESSFULLY!")
                        print("=" * 70)
                        print()
                        print("Check your phone for the message.")
                        print()
                        return True
                    else:
                        print("⚠️  SMS sending failed. Let me show you the browser...")
                        input("Press Enter to close...")
                        return False
                else:
                    print("✓ Setup complete. You can test SMS later with:")
                    print("  python3 workers/google_voice_sms.py '+15103886759' 'Test message'")
                    print()
                    return True
            else:
                print()
                print("⚠️  Setup may not be complete yet.")
                print(f"   Current URL: {current_url}")
                print()
                print("Please check the browser and complete all setup steps.")
                input("Press Enter to close...")
                return False

        elif (
            "voice.google.com/u/0/messages" in current_url
            or "voice.google.com/messages" in current_url
        ):
            print()
            print("=" * 70)
            print("✅ Google Voice ALREADY ACTIVATED!")
            print("=" * 70)
            print()
            print("The account already has Google Voice set up.")
            print()

            # Test SMS
            test_result = input("Do you want to send a test SMS to +15103886759? (y/n): ")

            if test_result.lower() == "y":
                print()
                print("📤 Sending test SMS...")
                if sms.send_sms(
                    "+15103886759", "🎉 Google Voice SMS is working! Sent from Architect Dashboard."
                ):
                    print()
                    print("=" * 70)
                    print("✅ TEST SMS SENT SUCCESSFULLY!")
                    print("=" * 70)
                    print()
                    print("Check your phone for the message.")
                    print()
                    return True
                else:
                    print("❌ SMS sending failed")
                    input("Press Enter to close...")
                    return False
            else:
                return True

    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        return False
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        print()
        input("Press Enter to close browser...")
        sms.close()


if __name__ == "__main__":
    print()
    success = main()
    print()

    if success:
        print("🎉 Setup complete! Google Voice SMS is ready to use.")
        print()
        print("Quick Start:")
        print("  # Send SMS")
        print("  python3 workers/google_voice_sms.py '+15103886759' 'Your message'")
        print()
        print("  # Fetch messages")
        print("  python3 workers/google_voice_fetch.py --limit 10")
        print()
        sys.exit(0)
    else:
        print("❌ Setup incomplete. Please try again or use alternative SMS service.")
        sys.exit(1)
