# HTML Element Extractor - Usage Guide

## Overview

The HTML Element Extractor is a core component of the text-first browser automation system. It extracts actionable elements from web pages and returns them in a minimal JSON format optimized for AI decision-making.

**Key Features:**
- ✅ Extracts only actionable elements (links, buttons, forms, etc.)
- ✅ Returns structured JSON, not raw HTML
- ✅ Maximum 50 items per page (configurable)
- ✅ Performance: <2 seconds per page
- ✅ Supports Selenium and Playwright
- ✅ Fallback HTML parsing if JavaScript fails

## Installation

The extractor is built into the Architect project:

```bash
# Already available at:
/services/html_extractor.py

# Tests available at:
/tests/test_html_extractor.py
```

## Quick Start

### Using Selenium

```python
from selenium import webdriver
from services.html_extractor import extract_selenium

# Create WebDriver and navigate
driver = webdriver.Chrome()
driver.get("https://aquatechswim.com")

# Extract elements
result = extract_selenium(driver)

# Print results
print(f"Page: {result['page_title']}")
print(f"Links found: {len(result['links'])}")
print(f"Forms found: {len(result['forms'])}")
```

### Using Playwright

```python
from playwright.sync_api import sync_playwright
from services.html_extractor import extract_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://aquatechswim.com")

    # Extract elements
    result = extract_playwright(page)

    # Print results
    print(f"Page: {result['page_title']}")
    print(f"Buttons found: {len(result['buttons'])}")
```

## Extraction Output

### Example Output

```json
{
    "page_title": "AquaTech Swimming - Login",
    "current_url": "https://aquatechswim.com/login",
    "extraction_time_ms": 342,
    "elements_count": 8,
    "links": [
        {
            "index": 1,
            "text": "Home",
            "href": "/",
            "id": null
        },
        {
            "index": 2,
            "text": "Programs",
            "href": "/programs",
            "id": null
        }
    ],
    "buttons": [
        {
            "index": 3,
            "text": "Login",
            "id": "login-btn",
            "type": "submit"
        },
        {
            "index": 4,
            "text": "Register",
            "id": "register-btn",
            "type": "button"
        }
    ],
    "forms": [
        {
            "id": "login-form",
            "name": null,
            "fields": [
                {
                    "label": "Email",
                    "name": "email",
                    "type": "email",
                    "required": true
                },
                {
                    "label": "Password",
                    "name": "password",
                    "type": "password",
                    "required": true
                }
            ]
        }
    ],
    "dropdowns": [],
    "tables": [],
    "headings": ["Welcome to AquaTech Swimming"],
    "alerts": []
}
```

## Element Types

### Links
Extracted from `<a href="...">` tags. Includes visible text and href.

```json
{
    "links": [
        {
            "index": 1,
            "text": "Customer Portal",
            "href": "/portal",
            "id": null
        }
    ]
}
```

### Buttons
Extracted from `<button>`, `<input type="button">`, and `<input type="submit">` tags.

```json
{
    "buttons": [
        {
            "index": 5,
            "text": "Submit",
            "id": "submit-btn",
            "type": "submit"
        }
    ]
}
```

### Forms
Extracted from `<form>` tags with all contained input fields.

```json
{
    "forms": [
        {
            "id": "registration",
            "name": "register_form",
            "fields": [
                {
                    "label": "First Name",
                    "name": "first_name",
                    "type": "text",
                    "required": true
                },
                {
                    "label": "Date of Birth",
                    "name": "dob",
                    "type": "date",
                    "required": false
                },
                {
                    "label": "Country",
                    "name": "country",
                    "type": "select",
                    "required": true,
                    "options": ["USA", "Canada", "Mexico"]
                }
            ]
        }
    ]
}
```

### Dropdowns
Extracted from standalone `<select>` tags (not within forms).

```json
{
    "dropdowns": [
        {
            "index": 8,
            "label": "Select Session",
            "name": "session_id",
            "options": ["Monday 9am", "Tuesday 5pm", "Saturday 10am"]
        }
    ]
}
```

### Tables
Extracted from `<table>` tags with header row detection.

```json
{
    "tables": [
        {
            "index": 9,
            "headers": ["Class", "Instructor", "Time", "Spots"],
            "row_count": 12,
            "summary": "4 columns, 12 rows"
        }
    ]
}
```

### Headings
Extracted from `<h1>`, `<h2>`, `<h3>` tags for page context.

```json
{
    "headings": [
        "Welcome to AquaTech Swimming",
        "Register for Classes"
    ]
}
```

### Alerts
Extracted from elements with alert styling (`.alert`, `.error`, `[role="alert"]`).

```json
{
    "alerts": [
        "Your session will expire in 5 minutes"
    ]
}
```

## Text Format for AI

Convert extraction to minimal text format for AI decision-making:

```python
from services.html_extractor import HTMLExtractor

extractor = HTMLExtractor()
result = extract_selenium(driver)

# Convert to text for AI
text_prompt = extractor.to_text_format(result)
print(text_prompt)
```

**Output:**
```
Page: AquaTech Swimming - Login
URL: https://aquatechswim.com/login

Available Actions:
  1. Link: Home
  2. Link: Programs
  3. Link: Schedule
  4. Button: Login
  5. Button: Register
  6. Form with fields: Email, Password
```

This text format is optimized for AI reasoning and keeps data under 200 words.

## Advanced Usage

### Custom Configuration

```python
from services.html_extractor import HTMLExtractor

# Create extractor with custom settings
extractor = HTMLExtractor(
    max_items=100,      # Allow more items
    timeout=5.0         # Longer timeout
)

result = extractor.extract_from_selenium(driver)
```

### Error Handling

```python
from services.html_extractor import HTMLExtractor

extractor = HTMLExtractor()

try:
    result = extractor.extract_from_selenium(driver)
except Exception as e:
    print(f"Extraction failed: {e}")
    # Handle error - maybe take screenshot or retry
```

### Batch Extraction

```python
from services.html_extractor import extract_selenium
from selenium import webdriver

driver = webdriver.Chrome()
urls = [
    "https://aquatechswim.com/login",
    "https://aquatechswim.com/programs",
    "https://aquatechswim.com/schedule"
]

results = []
for url in urls:
    driver.get(url)
    result = extract_selenium(driver)
    results.append(result)

driver.quit()

# Process results
for result in results:
    print(f"Extracted {result['elements_count']} elements from {result['page_title']}")
```

## Integration with Browser Automation

### In the Decision Cascade

```
1. Extract elements → HTMLExtractor.extract_from_selenium()
2. Convert to text → HTMLExtractor.to_text_format()
3. Send to AI → "Which of these actions advances the goal?"
4. Get decision → "Action 4 (Button: Submit)"
5. Execute → driver.find_element_by_id(...).click()
```

### Example Workflow

```python
from services.html_extractor import HTMLExtractor, extract_selenium
from selenium import webdriver

def navigate_to_goal(driver, goal, max_steps=20):
    """Navigate browser to achieve a goal using text-first approach."""

    extractor = HTMLExtractor()

    for step in range(max_steps):
        # Extract current page
        result = extract_selenium(driver)

        # Convert to text format
        text_prompt = extractor.to_text_format(result)

        # Ask AI what to do
        ai_decision = ask_ai(f"Goal: {goal}\n\n{text_prompt}")

        if ai_decision.is_goal_complete():
            return f"Goal achieved in {step} steps"

        if ai_decision.is_error():
            return f"Cannot proceed: {ai_decision.error}"

        # Execute decision
        action = ai_decision.action
        element = driver.find_element_by_xpath(action.xpath)
        element.click()

        # Wait for page load
        driver.implicitly_wait(2)

    return f"Goal not achieved in {max_steps} steps"

# Usage
driver = webdriver.Chrome()
driver.get("https://aquatechswim.com")
result = navigate_to_goal(driver, "Register Eden for Tuesday evening swimming")
print(result)
```

## Performance Characteristics

### Typical Extraction Times

| Page Type | Complexity | Time |
|-----------|-----------|------|
| Simple login | Low | 200-400ms |
| Blog/article | Low | 300-500ms |
| Form-heavy | Medium | 400-800ms |
| Data table | Medium | 500-1000ms |
| Complex dashboard | High | 800-1500ms |

**Target:** <2 seconds per extraction

### Memory Usage

- Per extraction: ~5-10MB
- Per browser: ~100-200MB (Selenium/Playwright overhead)
- Extraction itself: negligible

## Testing

Run the test suite:

```bash
pytest tests/test_html_extractor.py -v
```

Test scenarios covered:
- ✅ Basic element extraction
- ✅ All element types (links, buttons, forms, etc.)
- ✅ Complex forms with various field types
- ✅ Multiple tables on single page
- ✅ Text format conversion
- ✅ JSON serialization
- ✅ Empty pages
- ✅ Performance benchmarks

## Troubleshooting

### Extraction Returns No Elements

**Symptoms:** All arrays are empty

**Causes:**
- Page uses JavaScript to render content (wait for content to load)
- Page is behind authentication
- Elements are hidden/invisible

**Solution:**
```python
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# Wait for specific element to load
wait = WebDriverWait(driver, 10)
wait.until(EC.presence_of_element_located((By.ID, "main-content")))

# Then extract
result = extract_selenium(driver)
```

### JavaScript Extraction Fails

**Symptoms:** Error in console, extraction falls back to HTML parsing

**Solution:**
- Check that JavaScript is enabled
- Page may have CSP restrictions
- Fallback to HTML parsing (automatic)

### Extraction Too Slow

**Symptoms:** Extraction takes >3 seconds

**Solution:**
```python
# Reduce page complexity before extraction
driver.execute_script("document.querySelectorAll('script').forEach(s => s.remove())")
driver.execute_script("document.querySelectorAll('iframe').forEach(i => i.remove())")

# Then extract
result = extract_selenium(driver)
```

## Integration Checklist

- [ ] Add `services/html_extractor.py` to project
- [ ] Run tests: `pytest tests/test_html_extractor.py`
- [ ] Create `workers/browser_automation/` directory
- [ ] Implement `browser_decision.py` (Phase 2)
- [ ] Implement `cache.py` (Phase 2)
- [ ] Integrate with Goal Engine for task generation
- [ ] Integrate with Assigner Worker for distribution

## Next Steps

Once extraction is working:

1. **Phase 2:** Build AI Decision Router (`browser_decision.py`)
2. **Phase 3:** Build Site Knowledge Cache (`cache.py`)
3. **Phase 4:** Build Execution Loop (`runner.py`)
4. **Phase 5:** Build Chrome Extension (optional)

## Support

For issues or improvements:
- Check tests for usage examples
- Review source code comments
- Run in debug mode: add `logging.basicConfig(level=logging.DEBUG)`

