"""
HTML Element Extractor for Browser Automation
Extracts actionable elements from web pages for text-first AI decision making.

This module implements the Layer 2 component of the text-first browser automation
architecture: parsing rendered pages and returning only actionable elements as
structured JSON (not raw HTML).

Features:
- Extract links, buttons, forms, dropdowns, tables
- Return minimal JSON structure suitable for AI reasoning
- Maximum 50 items per page (configurable)
- Support for both Selenium and Playwright
- Performance: <2 seconds per page extraction
"""

import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin
import time

logger = logging.getLogger(__name__)


class HTMLExtractor:
    """
    Extract actionable elements from a web page.

    Supports both Selenium WebDriver and Playwright browser objects.
    """

    def __init__(self, max_items: int = 50, timeout: float = 2.0):
        """
        Initialize the extractor.

        Args:
            max_items: Maximum number of elements to extract (default 50)
            timeout: Maximum time allowed for extraction in seconds
        """
        self.max_items = max_items
        self.timeout = timeout
        self.extracted_count = 0

    def extract_from_selenium(self, driver) -> Dict[str, Any]:
        """
        Extract elements from a Selenium WebDriver instance.

        Args:
            driver: Selenium WebDriver object

        Returns:
            Dictionary with extracted page elements
        """
        start_time = time.time()
        try:
            # Get page metadata
            page_title = driver.title
            current_url = driver.current_url

            # Get rendered HTML
            page_source = driver.page_source

            # Extract elements using JavaScript (more reliable than parsing HTML)
            result = self._extract_elements_js(driver)

            elapsed = time.time() - start_time
            logger.info(f"Extraction completed in {elapsed:.2f}s")

            return {
                "page_title": page_title,
                "current_url": current_url,
                "extraction_time_ms": int(elapsed * 1000),
                "elements_count": len(result),
                **result
            }

        except Exception as e:
            logger.error(f"Error extracting from Selenium: {e}")
            raise

    def extract_from_playwright(self, page) -> Dict[str, Any]:
        """
        Extract elements from a Playwright page object.

        Args:
            page: Playwright page object

        Returns:
            Dictionary with extracted page elements
        """
        start_time = time.time()
        try:
            # Get page metadata
            page_title = page.title()
            current_url = page.url

            # Extract elements using JavaScript
            result = page.evaluate("""
                () => {
                    return window.__extractElements();
                }
            """)

            # Ensure extraction function is loaded
            if not result:
                page.add_init_script(self._get_extraction_script())
                result = page.evaluate("""
                    () => {
                        return window.__extractElements();
                    }
                """)

            elapsed = time.time() - start_time
            logger.info(f"Extraction completed in {elapsed:.2f}s")

            return {
                "page_title": page_title,
                "current_url": current_url,
                "extraction_time_ms": int(elapsed * 1000),
                "elements_count": len(result.get('all_elements', [])),
                **result
            }

        except Exception as e:
            logger.error(f"Error extracting from Playwright: {e}")
            raise

    def _extract_elements_js(self, driver) -> Dict[str, Any]:
        """
        Execute JavaScript to extract actionable elements.
        Works with both Selenium and Playwright via their JavaScript execution.
        """
        extraction_script = self._get_extraction_script()

        try:
            result = driver.execute_script(extraction_script)
            return result
        except Exception as e:
            logger.error(f"JavaScript extraction failed: {e}")
            # Fallback to HTML parsing if JS fails
            return self._extract_elements_html(driver)

    def _get_extraction_script(self) -> str:
        """
        Get the JavaScript extraction script.
        This runs in the browser context to extract elements.
        """
        return """
        window.__extractElements = function() {
            const elements = {};
            const allElements = [];

            // Helper to check if element is visible
            function isVisible(el) {
                if (!el) return false;
                return el.offsetParent !== null && window.getComputedStyle(el).display !== 'none';
            }

            // Helper to get text safely
            function getText(el) {
                return (el?.innerText || el?.textContent || '').trim().substring(0, 100);
            }

            // Extract LINKS
            elements.links = [];
            document.querySelectorAll('a[href]').forEach((link, idx) => {
                if (isVisible(link) && getText(link)) {
                    elements.links.push({
                        index: idx + 1,
                        text: getText(link),
                        href: link.href,
                        id: link.id || null
                    });
                }
            });

            // Extract BUTTONS
            elements.buttons = [];
            document.querySelectorAll('button, input[type="button"], input[type="submit"]').forEach((btn, idx) => {
                if (isVisible(btn)) {
                    elements.buttons.push({
                        index: elements.links.length + idx + 1,
                        text: getText(btn) || btn.value || 'Button',
                        id: btn.id || null,
                        type: btn.type || 'button'
                    });
                }
            });

            // Extract FORMS
            elements.forms = [];
            document.querySelectorAll('form').forEach((form, formIdx) => {
                if (isVisible(form)) {
                    const fields = [];
                    form.querySelectorAll('input, textarea, select').forEach(field => {
                        if (isVisible(field)) {
                            const label = form.querySelector(`label[for="${field.id}"]`)?.textContent?.trim() ||
                                        field.placeholder ||
                                        field.name || '';

                            if (field.tagName === 'SELECT') {
                                fields.push({
                                    label: label,
                                    name: field.name,
                                    type: 'select',
                                    required: field.required,
                                    options: Array.from(field.options).map(o => o.textContent.trim())
                                });
                            } else {
                                fields.push({
                                    label: label,
                                    name: field.name,
                                    type: field.type || 'text',
                                    required: field.required
                                });
                            }
                        }
                    });

                    if (fields.length > 0) {
                        elements.forms.push({
                            index: elements.links.length + elements.buttons.length + formIdx + 1,
                            id: form.id || null,
                            name: form.name || null,
                            fields: fields
                        });
                    }
                }
            });

            // Extract DROPDOWNS (standalone selects)
            elements.dropdowns = [];
            document.querySelectorAll('select:not(form select)').forEach((select, idx) => {
                if (isVisible(select)) {
                    elements.dropdowns.push({
                        index: elements.links.length + elements.buttons.length + elements.forms.length + idx + 1,
                        label: select.previousElementSibling?.textContent?.trim() || select.name || 'Dropdown',
                        name: select.name,
                        options: Array.from(select.options).map(o => o.textContent.trim())
                    });
                }
            });

            // Extract TABLES
            elements.tables = [];
            document.querySelectorAll('table').forEach((table, idx) => {
                if (isVisible(table)) {
                    const headers = Array.from(table.querySelectorAll('thead th, tbody tr:first-child th'))
                        .map(th => getText(th));
                    const rows = table.querySelectorAll('tbody tr').length ||
                               (table.querySelectorAll('tr').length - 1);

                    if (headers.length > 0 || rows > 0) {
                        elements.tables.push({
                            index: elements.links.length + elements.buttons.length +
                                   elements.forms.length + elements.dropdowns.length + idx + 1,
                            headers: headers,
                            row_count: rows,
                            summary: `${headers.length} columns, ${rows} rows`
                        });
                    }
                }
            });

            // Extract HEADINGS (for context)
            elements.headings = [];
            document.querySelectorAll('h1, h2, h3').forEach((heading, idx) => {
                if (isVisible(heading) && getText(heading)) {
                    elements.headings.push(getText(heading));
                }
            });

            // Extract ALERTS/MESSAGES
            elements.alerts = [];
            document.querySelectorAll('.alert, .error, .warning, .success, [role="alert"]')
                .forEach(alert => {
                    const text = getText(alert);
                    if (text) elements.alerts.push(text);
                });

            return elements;
        };

        return window.__extractElements();
        """

    def _extract_elements_html(self, driver) -> Dict[str, Any]:
        """
        Fallback HTML parsing if JavaScript execution fails.
        Uses BeautifulSoup to parse the page.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("BeautifulSoup not installed. Install with: pip install beautifulsoup4")
            return {
                "links": [],
                "buttons": [],
                "forms": [],
                "dropdowns": [],
                "tables": [],
                "headings": [],
                "alerts": [],
                "error": "BeautifulSoup not available"
            }

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        elements = {}

        # Extract links
        elements['links'] = []
        for idx, link in enumerate(soup.find_all('a', href=True)[:10]):
            text = link.get_text(strip=True)
            if text:
                elements['links'].append({
                    "index": idx + 1,
                    "text": text[:100],
                    "href": link['href']
                })

        # Extract buttons
        elements['buttons'] = []
        for idx, button in enumerate(soup.find_all(['button', 'input'], type=['button', 'submit'])[:10]):
            text = button.get_text(strip=True) or button.get('value', 'Button')
            elements['buttons'].append({
                "index": len(elements['links']) + idx + 1,
                "text": text[:100],
                "type": button.get('type', 'button')
            })

        # Extract forms
        elements['forms'] = []
        for form in soup.find_all('form')[:5]:
            fields = []
            for field in form.find_all(['input', 'textarea', 'select']):
                label = field.get('placeholder', field.get('name', 'field'))
                fields.append({
                    "label": label[:50],
                    "name": field.get('name'),
                    "type": field.get('type', 'text')
                })
            if fields:
                elements['forms'].append({
                    "fields": fields
                })

        # Extract dropdowns
        elements['dropdowns'] = []
        for select in soup.find_all('select')[:5]:
            options = [opt.get_text(strip=True) for opt in select.find_all('option')]
            elements['dropdowns'].append({
                "label": select.get('name', 'Dropdown'),
                "options": options
            })

        # Extract tables
        elements['tables'] = []
        for table in soup.find_all('table')[:3]:
            headers = [th.get_text(strip=True) for th in table.find_all('th')]
            rows = len(table.find_all('tr'))
            if headers or rows:
                elements['tables'].append({
                    "headers": headers,
                    "row_count": rows
                })

        # Extract headings
        elements['headings'] = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])[:5]]

        return elements

    def to_text_format(self, extraction: Dict[str, Any]) -> str:
        """
        Convert extraction to minimal text format for AI consumption.
        """
        text = f"Page: {extraction.get('page_title', 'Unknown')}\n"
        text += f"URL: {extraction.get('current_url', '')}\n\n"
        text += "Available Actions:\n"

        index = 1

        # Links
        for link in extraction.get('links', []):
            text += f"  {index}. Link: {link['text']}\n"
            index += 1

        # Buttons
        for button in extraction.get('buttons', []):
            text += f"  {index}. Button: {button['text']}\n"
            index += 1

        # Forms
        for form in extraction.get('forms', []):
            text += f"  {index}. Form with fields: {', '.join([f['label'] for f in form.get('fields', [])])}\n"
            index += 1

        # Dropdowns
        for dropdown in extraction.get('dropdowns', []):
            options = ', '.join(dropdown.get('options', [])[:3])
            text += f"  {index}. Dropdown: {dropdown.get('label', 'Select')} ({options})\n"
            index += 1

        # Tables
        for table in extraction.get('tables', []):
            text += f"  {index}. Table: {table.get('summary', 'Data table')}\n"
            index += 1

        return text


# Convenience functions
def extract_selenium(driver, max_items: int = 50) -> Dict[str, Any]:
    """Extract elements using Selenium WebDriver."""
    extractor = HTMLExtractor(max_items=max_items)
    return extractor.extract_from_selenium(driver)


def extract_playwright(page, max_items: int = 50) -> Dict[str, Any]:
    """Extract elements using Playwright."""
    extractor = HTMLExtractor(max_items=max_items)
    return extractor.extract_from_playwright(page)


if __name__ == "__main__":
    # Example usage
    print("""
    HTML Extractor Module
    ====================

    Usage:
        from services.html_extractor import extract_selenium, extract_playwright

        # With Selenium:
        result = extract_selenium(driver)

        # With Playwright:
        result = extract_playwright(page)

        # Convert to text format for AI:
        text_prompt = HTMLExtractor().to_text_format(result)
    """)
