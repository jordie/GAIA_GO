#!/usr/bin/env python3
"""
Google Voice Setup Helper
Opens browser to Google Voice for manual activation.
"""

import time

from google_voice_sms import GoogleVoiceSMS

print("\n" + "=" * 70)
print("Google Voice Setup - Opening Browser")
print("=" * 70 + "\n")

sms = GoogleVoiceSMS(headless=False)

# Get credentials
creds = sms.get_credentials()
if not creds:
    print("❌ Failed to get credentials")
    exit(1)

print(f"✓ Account: {creds['email']}")

# Initialize browser
if not sms.init_browser():
    print("❌ Failed to initialize browser")
    exit(1)

print("✓ Browser opened\n")

# Navigate to Google Voice
print("📱 Opening Google Voice...\n")
sms.driver.get("https://voice.google.com")
time.sleep(5)

# Check if login needed
if "accounts.google.com" in sms.driver.current_url:
    print("🔐 Logging in...")
    sms.login_google(creds["email"], creds["password"])
    time.sleep(5)

current_url = sms.driver.current_url
print(f"Current page: {current_url}\n")

if "workspace.google.com" in current_url:
    print("=" * 70)
    print("SETUP INSTRUCTIONS")
    print("=" * 70)
    print()
    print("The browser is now open. Follow these steps:")
    print()
    print("1. Click 'Get started' (blue button)")
    print("2. Choose 'For personal use'")
    print("3. Click 'Continue'")
    print("4. Search for area code: 510")
    print("5. Pick a phone number you like")
    print("6. Click 'Select'")
    print("7. Enter forwarding number: 5103886759")
    print("8. Click 'Send code'")
    print("9. Check your phone (5103886759) for the code")
    print("10. Enter the code")
    print("11. Click 'Verify'")
    print()
    print("=" * 70)
    print()
    print("⏳ Browser will stay open for 10 minutes for you to complete setup.")
    print("   The browser will close automatically after that.")
    print()

    # Keep browser open for 10 minutes
    for i in range(10, 0, -1):
        print(f"   Time remaining: {i} minutes...", end="\r")
        time.sleep(60)

    print("\n\n✓ Time's up! Closing browser...")

elif "voice.google.com/messages" in current_url:
    print("✅ Google Voice is already activated!")
    print("\n⏳ Browser will stay open for 2 minutes...")
    time.sleep(120)

sms.close()
print("\n✓ Done!\n")
