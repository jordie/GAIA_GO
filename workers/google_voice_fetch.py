#!/usr/bin/env python3
"""
Google Voice Message Fetcher
Retrieves recent messages from Google Voice web interface.
"""

import logging
import sqlite3
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GoogleVoiceFetch")


def get_credentials():
    """Get Google Voice credentials from vault."""
    try:
        db_path = Path(__file__).parent.parent / "data" / "architect.db"
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


def fetch_messages(limit=10, headless=False):
    """Fetch recent Google Voice messages."""

    creds = get_credentials()
    if not creds:
        print("❌ Failed to get credentials")
        return []

    # Setup Chrome
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Selenium Manager will auto-download verified chromedriver
    from selenium.webdriver.chrome.service import Service

    driver = webdriver.Chrome(service=Service(), options=chrome_options)
    wait = WebDriverWait(driver, 20)

    messages = []

    try:
        # Navigate to Google Voice
        logger.info("Opening Google Voice...")
        driver.get("https://voice.google.com")
        time.sleep(3)

        # Check if login needed
        if (
            "accounts.google.com" in driver.current_url
            or "voice.google.com/u/0/messages" not in driver.current_url
        ):
            logger.info("Logging in...")

            # Enter email
            email_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="email"]'))
            )
            email_input.send_keys(creds["email"])
            email_input.send_keys(Keys.RETURN)
            time.sleep(2)

            # Enter password
            password_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="password"]'))
            )
            password_input.send_keys(creds["password"])
            password_input.send_keys(Keys.RETURN)
            time.sleep(5)

        # Navigate to messages
        driver.get("https://voice.google.com/u/0/messages")
        time.sleep(3)

        logger.info("Fetching messages...")

        # Get message threads
        message_threads = wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "gv-message-list gv-conversation-list-item")
            )
        )

        for i, thread in enumerate(message_threads[:limit]):
            try:
                # Get phone number/name
                name_elem = thread.find_element(By.CSS_SELECTOR, ".contact-name")
                contact = name_elem.text if name_elem else "Unknown"

                # Get message preview
                preview_elem = thread.find_element(By.CSS_SELECTOR, ".message-text")
                preview = preview_elem.text if preview_elem else ""

                # Get timestamp
                time_elem = thread.find_element(By.CSS_SELECTOR, ".relative-time")
                timestamp = time_elem.text if time_elem else ""

                messages.append({"contact": contact, "preview": preview, "time": timestamp})

            except Exception as e:
                logger.warning(f"Error parsing message {i}: {e}")
                continue

        logger.info(f"✓ Fetched {len(messages)} messages")

    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        driver.save_screenshot("/tmp/google_voice_fetch_error.png")

    finally:
        driver.quit()

    return messages


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch Google Voice Messages")
    parser.add_argument("--limit", type=int, default=10, help="Number of messages to fetch")
    parser.add_argument("--headless", action="store_true", help="Run headless")

    args = parser.parse_args()

    messages = fetch_messages(limit=args.limit, headless=args.headless)

    if messages:
        print(f"\n📱 Last {len(messages)} Google Voice Messages:\n")
        print("=" * 80)

        for i, msg in enumerate(messages, 1):
            print(f"\n{i}. From: {msg['contact']}")
            print(f"   Time: {msg['time']}")
            print(f"   Message: {msg['preview']}")
            print("-" * 80)
    else:
        print("\n❌ No messages retrieved")
