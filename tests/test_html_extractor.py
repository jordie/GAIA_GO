"""
Unit tests for HTML Element Extractor
Tests extraction accuracy on different page types
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.html_extractor import HTMLExtractor, extract_selenium, extract_playwright


class TestHTMLExtractor:
    """Test suite for HTMLExtractor"""

    @pytest.fixture
    def extractor(self):
        """Create extractor instance"""
        return HTMLExtractor(max_items=50, timeout=2.0)

    @pytest.fixture
    def mock_selenium_driver(self):
        """Mock Selenium WebDriver"""
        driver = Mock()
        driver.title = "Test Page"
        driver.current_url = "https://example.com/test"
        driver.page_source = "<html><body><h1>Test</h1></body></html>"

        # Mock JavaScript extraction result
        driver.execute_script = Mock(return_value={
            "links": [
                {"index": 1, "text": "Home", "href": "/"},
                {"index": 2, "text": "About", "href": "/about"}
            ],
            "buttons": [
                {"index": 3, "text": "Submit", "id": "submit-btn", "type": "submit"}
            ],
            "forms": [
                {
                    "id": "login-form",
                    "fields": [
                        {"label": "Username", "name": "username", "type": "text", "required": True},
                        {"label": "Password", "name": "password", "type": "password", "required": True}
                    ]
                }
            ],
            "dropdowns": [
                {"label": "Select Option", "name": "options", "options": ["Option A", "Option B", "Option C"]}
            ],
            "tables": [
                {"headers": ["Name", "Email", "Action"], "row_count": 5, "summary": "3 columns, 5 rows"}
            ],
            "headings": ["Welcome", "Getting Started"],
            "alerts": ["Successfully logged in"]
        })

        return driver

    def test_extractor_initialization(self, extractor):
        """Test extractor initialization"""
        assert extractor.max_items == 50
        assert extractor.timeout == 2.0

    def test_extract_from_selenium_basic(self, extractor, mock_selenium_driver):
        """Test basic Selenium extraction"""
        result = extractor.extract_from_selenium(mock_selenium_driver)

        assert result["page_title"] == "Test Page"
        assert result["current_url"] == "https://example.com/test"
        assert "extraction_time_ms" in result
        assert len(result["links"]) == 2
        assert len(result["buttons"]) == 1

    def test_extract_links(self, extractor, mock_selenium_driver):
        """Test link extraction"""
        result = extractor.extract_from_selenium(mock_selenium_driver)
        links = result["links"]

        assert len(links) == 2
        assert links[0]["text"] == "Home"
        assert links[0]["href"] == "/"
        assert links[1]["text"] == "About"

    def test_extract_buttons(self, extractor, mock_selenium_driver):
        """Test button extraction"""
        result = extractor.extract_from_selenium(mock_selenium_driver)
        buttons = result["buttons"]

        assert len(buttons) == 1
        assert buttons[0]["text"] == "Submit"
        assert buttons[0]["type"] == "submit"

    def test_extract_forms(self, extractor, mock_selenium_driver):
        """Test form extraction"""
        result = extractor.extract_from_selenium(mock_selenium_driver)
        forms = result["forms"]

        assert len(forms) == 1
        assert len(forms[0]["fields"]) == 2
        assert forms[0]["fields"][0]["label"] == "Username"
        assert forms[0]["fields"][0]["required"] == True

    def test_extract_dropdowns(self, extractor, mock_selenium_driver):
        """Test dropdown extraction"""
        result = extractor.extract_from_selenium(mock_selenium_driver)
        dropdowns = result["dropdowns"]

        assert len(dropdowns) == 1
        assert dropdowns[0]["label"] == "Select Option"
        assert len(dropdowns[0]["options"]) == 3
        assert "Option A" in dropdowns[0]["options"]

    def test_extract_tables(self, extractor, mock_selenium_driver):
        """Test table extraction"""
        result = extractor.extract_from_selenium(mock_selenium_driver)
        tables = result["tables"]

        assert len(tables) == 1
        assert len(tables[0]["headers"]) == 3
        assert tables[0]["row_count"] == 5

    def test_extract_headings(self, extractor, mock_selenium_driver):
        """Test heading extraction"""
        result = extractor.extract_from_selenium(mock_selenium_driver)
        headings = result["headings"]

        assert len(headings) == 2
        assert "Welcome" in headings

    def test_extract_alerts(self, extractor, mock_selenium_driver):
        """Test alert extraction"""
        result = extractor.extract_from_selenium(mock_selenium_driver)
        alerts = result["alerts"]

        assert len(alerts) == 1
        assert "Successfully logged in" in alerts

    def test_to_text_format(self, extractor, mock_selenium_driver):
        """Test conversion to text format for AI"""
        result = extractor.extract_from_selenium(mock_selenium_driver)
        text = extractor.to_text_format(result)

        assert "Page: Test Page" in text
        assert "Available Actions:" in text
        assert "Link: Home" in text
        assert "Button: Submit" in text
        assert "Dropdown: Select Option" in text

    def test_json_serializable(self, extractor, mock_selenium_driver):
        """Test that extraction result is JSON serializable"""
        result = extractor.extract_from_selenium(mock_selenium_driver)

        # Should not raise exception
        json_str = json.dumps(result)
        assert json_str is not None

        # Should be deserializable
        parsed = json.loads(json_str)
        assert parsed["page_title"] == "Test Page"

    def test_max_items_limit(self):
        """Test max items configuration"""
        extractor_small = HTMLExtractor(max_items=10)
        assert extractor_small.max_items == 10

        extractor_large = HTMLExtractor(max_items=100)
        assert extractor_large.max_items == 100

    def test_extraction_time_recorded(self, extractor, mock_selenium_driver):
        """Test that extraction time is recorded"""
        result = extractor.extract_from_selenium(mock_selenium_driver)

        assert "extraction_time_ms" in result
        assert isinstance(result["extraction_time_ms"], int)
        assert result["extraction_time_ms"] >= 0

    def test_convenience_functions(self, mock_selenium_driver):
        """Test convenience wrapper functions"""
        result = extract_selenium(mock_selenium_driver)
        assert result["page_title"] == "Test Page"

    def test_empty_page(self, extractor):
        """Test extraction on empty page"""
        driver = Mock()
        driver.title = "Empty Page"
        driver.current_url = "https://example.com/empty"
        driver.execute_script = Mock(return_value={
            "links": [],
            "buttons": [],
            "forms": [],
            "dropdowns": [],
            "tables": [],
            "headings": [],
            "alerts": []
        })

        result = extractor.extract_from_selenium(driver)

        assert result["page_title"] == "Empty Page"
        assert len(result["links"]) == 0
        assert len(result["buttons"]) == 0

    def test_complex_form_extraction(self, extractor):
        """Test complex form with various field types"""
        driver = Mock()
        driver.title = "Complex Form"
        driver.current_url = "https://example.com/form"
        driver.execute_script = Mock(return_value={
            "links": [],
            "buttons": [],
            "forms": [
                {
                    "id": "complex-form",
                    "fields": [
                        {"label": "First Name", "name": "first_name", "type": "text", "required": True},
                        {"label": "Email", "name": "email", "type": "email", "required": True},
                        {"label": "Date", "name": "date", "type": "date", "required": False},
                        {"label": "Message", "name": "message", "type": "textarea", "required": False},
                        {"label": "Country", "name": "country", "type": "select", "required": True,
                         "options": ["USA", "Canada", "Mexico"]}
                    ]
                }
            ],
            "dropdowns": [],
            "tables": [],
            "headings": [],
            "alerts": []
        })

        result = extractor.extract_from_selenium(driver)
        form = result["forms"][0]

        assert len(form["fields"]) == 5
        assert form["fields"][0]["type"] == "text"
        assert form["fields"][1]["type"] == "email"
        assert form["fields"][2]["type"] == "date"
        assert form["fields"][3]["type"] == "textarea"
        assert form["fields"][4]["options"] == ["USA", "Canada", "Mexico"]

    def test_multiple_tables_extraction(self, extractor):
        """Test extraction of multiple tables"""
        driver = Mock()
        driver.title = "Tables Page"
        driver.current_url = "https://example.com/tables"
        driver.execute_script = Mock(return_value={
            "links": [],
            "buttons": [],
            "forms": [],
            "dropdowns": [],
            "tables": [
                {"headers": ["ID", "Name"], "row_count": 10, "summary": "2 columns, 10 rows"},
                {"headers": ["Date", "Amount", "Status"], "row_count": 5, "summary": "3 columns, 5 rows"},
                {"headers": ["Product", "Price", "Qty", "Total"], "row_count": 20, "summary": "4 columns, 20 rows"}
            ],
            "headings": [],
            "alerts": []
        })

        result = extractor.extract_from_selenium(driver)
        tables = result["tables"]

        assert len(tables) == 3
        assert tables[0]["row_count"] == 10
        assert tables[1]["row_count"] == 5
        assert tables[2]["row_count"] == 20

    def test_text_format_preserves_data(self, extractor, mock_selenium_driver):
        """Test that text format preserves all important data"""
        result = extractor.extract_from_selenium(mock_selenium_driver)
        text = extractor.to_text_format(result)

        # All elements should appear in text
        assert "Link: Home" in text
        assert "Button: Submit" in text
        assert "Form with fields" in text
        assert "Dropdown: Select Option" in text
        assert "Table:" in text

        # Should be readable
        lines = text.split("\n")
        assert len(lines) > 5


class TestExtractionScenarios:
    """Test real-world extraction scenarios"""

    def test_aquatech_login_page(self):
        """Test extraction on AquaTech-like login page"""
        extractor = HTMLExtractor()
        driver = Mock()
        driver.title = "AquaTech Swimming - Login"
        driver.current_url = "https://aquatechswim.com/login"
        driver.execute_script = Mock(return_value={
            "links": [
                {"index": 1, "text": "Home", "href": "/"},
                {"index": 2, "text": "Programs", "href": "/programs"},
                {"index": 3, "text": "Schedule", "href": "/schedule"},
                {"index": 4, "text": "Contact", "href": "/contact"}
            ],
            "buttons": [
                {"index": 5, "text": "Login", "id": "login-btn", "type": "submit"},
                {"index": 6, "text": "Register", "id": "register-btn", "type": "button"}
            ],
            "forms": [
                {
                    "id": "login-form",
                    "fields": [
                        {"label": "Email", "name": "email", "type": "email", "required": True},
                        {"label": "Password", "name": "password", "type": "password", "required": True}
                    ]
                }
            ],
            "dropdowns": [],
            "tables": [],
            "headings": ["Welcome to AquaTech Swimming"],
            "alerts": []
        })

        result = extractor.extract_from_selenium(driver)

        assert result["page_title"] == "AquaTech Swimming - Login"
        assert len(result["links"]) == 4
        assert len(result["buttons"]) == 2
        assert len(result["forms"]) == 1

        text = extractor.to_text_format(result)
        assert "Login" in text
        assert "Register" in text

    def test_google_forms_like_page(self):
        """Test extraction on form-heavy page"""
        extractor = HTMLExtractor()
        driver = Mock()
        driver.title = "Survey Form"
        driver.current_url = "https://example.com/survey"
        driver.execute_script = Mock(return_value={
            "links": [],
            "buttons": [
                {"index": 1, "text": "Submit", "type": "submit"}
            ],
            "forms": [
                {
                    "id": "survey-form",
                    "fields": [
                        {"label": "Name", "name": "name", "type": "text", "required": True},
                        {"label": "Email", "name": "email", "type": "email", "required": True},
                        {"label": "How satisfied are you?", "name": "satisfaction", "type": "select",
                         "options": ["Very Satisfied", "Satisfied", "Neutral", "Dissatisfied"]},
                        {"label": "Comments", "name": "comments", "type": "textarea", "required": False}
                    ]
                }
            ],
            "dropdowns": [],
            "tables": [],
            "headings": ["Customer Satisfaction Survey"],
            "alerts": []
        })

        result = extractor.extract_from_selenium(driver)

        assert len(result["forms"]) == 1
        form = result["forms"][0]
        assert len(form["fields"]) == 4


class TestExtractionPerformance:
    """Test extraction performance"""

    def test_extraction_completes_quickly(self):
        """Test that extraction completes within timeout"""
        import time

        extractor = HTMLExtractor(timeout=2.0)
        driver = Mock()
        driver.title = "Performance Test"
        driver.current_url = "https://example.com/perf"

        # Simulate complex page with many elements
        driver.execute_script = Mock(return_value={
            "links": [{"index": i, "text": f"Link {i}", "href": f"/link/{i}"} for i in range(1, 21)],
            "buttons": [{"index": i+20, "text": f"Button {i}", "type": "button"} for i in range(1, 11)],
            "forms": [],
            "dropdowns": [],
            "tables": [],
            "headings": [],
            "alerts": []
        })

        start = time.time()
        result = extractor.extract_from_selenium(driver)
        elapsed = time.time() - start

        # Should complete in reasonable time
        assert elapsed < 1.0  # Should be much faster than timeout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
