#!/usr/bin/env python3
"""
Crawl Results Integration Tests

Tests for Crawl Results Storage system (P06).

Tests the full integration of:
- Crawl results API routes
- Database operations
- JSON serialization/deserialization
- Pagination and filtering
- Statistics aggregation
- Cleanup operations
"""

import json
import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database with crawl_results schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create crawl_results table
    conn.executescript(
        """
        CREATE TABLE crawl_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            start_url TEXT,
            final_url TEXT,
            success BOOLEAN DEFAULT 0,
            extracted_data TEXT,
            action_history TEXT,
            screenshots TEXT,
            error_message TEXT,
            duration_seconds REAL,
            llm_provider TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_crawl_results_task_id ON crawl_results(task_id);
        CREATE INDEX idx_crawl_results_created_at ON crawl_results(created_at);
        CREATE INDEX idx_crawl_results_success ON crawl_results(success);
        CREATE INDEX idx_crawl_results_llm_provider ON crawl_results(llm_provider);
    """
    )
    conn.commit()

    yield conn

    conn.close()


@pytest.fixture
def flask_client(test_db, tmp_path):
    """Create Flask test client with crawl results routes."""
    try:
        from flask import Flask
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))
        from services.crawl_results_routes import crawl_results_bp

        app = Flask(__name__)
        app.config["TESTING"] = True

        # Override DB path for testing
        import services.crawl_results_routes as cr

        cr.DB_PATH = str(tmp_path / "test.db")

        app.register_blueprint(crawl_results_bp)

        return app.test_client()
    except ImportError:
        pytest.skip("Crawl results routes not available")


class TestCrawlResultsAPI:
    """Test crawl results API endpoints."""

    def test_save_result(self, flask_client, test_db):
        """Test saving a crawl result via API."""
        result_data = {
            "task_id": 123,
            "prompt": "Find product prices",
            "start_url": "https://example.com",
            "final_url": "https://example.com/products",
            "success": True,
            "extracted_data": {"price": "$19.99", "product": "Widget"},
            "action_history": [{"action": "click", "element": "button"}],
            "screenshots": ["screenshot1.png"],
            "duration_seconds": 12.5,
            "llm_provider": "claude",
        }

        response = flask_client.post("/api/crawl/results", json=result_data, content_type="application/json")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "id" in data

        # Verify in database
        cursor = test_db.execute("SELECT * FROM crawl_results WHERE task_id = ?", (123,))
        row = cursor.fetchone()
        assert row is not None

    def test_get_result_by_task_id(self, flask_client, test_db):
        """Test retrieving result by task ID."""
        # Insert test data
        test_db.execute(
            """
            INSERT INTO crawl_results (
                task_id, prompt, start_url, success, extracted_data, llm_provider
            ) VALUES (?, ?, ?, ?, ?, ?)
        """,
            (456, "Test prompt", "https://test.com", 1, json.dumps({"key": "value"}), "ollama"),
        )
        test_db.commit()

        response = flask_client.get("/api/crawl/456/result")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["result"]["task_id"] == 456
        assert data["result"]["extracted_data"]["key"] == "value"

    def test_get_result_not_found(self, flask_client):
        """Test retrieving non-existent result."""
        response = flask_client.get("/api/crawl/99999/result")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False

    def test_get_history(self, flask_client, test_db):
        """Test retrieving crawl history."""
        # Insert test data
        for i in range(5):
            test_db.execute(
                """
                INSERT INTO crawl_results (
                    task_id, prompt, success, llm_provider
                ) VALUES (?, ?, ?, ?)
            """,
                (i, f"Prompt {i}", i % 2 == 0, "claude" if i % 2 == 0 else "ollama"),
            )
        test_db.commit()

        response = flask_client.get("/api/crawl/history")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert len(data["results"]) == 5
        assert data["total"] == 5

    def test_get_history_with_filters(self, flask_client, test_db):
        """Test history filtering."""
        # Insert mixed data
        for i in range(10):
            test_db.execute(
                """
                INSERT INTO crawl_results (
                    task_id, prompt, success, llm_provider
                ) VALUES (?, ?, ?, ?)
            """,
                (i, f"Prompt {i}", i < 7, "claude" if i % 2 == 0 else "ollama"),
            )
        test_db.commit()

        # Filter by success
        response = flask_client.get("/api/crawl/history?success=true")
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["total"] == 7  # 7 successful

        # Filter by provider
        response = flask_client.get("/api/crawl/history?llm_provider=claude")
        data = json.loads(response.data)
        assert data["total"] == 5  # 5 with claude (0,2,4,6,8)

    def test_get_history_pagination(self, flask_client, test_db):
        """Test history pagination."""
        # Insert 25 results
        for i in range(25):
            test_db.execute(
                """
                INSERT INTO crawl_results (task_id, prompt, success)
                VALUES (?, ?, ?)
            """,
                (i, f"Prompt {i}", True),
            )
        test_db.commit()

        # Get first page
        response = flask_client.get("/api/crawl/history?limit=10&offset=0")
        data = json.loads(response.data)
        assert len(data["results"]) == 10
        assert data["total"] == 25
        assert data["limit"] == 10
        assert data["offset"] == 0

        # Get second page
        response = flask_client.get("/api/crawl/history?limit=10&offset=10")
        data = json.loads(response.data)
        assert len(data["results"]) == 10
        assert data["offset"] == 10

        # Get third page (partial)
        response = flask_client.get("/api/crawl/history?limit=10&offset=20")
        data = json.loads(response.data)
        assert len(data["results"]) == 5  # Only 5 remaining

    def test_get_stats(self, flask_client, test_db):
        """Test statistics endpoint."""
        # Insert test data
        test_data = [
            (1, True, 10.0, "claude"),
            (2, True, 15.0, "claude"),
            (3, False, 5.0, "ollama"),
            (4, True, 20.0, "ollama"),
            (5, False, 8.0, "claude"),
        ]

        for task_id, success, duration, provider in test_data:
            test_db.execute(
                """
                INSERT INTO crawl_results (
                    task_id, prompt, success, duration_seconds, llm_provider
                ) VALUES (?, ?, ?, ?, ?)
            """,
                (task_id, f"Prompt {task_id}", success, duration, provider),
            )
        test_db.commit()

        response = flask_client.get("/api/crawl/stats")

        assert response.status_code == 200
        data = json.loads(response.data)
        stats = data["stats"]

        assert stats["total_crawls"] == 5
        assert stats["successful_crawls"] == 3
        assert stats["failed_crawls"] == 2
        assert stats["success_rate"] == 60.0

        # Check by provider
        assert "claude" in stats["by_provider"]
        assert "ollama" in stats["by_provider"]
        assert stats["by_provider"]["claude"]["count"] == 3
        assert stats["by_provider"]["ollama"]["count"] == 2

    def test_delete_result(self, flask_client, test_db):
        """Test deleting a result."""
        # Insert test data
        cursor = test_db.execute(
            """
            INSERT INTO crawl_results (task_id, prompt, success)
            VALUES (?, ?, ?)
        """,
            (789, "Test prompt", True),
        )
        result_id = cursor.lastrowid
        test_db.commit()

        # Delete via API
        response = flask_client.delete(f"/api/crawl/{result_id}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

        # Verify deleted
        cursor = test_db.execute("SELECT * FROM crawl_results WHERE id = ?", (result_id,))
        assert cursor.fetchone() is None

    def test_cleanup_old_results(self, flask_client, test_db):
        """Test cleanup of old results."""
        # Insert old results
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        recent_date = datetime.now().isoformat()

        test_db.execute(
            """
            INSERT INTO crawl_results (task_id, prompt, success, created_at)
            VALUES (1, 'Old', 1, ?), (2, 'Old', 1, ?), (3, 'Recent', 1, ?)
        """,
            (old_date, old_date, recent_date),
        )
        test_db.commit()

        # Cleanup results older than 30 days
        response = flask_client.post("/api/crawl/cleanup", json={"days": 30}, content_type="application/json")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["deleted_count"] == 2  # 2 old results

        # Verify recent result still exists
        cursor = test_db.execute("SELECT COUNT(*) FROM crawl_results")
        count = cursor.fetchone()[0]
        assert count == 1


class TestCrawlResultsJSONHandling:
    """Test JSON serialization and deserialization."""

    def test_complex_extracted_data(self, flask_client, test_db):
        """Test storing and retrieving complex extracted data."""
        complex_data = {
            "products": [
                {"name": "Product 1", "price": 19.99, "in_stock": True},
                {"name": "Product 2", "price": 29.99, "in_stock": False},
            ],
            "metadata": {"page": 1, "total_pages": 5, "results_per_page": 20},
        }

        result_data = {
            "task_id": 100,
            "prompt": "Extract products",
            "success": True,
            "extracted_data": complex_data,
        }

        # Save via API
        response = flask_client.post("/api/crawl/results", json=result_data, content_type="application/json")
        assert response.status_code == 200

        # Retrieve and verify
        response = flask_client.get("/api/crawl/100/result")
        data = json.loads(response.data)

        retrieved_data = data["result"]["extracted_data"]
        assert len(retrieved_data["products"]) == 2
        assert retrieved_data["products"][0]["name"] == "Product 1"
        assert retrieved_data["metadata"]["page"] == 1

    def test_action_history_array(self, flask_client):
        """Test storing action history as array."""
        actions = [
            {"step": 1, "action": "navigate", "url": "https://example.com"},
            {"step": 2, "action": "click", "element": "#login-button"},
            {"step": 3, "action": "type", "element": "#username", "value": "user@test.com"},
            {"step": 4, "action": "submit", "element": "#login-form"},
        ]

        result_data = {
            "task_id": 200,
            "prompt": "Login workflow",
            "success": True,
            "action_history": actions,
        }

        # Save
        response = flask_client.post("/api/crawl/results", json=result_data, content_type="application/json")
        assert response.status_code == 200

        # Retrieve
        response = flask_client.get("/api/crawl/200/result")
        data = json.loads(response.data)

        history = data["result"]["action_history"]
        assert len(history) == 4
        assert history[0]["action"] == "navigate"
        assert history[2]["value"] == "user@test.com"

    def test_empty_json_fields(self, flask_client):
        """Test handling of empty JSON fields."""
        result_data = {
            "task_id": 300,
            "prompt": "Test empty fields",
            "success": False,
            "extracted_data": {},  # Empty dict
            "action_history": [],  # Empty array
            "screenshots": [],  # Empty array
        }

        # Save
        response = flask_client.post("/api/crawl/results", json=result_data, content_type="application/json")
        assert response.status_code == 200

        # Retrieve
        response = flask_client.get("/api/crawl/300/result")
        data = json.loads(response.data)

        assert data["result"]["extracted_data"] == {}
        assert data["result"]["action_history"] == []
        assert data["result"]["screenshots"] == []


class TestCrawlResultsStatistics:
    """Test statistics and aggregation."""

    def test_success_rate_calculation(self, flask_client, test_db):
        """Test success rate calculation."""
        # Insert 100 results: 85 successful, 15 failed
        for i in range(100):
            test_db.execute(
                """
                INSERT INTO crawl_results (task_id, prompt, success)
                VALUES (?, ?, ?)
            """,
                (i, f"Prompt {i}", i < 85),  # First 85 are successful
            )
        test_db.commit()

        response = flask_client.get("/api/crawl/stats")
        data = json.loads(response.data)
        stats = data["stats"]

        assert stats["total_crawls"] == 100
        assert stats["successful_crawls"] == 85
        assert stats["failed_crawls"] == 15
        assert stats["success_rate"] == 85.0

    def test_average_duration(self, flask_client, test_db):
        """Test average duration calculation."""
        durations = [10.0, 15.0, 20.0, 25.0, 30.0]  # Average = 20.0

        for i, duration in enumerate(durations):
            test_db.execute(
                """
                INSERT INTO crawl_results (
                    task_id, prompt, success, duration_seconds
                ) VALUES (?, ?, ?, ?)
            """,
                (i, f"Prompt {i}", True, duration),
            )
        test_db.commit()

        response = flask_client.get("/api/crawl/stats")
        data = json.loads(response.data)
        stats = data["stats"]

        assert stats["avg_duration_seconds"] == 20.0

    def test_provider_statistics(self, flask_client, test_db):
        """Test per-provider statistics."""
        # Insert results with different providers and success rates
        providers_data = [
            ("claude", True, 10),  # 10 successful claude
            ("claude", False, 2),  # 2 failed claude
            ("ollama", True, 8),  # 8 successful ollama
            ("ollama", False, 4),  # 4 failed ollama
        ]

        task_id = 0
        for provider, success, count in providers_data:
            for _ in range(count):
                test_db.execute(
                    """
                    INSERT INTO crawl_results (
                        task_id, prompt, success, llm_provider
                    ) VALUES (?, ?, ?, ?)
                """,
                    (task_id, f"Prompt {task_id}", success, provider),
                )
                task_id += 1
        test_db.commit()

        response = flask_client.get("/api/crawl/stats")
        data = json.loads(response.data)
        by_provider = data["stats"]["by_provider"]

        # Claude: 10/12 = 83.3%
        assert by_provider["claude"]["count"] == 12
        assert by_provider["claude"]["success_rate"] == 83.3

        # Ollama: 8/12 = 66.7%
        assert by_provider["ollama"]["count"] == 12
        assert by_provider["ollama"]["success_rate"] == 66.7


class TestCrawlResultsPerformance:
    """Test performance characteristics."""

    def test_bulk_insert_performance(self, flask_client, test_db):
        """Test bulk insert of many results."""
        import time

        start_time = time.time()

        # Insert 100 results
        for i in range(100):
            result_data = {
                "task_id": i,
                "prompt": f"Prompt {i}",
                "success": True,
                "llm_provider": "claude",
            }
            flask_client.post("/api/crawl/results", json=result_data, content_type="application/json")

        duration = time.time() - start_time

        # Should complete in reasonable time (< 10 seconds)
        assert duration < 10.0

        # Verify all inserted
        cursor = test_db.execute("SELECT COUNT(*) FROM crawl_results")
        count = cursor.fetchone()[0]
        assert count == 100

    def test_large_json_storage(self, flask_client):
        """Test storing large JSON data."""
        # Create large extracted data (1000 items)
        large_data = {"items": [{"id": i, "name": f"Item {i}", "value": i * 10} for i in range(1000)]}

        result_data = {
            "task_id": 9999,
            "prompt": "Extract large dataset",
            "success": True,
            "extracted_data": large_data,
        }

        # Should handle large JSON
        response = flask_client.post("/api/crawl/results", json=result_data, content_type="application/json")
        assert response.status_code == 200

        # Retrieve and verify
        response = flask_client.get("/api/crawl/9999/result")
        data = json.loads(response.data)

        assert len(data["result"]["extracted_data"]["items"]) == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
