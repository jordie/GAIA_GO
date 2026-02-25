#!/usr/bin/env python3
"""Direct AquaTech login automation - step by step"""

import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Start browser
options = Options()
options.add_argument("--start-maximized")
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

username = "jgirmay@gmail.com"
password = "taqX$ZuKU38QgL-"

try:
    print("Step 1: Navigate to AquaTech")
    driver.get("https://www.aquatechswim.com")
    time.sleep(3)
    driver.save_screenshot("/tmp/step1_home.png")
    print("  Screenshot: /tmp/step1_home.png")

    print("\nStep 2: Click CUSTOMER PORTAL")
    driver.find_element(By.LINK_TEXT, "CUSTOMER PORTAL").click()
    time.sleep(3)
    driver.save_screenshot("/tmp/step2_portal.png")
    print("  Screenshot: /tmp/step2_portal.png")
    print(f"  Current URL: {driver.current_url}")

    print("\nStep 2b: Select Alameda Campus")
    # Modal appears - try multiple strategies to click Alameda Campus
    time.sleep(2)  # Wait for modal to fully render

    # First, let's see what elements we can find
    print("  Debugging: Looking for Alameda elements...")
    try:
        all_alameda = driver.find_elements(
            By.XPATH, "//*[contains(text(), 'ALAMEDA') or contains(text(), 'Alameda')]"
        )
        print(f"  Found {len(all_alameda)} elements with Alameda text")
        for i, elem in enumerate(all_alameda):
            print(f"    {i}: {elem.tag_name}, text='{elem.text}', displayed={elem.is_displayed()}")
    except Exception as e:
        print(f"  Debug failed: {e}")

    clicked = False

    # Strategy 1: Find link with exact text "ALAMEDA CAMPUS"
    try:
        print("  Trying: Link with exact text 'ALAMEDA CAMPUS'...")
        alameda_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "ALAMEDA CAMPUS"))
        )
        # Use JavaScript click to avoid potential issues
        driver.execute_script("arguments[0].click();", alameda_btn)
        clicked = True
        print("  ✅ Clicked with exact link text (JavaScript)")
    except Exception as e:
        print(f"    Failed: {e}")

    # Strategy 2: Find link with partial text
    if not clicked:
        try:
            print("  Trying: Partial link text...")
            alameda_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "ALAMEDA"))
            )
            alameda_btn.click()
            clicked = True
            print("  ✅ Clicked with partial link text")
        except Exception as e:
            print(f"    Failed: {e}")

    # Strategy 3: Try finding by class (common button classes)
    if not clicked:
        try:
            print("  Trying: Button with alameda in class or href...")
            alameda_btn = driver.find_element(
                By.XPATH, "//a[contains(@href, 'alameda') or contains(@class, 'alameda')]"
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", alameda_btn)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", alameda_btn)
            clicked = True
            print("  ✅ Clicked with href/class selector")
        except Exception as e:
            print(f"    Failed: {e}")

    # Strategy 4: Click the first clickable element in modal containing Alameda
    if not clicked:
        try:
            print("  Trying: First clickable Alameda element...")
            alameda_elements = driver.find_elements(
                By.XPATH, "//*[contains(., 'ALAMEDA') or contains(., 'Alameda')]"
            )
            for elem in alameda_elements:
                try:
                    if elem.is_displayed() and elem.tag_name in ["a", "button", "div"]:
                        driver.execute_script("arguments[0].click();", elem)
                        clicked = True
                        print(f"  ✅ Clicked {elem.tag_name} element")
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"    Failed: {e}")

    if not clicked:
        raise Exception("Failed to click Alameda Campus button with all strategies")

    time.sleep(5)  # Wait longer for navigation
    driver.save_screenshot("/tmp/step2b_campus.png")
    print("  Screenshot after click: /tmp/step2b_campus.png")
    print(f"  Current URL: {driver.current_url}")

    print("\nStep 2c: Switch to iClassPro iframe")
    try:
        # Wait for iframe to be available and switch to it
        iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "customer-portal"))
        )
        driver.switch_to.frame(iframe)
        print("  ✅ Switched to iframe")
        time.sleep(2)  # Wait for iframe content to load
    except Exception as e:
        print(f"  ❌ Failed to switch to iframe: {e}")
        raise

    print("\nStep 2d: Click LOG IN button (inside iframe)")

    # Debug: Find all buttons/links in iframe
    print("  Debugging: Looking for login elements in iframe...")
    try:
        all_links = driver.find_elements(By.TAG_NAME, "a")
        print(f"  Found {len(all_links)} links in iframe")
        for i, link in enumerate(all_links[:20]):  # First 20
            if link.is_displayed():
                print(f"    {i}: href={link.get_attribute('href')}, text='{link.text}'")
    except Exception as e:
        print(f"  Debug failed: {e}")

    clicked = False

    # Strategy 1: Try button element with LOG IN text
    try:
        print("  Trying: Button with 'LOG IN' text...")
        login_btn = driver.find_element(By.XPATH, "//button[contains(., 'LOG IN')]")
        driver.execute_script("arguments[0].click();", login_btn)
        clicked = True
        print("  ✅ Clicked LOG IN button")
    except Exception:
        pass

    # Strategy 2: Try link containing "Log" (case insensitive)
    if not clicked:
        try:
            print("  Trying: Link containing 'log'...")
            login_btn = driver.find_element(
                By.XPATH, "//a[contains(translate(., 'LOG IN', 'log in'), 'log')]"
            )
            driver.execute_script("arguments[0].click();", login_btn)
            clicked = True
            print("  ✅ Clicked LOG IN link")
        except Exception:
            pass

    # Strategy 3: Try clicking by href containing "login" or "sign"
    if not clicked:
        try:
            print("  Trying: Link with href containing 'login' or 'sign'...")
            login_btn = driver.find_element(
                By.XPATH, "//a[contains(@href, 'login') or contains(@href, 'sign')]"
            )
            driver.execute_script("arguments[0].click();", login_btn)
            clicked = True
            print("  ✅ Clicked login href")
        except Exception:
            pass

    # Strategy 4: Find any clickable element in the middle area that might be the button
    if not clicked:
        try:
            print("  Trying: Click any element with 'Log' text...")
            all_elements = driver.find_elements(
                By.XPATH, "//*[contains(text(), 'Log') or contains(text(), 'LOG')]"
            )
            for elem in all_elements:
                if elem.is_displayed():
                    driver.execute_script("arguments[0].click();", elem)
                    clicked = True
                    print(f"  ✅ Clicked {elem.tag_name} element")
                    break
        except Exception:
            pass

    if not clicked:
        print("  ❌ Could not find LOG IN button, saving page source for analysis...")
        with open("/tmp/portal_page_source.html", "w") as f:
            f.write(driver.page_source)
        print("  Saved page source to: /tmp/portal_page_source.html")
        raise Exception("Failed to find LOG IN button")

    time.sleep(3)
    driver.save_screenshot("/tmp/step2c_login_page.png")
    print("  Screenshot: /tmp/step2c_login_page.png")
    print(f"  Current URL: {driver.current_url}")

    print("\nStep 3: Fill login form")
    # Find email field
    email_field = driver.find_element(
        By.CSS_SELECTOR, 'input[type="email"], input[name="email"], input[id*="email"]'
    )
    email_field.send_keys(username)
    print("  ✅ Filled email")

    # Find password field
    pass_field = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
    pass_field.send_keys(password)
    print("  ✅ Filled password")

    driver.save_screenshot("/tmp/step3_filled.png")
    print("  Screenshot: /tmp/step3_filled.png")

    print("\nStep 4: Submit form")
    submitted = False

    # Strategy 1: Press Enter on password field
    try:
        print("  Trying: Press Enter on password field...")
        from selenium.webdriver.common.keys import Keys

        pass_field.send_keys(Keys.RETURN)
        submitted = True
        print("  ✅ Pressed Enter")
    except Exception as e:
        print(f"    Failed: {e}")

    # Strategy 2: Find and click submit button
    if not submitted:
        try:
            print("  Trying: Find submit button...")
            submit_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"]')
                )
            )
            driver.execute_script("arguments[0].click();", submit_btn)
            submitted = True
            print("  ✅ Clicked submit button")
        except Exception as e:
            print(f"    Failed: {e}")

    # Strategy 3: Look for any button with "Log", "Sign", or "Submit" text
    if not submitted:
        try:
            print("  Trying: Find button with login text...")
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                btn_text = btn.text.lower()
                if any(word in btn_text for word in ["log", "sign", "submit", "enter"]):
                    driver.execute_script("arguments[0].click();", btn)
                    submitted = True
                    print(f"  ✅ Clicked button: {btn.text}")
                    break
        except Exception as e:
            print(f"    Failed: {e}")

    # Strategy 4: Submit the form using JavaScript
    if not submitted:
        try:
            print("  Trying: Submit form with JavaScript...")
            driver.execute_script("document.querySelector('form').submit();")
            submitted = True
            print("  ✅ Submitted form with JavaScript")
        except Exception as e:
            print(f"    Failed: {e}")

    if not submitted:
        print("  ❌ Could not submit form")

    time.sleep(5)
    driver.save_screenshot("/tmp/step4_logged_in.png")
    print("  Screenshot: /tmp/step4_logged_in.png")
    print(f"  Current URL: {driver.current_url}")

    print("\nStep 5: Navigate to My Account")
    try:
        # Find and click My Account link
        my_account_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "My Account"))
        )
        driver.execute_script("arguments[0].click();", my_account_link)
        time.sleep(3)
        driver.save_screenshot("/tmp/step5_my_account.png")
        print("  ✅ Clicked My Account")
        print("  Screenshot: /tmp/step5_my_account.png")
    except Exception as e:
        print(f"  ❌ Failed to click My Account: {e}")

    print("\nStep 6: Extract billing and student information")
    page_text = driver.find_element(By.TAG_NAME, "body").text

    # Save full page text
    with open("/tmp/my_account_page.txt", "w") as f:
        f.write(page_text)
    print("  Saved page text: /tmp/my_account_page.txt")

    # Look for pricing info
    import re

    prices = re.findall(r"\$[\d,]+\.?\d*", page_text)
    print(f"\n💰 Prices found: {prices}")

    # Look for monthly info
    monthly_lines = [line for line in page_text.split("\n") if "month" in line.lower()]
    print("\n📅 Monthly info:")
    for line in monthly_lines[:10]:
        print(f"  - {line}")

    # Look for payment/billing info
    payment_lines = [
        line
        for line in page_text.split("\n")
        if any(word in line.lower() for word in ["payment", "billing", "balance", "due", "total"])
    ]
    print("\n💳 Payment/Billing info:")
    for line in payment_lines[:15]:
        print(f"  - {line}")

    # Look for student/child info
    student_lines = [
        line
        for line in page_text.split("\n")
        if any(
            word in line.lower()
            for word in ["student", "child", "swimmer", "lesson", "saba", "jordan"]
        )
    ]
    print("\n👤 Student/Lesson info:")
    for line in student_lines[:20]:
        print(f"  - {line}")

    print("\n✅ Data extraction complete! Check screenshots and text files for details.")
    print("\n⏸  Browser staying open for 30 seconds...")
    time.sleep(30)

except Exception as e:
    print(f"\n❌ Error: {e}")
    try:
        driver.save_screenshot("/tmp/error.png")
        print("  Error screenshot: /tmp/error.png")
    except Exception:
        print("  (Could not save error screenshot - browser may have closed)")
    import traceback

    traceback.print_exc()

finally:
    try:
        driver.quit()
        print("\n✅ Browser closed")
    except Exception:
        print("\n✅ Browser already closed")
