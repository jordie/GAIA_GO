#!/usr/bin/env python3
"""
Google Voice SMS Automation
Uses browser automation (not API) to send SMS via Google Voice web interface.
"""

import json
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GoogleVoiceSMS")


class GoogleVoiceSMS:
    """Send SMS via Google Voice web interface using browser automation."""

    def __init__(self, headless=True):
        self.base_path = Path(__file__).parent.parent
        self.headless = headless
        self.driver = None
        self.wait = None

    def get_credentials(self):
        """Get Google Voice credentials from vault."""
        try:
            db_path = self.base_path / "data" / "architect.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Get Google Voice credentials for cs@peraltaservices.net
            cursor.execute(
                """
                SELECT username, encrypted_value
                FROM secrets
                WHERE username = 'cs@peratlatservices.net'
                LIMIT 1
            """
            )

            result = cursor.fetchone()
            conn.close()

            if result:
                email = result[0]
                encrypted = result[1]

                # Decrypt (XOR with 42)
                if isinstance(encrypted, bytes):
                    encrypted = encrypted.decode("utf-8")
                password = "".join(chr(ord(c) ^ 42) for c in encrypted)

                return {"email": email, "password": password}

            return None

        except Exception as e:
            logger.error(f"Failed to get credentials: {e}")
            return None

    def init_browser(self):
        """Initialize Chrome browser."""
        try:
            chrome_options = Options()

            if self.headless:
                chrome_options.add_argument("--headless=new")

            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")

            # Use persistent Chrome profile for cs@peraltaservices.net
            user_data_dir = self.base_path / "data" / "chrome_profile_peraltaservices"
            user_data_dir.mkdir(exist_ok=True)
            chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

            # Selenium Manager will auto-download verified chromedriver
            from selenium.webdriver.chrome.service import Service

            self.driver = webdriver.Chrome(service=Service(), options=chrome_options)
            self.wait = WebDriverWait(self.driver, 20)

            logger.info("✓ Browser initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            return False

    def login_google(self, email, password):
        """Login to Google account."""
        try:
            logger.info("Navigating to Google Voice...")
            self.driver.get("https://voice.google.com")
            time.sleep(3)

            # Check if we need to login
            if "accounts.google.com" in self.driver.current_url:
                logger.info("Logging in...")

                # Enter email
                email_input = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="email"]'))
                )
                email_input.send_keys(email)
                email_input.send_keys(Keys.RETURN)
                time.sleep(2)

                # Enter password
                password_input = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="password"]'))
                )
                password_input.send_keys(password)
                password_input.send_keys(Keys.RETURN)
                time.sleep(5)

            logger.info("✓ Logged in successfully")
            return True

        except Exception as e:
            logger.error(f"Login failed: {e}")
            # Save screenshot for debugging
            try:
                self.driver.save_screenshot("/tmp/google_voice_login_error.png")
                logger.info("Screenshot saved to /tmp/google_voice_login_error.png")
            except:
                pass
            return False

    def send_sms(self, phone_number, message):
        """
        Send SMS via Google Voice web interface.

        Args:
            phone_number: Phone number to send to (e.g., "+1234567890")
            message: Message text to send

        Returns:
            bool: True if successful
        """
        try:
            logger.info(f"Sending SMS to {phone_number}...")

            # Navigate to messages
            self.driver.get("https://voice.google.com/u/0/messages")
            time.sleep(3)

            # Click "New message" button
            new_msg_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '[aria-label="Send new message"]'))
            )
            new_msg_btn.click()
            time.sleep(1)

            # Enter recipient phone number
            recipient_input = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'input[aria-label="Type a name or phone number"]')
                )
            )
            recipient_input.clear()
            recipient_input.send_keys(phone_number)
            time.sleep(1)
            recipient_input.send_keys(Keys.RETURN)
            time.sleep(1)

            # Enter message text
            message_input = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'textarea[aria-label="Type a message"]')
                )
            )
            message_input.clear()
            message_input.send_keys(message)
            time.sleep(1)

            # Click send button
            send_btn = self.driver.find_element(By.CSS_SELECTOR, '[aria-label="Send message"]')
            send_btn.click()

            logger.info("✓ SMS sent successfully")
            time.sleep(2)
            return True

        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            # Take screenshot for debugging
            if self.driver:
                screenshot_path = "/tmp/google_voice_error.png"
                self.driver.save_screenshot(screenshot_path)
                logger.info(f"Screenshot saved to {screenshot_path}")
            return False

    def close(self):
        """Close browser."""
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")

    def send(self, phone_number, message):
        """
        Complete flow: init browser, login, send SMS, close.

        Args:
            phone_number: Phone number to send to
            message: Message text

        Returns:
            bool: True if successful
        """
        try:
            # Get credentials
            creds = self.get_credentials()
            if not creds:
                logger.error("Failed to get credentials")
                return False

            # Initialize browser
            if not self.init_browser():
                return False

            # Login
            if not self.login_google(creds["email"], creds["password"]):
                return False

            # Send SMS
            success = self.send_sms(phone_number, message)

            return success

        except Exception as e:
            logger.error(f"SMS send failed: {e}")
            return False
        finally:
            self.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Google Voice SMS Automation")
    parser.add_argument("phone", help="Phone number to send to (e.g., +1234567890)")
    parser.add_argument("message", help="Message text to send")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")

    args = parser.parse_args()

    sms = GoogleVoiceSMS(headless=not args.no_headless)

    if sms.send(args.phone, args.message):
        print("✓ SMS sent successfully")
        sys.exit(0)
    else:
        print("✗ Failed to send SMS")
        sys.exit(1)


if __name__ == "__main__":
    main()
