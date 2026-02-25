#!/usr/bin/env python3
"""
Twilio SMS Service
Professional SMS sending via Twilio API - no browser automation needed.
"""

import logging
import sqlite3
import sys
from pathlib import Path

from twilio.rest import Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TwilioSMS")


class TwilioSMS:
    """Send SMS via Twilio API."""

    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.db_path = self.base_path / "data" / "architect.db"

    def get_credentials(self):
        """Get Twilio credentials from vault."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Get Twilio credentials
            cursor.execute(
                """
                SELECT name, encrypted_value
                FROM secrets
                WHERE service = 'twilio'
                ORDER BY name
            """
            )

            creds = {}
            for row in cursor.fetchall():
                name = row[0]
                encrypted = row[1]

                # Decrypt (XOR with 42)
                if isinstance(encrypted, bytes):
                    encrypted = encrypted.decode("utf-8")
                decrypted = "".join(chr(ord(c) ^ 42) for c in encrypted)

                # Map credential names
                if "ACCOUNT_SID" in name.upper():
                    creds["account_sid"] = decrypted
                elif "AUTH_TOKEN" in name.upper():
                    creds["auth_token"] = decrypted
                elif "PHONE" in name.upper() or "NUMBER" in name.upper():
                    creds["from_number"] = decrypted

            conn.close()

            if "account_sid" not in creds or "auth_token" not in creds:
                logger.error("Twilio credentials incomplete")
                return None

            return creds

        except Exception as e:
            logger.error(f"Failed to get credentials: {e}")
            return None

    def send_sms(self, to_number, message):
        """
        Send SMS via Twilio.

        Args:
            to_number: Phone number (E.164 format, e.g., "+15103886759")
            message: Message text

        Returns:
            dict: Result with status and message_sid
        """
        try:
            # Get credentials
            creds = self.get_credentials()
            if not creds:
                return {"success": False, "error": "No credentials found"}

            # Initialize Twilio client
            client = Client(creds["account_sid"], creds["auth_token"])

            # Send message
            logger.info(f"Sending SMS to {to_number}...")
            message_obj = client.messages.create(
                body=message,
                from_=creds.get("from_number", None),  # Will auto-select if not provided
                to=to_number,
            )

            logger.info(f"✓ SMS sent! SID: {message_obj.sid}")

            return {
                "success": True,
                "sid": message_obj.sid,
                "status": message_obj.status,
                "to": message_obj.to,
                "from": message_obj.from_,
            }

        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return {"success": False, "error": str(e)}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Send SMS via Twilio")
    parser.add_argument("to", help="Phone number (E.164 format, e.g., +15103886759)")
    parser.add_argument("message", help="Message text")

    args = parser.parse_args()

    sms = TwilioSMS()
    result = sms.send_sms(args.to, args.message)

    if result["success"]:
        print(f"\n✅ SMS sent successfully!")
        print(f"   SID: {result['sid']}")
        print(f"   To: {result['to']}")
        print(f"   From: {result['from']}")
        print(f"   Status: {result['status']}\n")
        sys.exit(0)
    else:
        print(f"\n❌ Failed to send SMS")
        print(f"   Error: {result['error']}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
