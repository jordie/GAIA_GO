#!/usr/bin/env python3
"""
Test iClassPro Login with Vault Credentials
Retrieve Saba's enrollment information from Aquatech Alameda
"""

import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.vault_service import get_login_credentials


def test_iclasspro_login():
    """Test login and retrieve Saba's information."""

    print("🔐 Retrieving credentials from vault...")
    creds = get_login_credentials("iclasspro")

    if not creds or not creds.get("password"):
        print("❌ iClassPro credentials not found or password not set")
        print("   Run: python3 scripts/vault_cli.py add iclasspro")
        return False

    print(f"✅ Credentials retrieved")
    print(f"   Username: {creds['username']}")
    print(f"   URL: {creds['url']}")

    # Check if Comet backend is available
    print("\n🌐 Checking Comet automation backend...")
    try:
        response = requests.get("http://localhost:9090/health", timeout=5)
        if response.status_code == 200:
            print("✅ Comet backend is running")
        else:
            print("⚠️  Comet backend responded but not healthy")
            return False
    except Exception as e:
        print(f"❌ Comet backend not available: {e}")
        print("   Start Comet in debug mode first")
        return False

    print("\n📋 Automation Task:")
    print("   1. Navigate to iClassPro login page")
    print("   2. Fill username and password from vault")
    print("   3. Submit login form")
    print("   4. Navigate to student/enrollment information")
    print("   5. Find Saba's enrollment time and class level")

    # For now, we'll use CDP commands via Comet backend
    # This would integrate with the Comet API we discovered

    print("\n⚠️  Manual verification needed:")
    print(f"   1. Open Comet browser")
    print(f"   2. Navigate to: {creds['url']}")
    print(f"   3. Login with username: {creds['username']}")
    print(f"   4. Password available in vault (use: vault_cli.py view iclasspro)")
    print(f"   5. Look for 'Saba' in students/enrollments")
    print(f"   6. Record enrollment time and class level")

    # TODO: Full automation implementation
    # This would require:
    # - CDP protocol commands via Comet backend
    # - DOM selection and form filling
    # - Navigation and waiting for page loads
    # - Scraping the enrollment information

    return True


def automated_login_via_cdp():
    """
    Future: Full automated login using CDP protocol

    This would send commands to Comet backend at port 9090
    to control the browser, fill forms, and scrape data.
    """
    pass


if __name__ == "__main__":
    print("=" * 60)
    print("iClassPro Login Test - Vault Credential Verification")
    print("=" * 60)
    print()

    success = test_iclasspro_login()

    if success:
        print("\n✅ Vault credential test setup complete")
        print("   Next: Implement full CDP automation")
    else:
        print("\n❌ Test setup failed")
        sys.exit(1)
