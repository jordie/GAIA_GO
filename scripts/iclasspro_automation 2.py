#!/usr/bin/env python3
"""
iClassPro Automated Login and Data Retrieval
Uses Comet browser automation with vault credentials
"""

import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.vault_service import get_login_credentials

COMET_API = "http://localhost:9090"
CDP_ENDPOINT = "http://localhost:9222"


def get_active_tab():
    """Get an active tab from Comet."""
    try:
        response = requests.get(f"{CDP_ENDPOINT}/json", timeout=5)
        tabs = response.json()

        # Find a tab we can use (not chrome:// or devtools://)
        for tab in tabs:
            if tab["type"] == "page" and not tab["url"].startswith(("chrome://", "devtools://")):
                return tab

        # If no suitable tab, return first page
        for tab in tabs:
            if tab["type"] == "page":
                return tab

        return None
    except Exception as e:
        print(f"Error getting tabs: {e}")
        return None


def navigate_to_url(tab_id, url):
    """Navigate to a URL using CDP."""
    try:
        ws_url = f"ws://localhost:9222/devtools/page/{tab_id}"

        # For now, use HTTP commands if available
        # Full implementation would use websocket CDP commands

        print(f"📍 Navigate to: {url}")
        print(f"   Tab ID: {tab_id}")

        # This is a simplified version
        # Full CDP implementation would:
        # 1. Connect to websocket
        # 2. Send Page.navigate command
        # 3. Wait for Page.loadEventFired

        return True
    except Exception as e:
        print(f"Error navigating: {e}")
        return False


def fill_login_form(tab_id, username, password):
    """Fill and submit login form."""
    print(f"📝 Filling login form...")
    print(f"   Username: {username}")
    print(f"   Password: {'*' * len(password)}")

    # CDP commands needed:
    # 1. Runtime.evaluate to execute JavaScript
    # 2. Fill username field
    # 3. Fill password field
    # 4. Click submit button

    js_code = f"""
    (function() {{
        // Find and fill username
        const usernameField = document.querySelector('input[name="email"], input[type="email"], input[name="username"]');
        if (usernameField) {{
            usernameField.value = '{username}';
            usernameField.dispatchEvent(new Event('input', {{ bubbles: true }}));
        }}

        // Find and fill password
        const passwordField = document.querySelector('input[name="password"], input[type="password"]');
        if (passwordField) {{
            passwordField.value = '{password}';
            passwordField.dispatchEvent(new Event('input', {{ bubbles: true }}));
        }}

        // Find and click submit
        const submitBtn = document.querySelector('button[type="submit"], input[type="submit"], button:contains("Log In")');
        if (submitBtn) {{
            setTimeout(() => submitBtn.click(), 500);
            return 'submitted';
        }}

        return 'no_submit_button';
    }})();
    """

    return True


def find_saba_info(tab_id):
    """Find Saba's enrollment time and class level."""
    print(f"🔍 Searching for Saba's information...")

    # JavaScript to search for Saba in the page
    js_code = """
    (function() {
        const results = {
            found: false,
            enrollmentTime: null,
            classLevel: null,
            allText: []
        };

        // Search for "Saba" in the page
        const bodyText = document.body.innerText;
        if (bodyText.toLowerCase().includes('saba')) {
            results.found = true;

            // Try to find enrollment time and class level
            // Look for common patterns
            const timeMatch = bodyText.match(/time[:\\s]*([0-9]{1,2}:[0-9]{2}\\s*[AP]M)/i);
            if (timeMatch) results.enrollmentTime = timeMatch[1];

            const levelMatch = bodyText.match(/level[:\\s]*([A-Z0-9]+)/i);
            if (levelMatch) results.classLevel = levelMatch[1];

            // Get surrounding context
            const lines = bodyText.split('\\n');
            for (let i = 0; i < lines.length; i++) {
                if (lines[i].toLowerCase().includes('saba')) {
                    // Get context lines
                    results.allText.push(...lines.slice(Math.max(0, i-2), Math.min(lines.length, i+3)));
                }
            }
        }

        return results;
    })();
    """

    return None


def main():
    """Main automation flow."""
    print("=" * 70)
    print("iClassPro Automation - Retrieve Saba's Information")
    print("=" * 70)
    print()

    # Step 1: Get credentials from vault
    print("🔐 Step 1: Retrieve credentials from vault...")
    creds = get_login_credentials("iclasspro")

    if not creds or not creds.get("password"):
        print("❌ Credentials not available")
        return False

    print(f"✅ Retrieved: {creds['username']}")

    # Step 2: Check Comet backend
    print("\n🌐 Step 2: Check Comet automation backend...")
    try:
        response = requests.get(f"{COMET_API}/health", timeout=5)
        health = response.json()
        print(f"✅ Backend: {health['service']} - {health['status']}")
    except Exception as e:
        print(f"❌ Comet backend not available: {e}")
        print("\n💡 Quick fix:")
        print("   The Comet browser and backend are running (verified earlier)")
        print("   Use manual login for now with vault credentials\n")
        print("🔑 Login Details:")
        print(f"   URL: {creds['url']}")
        print(f"   Username: {creds['username']}")
        print(f"   Password: (run: python3 scripts/vault_cli.py view iclasspro)")
        print("\n📋 Manual Steps:")
        print("   1. Open URL in Comet browser")
        print("   2. Login with credentials above")
        print("   3. Navigate to Students/Enrollments")
        print("   4. Search for 'Saba'")
        print("   5. Record enrollment time and class level")
        return False

    # Step 3: Get active tab
    print("\n📑 Step 3: Get browser tab...")
    tab = get_active_tab()
    if tab:
        print(f"✅ Tab found: {tab.get('title', 'Unknown')[:50]}")
    else:
        print("❌ No suitable tab available")
        return False

    # Step 4: Navigate to login page
    print("\n📍 Step 4: Navigate to login page...")
    navigate_to_url(tab["id"], creds["url"])

    # Step 5: Fill login form
    print("\n📝 Step 5: Fill login form...")
    fill_login_form(tab["id"], creds["username"], creds["password"])

    # Step 6: Wait for login
    print("\n⏳ Step 6: Waiting for login to complete...")
    time.sleep(3)

    # Step 7: Find Saba's information
    print("\n🔍 Step 7: Searching for Saba's information...")
    info = find_saba_info(tab["id"])

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print("\n⚠️  Automation partially implemented")
    print("Full CDP integration requires websocket connection")
    print("\n🔑 Use vault credentials for manual verification:")
    print(f"   python3 scripts/vault_cli.py view iclasspro")

    return True


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
