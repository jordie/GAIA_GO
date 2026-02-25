#!/usr/bin/env python3
"""
Dialpad SMS Client - Adapted for Architect Dashboard
Send SMS via Dialpad API
"""

import logging
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Optional

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DialpadSMS")


class DialpadSMS:
    """Send SMS via Dialpad API."""

    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.db_path = self.base_path / "data" / "architect.db"
        self.api_key = self._get_api_key()
        self.api_url = "https://dialpad.com/api/v2"

    def _get_api_key(self) -> str:
        """Get Dialpad API key from vault."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT encrypted_value
                FROM secrets
                WHERE name = 'DIALPAD_API_KEY'
                LIMIT 1
            """
            )

            result = cursor.fetchone()
            conn.close()

            if result:
                encrypted = result[0]
                if isinstance(encrypted, bytes):
                    encrypted = encrypted.decode("utf-8")
                # Decrypt (XOR with 42)
                api_key = "".join(chr(ord(c) ^ 42) for c in encrypted)
                return api_key

            logger.error("Dialpad API key not found in vault")
            return ""

        except Exception as e:
            logger.error(f"Failed to get API key: {e}")
            return ""

    def _headers(self) -> Dict[str, str]:
        """Get API headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get_user_id(self) -> str:
        """Get Dialpad user ID."""
        try:
            response = requests.get(f"{self.api_url}/users", headers=self._headers(), timeout=10)
            response.raise_for_status()
            users = response.json().get("items", [])
            if users:
                return users[0].get("id")
        except Exception as e:
            logger.error(f"Failed to get user ID: {e}")
        return ""

    def send_sms(self, to_number: str, message: str, from_number: str = None) -> Optional[Dict]:
        """
        Send SMS via Dialpad API.

        Args:
            to_number: Phone number (E.164 format, e.g., "+15103886759")
            message: Message text
            from_number: Optional from number

        Returns:
            dict: API response with success status
        """
        if not self.api_key:
            return {"success": False, "error": "No API key configured"}

        # Get user_id for sending
        user_id = self._get_user_id()
        if not user_id:
            return {"success": False, "error": "No Dialpad user ID found"}

        url = f"{self.api_url}/sms"
        data = {"to_numbers": [to_number], "text": message, "user_id": user_id}  # API expects array

        if from_number:
            data["from_number"] = from_number

        try:
            logger.info(f"Sending SMS to {to_number} via Dialpad...")
            response = requests.post(url, headers=self._headers(), json=data, timeout=30)
            response.raise_for_status()

            result = response.json() if response.content else {}
            logger.info(f"✓ SMS sent successfully!")

            return {"success": True, "response": result, "to": to_number, "message": message}

        except requests.exceptions.HTTPError as e:
            logger.error(f"Dialpad API error: {e}")
            logger.error(f"Response: {e.response.text if hasattr(e, 'response') else 'N/A'}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return {"success": False, "error": str(e)}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Send SMS via Dialpad")
    parser.add_argument("to", help="Phone number (E.164 format, e.g., +15103886759)")
    parser.add_argument("message", help="Message text")
    parser.add_argument("--from", dest="from_number", help="From number (optional)")

    args = parser.parse_args()

    sms = DialpadSMS()
    result = sms.send_sms(args.to, args.message, args.from_number)

    if result["success"]:
        print(f"\n✅ SMS sent successfully via Dialpad!")
        print(f"   To: {result['to']}")
        print(f"   Message: {result['message']}\n")
        sys.exit(0)
    else:
        print(f"\n❌ Failed to send SMS")
        print(f"   Error: {result['error']}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
