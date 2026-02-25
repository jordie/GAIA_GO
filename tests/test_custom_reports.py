"""
Tests for Custom Report Builder Module

Tests the report builder functionality including:
- Data source configuration
- Report CRUD operations
- Query building with filters and aggregations
- JOIN support
- CSV export
- Report templates
- Time range helpers
"""

import json
import os
import sqlite3

# Add parent directory to path for imports
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import reports as custom_reports


class TestReportDataSources:
    """Test data source configuration."""

    def test_data_sources_exist(self):
        """Test that all expected data sources are defined."""
        sources = custom_reports.get_data_sources()
        expected = [
            "projects",
            "milestones",
            "features",
            "bugs",
            "tasks",
            "errors",
            "nodes",
            "workers",
            "activity",
        ]
        for source in expected:
            assert source in sources

    def test_data_source_structure(self):
        """Test that data sources have required fields."""
        sources = custom_reports.get_data_sources()
        for name, config in sources.items():
            assert "table" in config
            assert "fields" in config
            assert "description" in config
            assert isinstance(config["fields"], list)

    def test_data_source_joins(self):
        """Test that JOIN configurations exist."""
        sources = custom_reports.get_data_sources()
        # Projects should have joins to milestones, features, bugs
        assert "joins" in sources["projects"]
        assert "milestones" in sources["projects"]["joins"]


class TestFilterOperators:
    """Test filter operators."""

    def test_operators_defined(self):
        """Test that all standard operators are defined."""
        ops = custom_reports.FILTER_OPERATORS
        expected = ["eq", "ne", "gt", "gte", "lt", "lte", "like", "in", "between"]
        for op in expected:
            assert op in ops

    def test_operator_mapping(self):
        """Test SQL operator mapping."""
        ops = custom_reports.FILTER_OPERATORS
        assert ops["eq"] == "="
        assert ops["ne"] == "!="
        assert ops["gt"] == ">"
        assert ops["like"] == "LIKE"


class TestTimeRanges:
    """Test time range functionality."""

    def test_time_ranges_defined(self):
        """Test that time range presets are defined."""
        ranges = custom_reports.TIME_RANGES
        expected = ["today", "yesterday", "last_7_days", "last_30_days", "this_week"]
        for r in expected:
            assert r in ranges

    def test_get_time_range_dates(self):
        """Test time range date conversion."""
        start, end = custom_reports.get_time_range_dates("today")
        assert start.date() == datetime.now().date()
        assert end >= start

    def test_get_time_range_last_7_days(self):
        """Test last 7 days range."""
        start, end = custom_reports.get_time_range_dates("last_7_days")
        diff = (end - start).days
        assert diff >= 6 and diff <= 7

    def test_apply_time_range_filter(self):
        """Test applying time range filter."""
        filters = []
        filters = custom_reports.apply_time_range_filter(filters, "created_at", "last_30_days")
        assert len(filters) == 1
        assert filters[0]["field"] == "created_at"
        assert filters[0]["operator"] == "between"
        assert len(filters[0]["value"]) == 2


class TestReportCRUD:
    """Test report CRUD operations."""

    @pytest.fixture
    def db_path(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        os.unlink(path)

    @pytest.fixture
    def db_with_schema(self, db_path):
        """Create database with required schema."""
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS custom_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                data_source TEXT NOT NULL,
                columns TEXT,
                filters TEXT,
                config TEXT,
                schedule TEXT,
                owner_id INTEGER,
                is_public INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS report_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL,
                row_count INTEGER DEFAULT 0,
                duration_seconds REAL,
                status TEXT,
                error TEXT,
                run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (report_id) REFERENCES custom_reports(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT
            );

            INSERT INTO users (id, username) VALUES (1, 'testuser');

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY,
                name TEXT,
                description TEXT,
                status TEXT,
                priority INTEGER,
                source_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );

            INSERT INTO projects (id, name, status, priority) VALUES
                (1, 'Project A', 'active', 1),
                (2, 'Project B', 'active', 2),
                (3, 'Project C', 'completed', 3);

            CREATE TABLE IF NOT EXISTS features (
                id INTEGER PRIMARY KEY,
                project_id INTEGER,
                name TEXT,
                status TEXT,
                priority INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            INSERT INTO features (project_id, name, status, priority) VALUES
                (1, 'Feature 1', 'pending', 1),
                (1, 'Feature 2', 'in_progress', 2),
                (2, 'Feature 3', 'completed', 1);

            CREATE TABLE IF NOT EXISTS bugs (
                id INTEGER PRIMARY KEY,
                project_id INTEGER,
                title TEXT,
                status TEXT,
                severity TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            );

            INSERT INTO bugs (project_id, title, status, severity) VALUES
                (1, 'Bug 1', 'open', 'high'),
                (1, 'Bug 2', 'closed', 'low'),
                (2, 'Bug 3', 'open', 'critical');
        """
        )
        conn.commit()
        conn.close()
        return db_path

    def test_create_report(self, db_with_schema):
        """Test creating a new report."""
        conn = sqlite3.connect(db_with_schema)

        report_id = custom_reports.create_report(
            conn,
            name="Test Report",
            data_source="projects",
            columns=[{"field": "name"}, {"field": "status"}],
            owner_id=1,
            description="A test report",
        )
        conn.commit()

        assert report_id is not None
        assert report_id > 0

        report = custom_reports.get_report(conn, report_id)
        assert report["name"] == "Test Report"
        assert report["data_source"] == "projects"
        conn.close()

    def test_get_reports(self, db_with_schema):
        """Test getting all reports."""
        conn = sqlite3.connect(db_with_schema)

        # Create two reports
        custom_reports.create_report(conn, "Report 1", "projects", [], 1)
        custom_reports.create_report(conn, "Report 2", "bugs", [], 1)
        conn.commit()

        reports = custom_reports.get_reports(conn, 1)
        assert len(reports) == 2
        conn.close()

    def test_update_report(self, db_with_schema):
        """Test updating a report."""
        conn = sqlite3.connect(db_with_schema)

        report_id = custom_reports.create_report(conn, "Original Name", "projects", [], 1)
        conn.commit()

        success = custom_reports.update_report(conn, report_id, name="Updated Name")
        conn.commit()

        assert success is True

        report = custom_reports.get_report(conn, report_id)
        assert report["name"] == "Updated Name"
        conn.close()

    def test_delete_report(self, db_with_schema):
        """Test deleting a report."""
        conn = sqlite3.connect(db_with_schema)

        report_id = custom_reports.create_report(conn, "To Delete", "projects", [], 1)
        conn.commit()

        success = custom_reports.delete_report(conn, report_id)
        conn.commit()

        assert success is True

        report = custom_reports.get_report(conn, report_id)
        assert report is None
        conn.close()

    def test_duplicate_report(self, db_with_schema):
        """Test duplicating a report."""
        conn = sqlite3.connect(db_with_schema)

        original_id = custom_reports.create_report(
            conn,
            name="Original Report",
            data_source="projects",
            columns=[{"field": "name"}],
            owner_id=1,
            filters=[{"field": "status", "operator": "eq", "value": "active"}],
        )
        conn.commit()

        new_id = custom_reports.duplicate_report(conn, original_id, "Duplicate Report", 1)
        conn.commit()

        assert new_id != original_id

        original = custom_reports.get_report(conn, original_id)
        duplicate = custom_reports.get_report(conn, new_id)

        assert duplicate["name"] == "Duplicate Report"
        assert duplicate["data_source"] == original["data_source"]
        assert duplicate["columns"] == original["columns"]
        conn.close()


class TestQueryBuilder:
    """Test SQL query building."""

    def test_build_simple_query(self):
        """Test building a simple SELECT query."""
        report = {
            "data_source": "projects",
            "columns": [{"field": "name"}, {"field": "status"}],
            "filters": [],
            "config": {"data_source": "projects"},
        }

        query, params = custom_reports.build_report_query(report)
        assert "SELECT" in query
        assert "FROM projects" in query
        assert "name" in query
        assert "status" in query

    def test_build_query_with_filters(self):
        """Test building query with WHERE filters."""
        report = {
            "data_source": "projects",
            "columns": [{"field": "name"}],
            "filters": [{"field": "status", "operator": "eq", "value": "active"}],
            "config": {"data_source": "projects"},
        }

        query, params = custom_reports.build_report_query(report)
        assert "WHERE" in query
        assert "status" in query
        assert "active" in params

    def test_build_query_with_aggregation(self):
        """Test building query with aggregation."""
        report = {
            "data_source": "projects",
            "columns": [{"field": "*", "aggregate": "COUNT", "alias": "count"}],
            "filters": [],
            "config": {"data_source": "projects"},
        }

        query, params = custom_reports.build_report_query(report)
        assert "COUNT(*)" in query
        assert "AS count" in query

    def test_build_query_with_group_by(self):
        """Test building query with GROUP BY."""
        report = {
            "data_source": "projects",
            "columns": [
                {"field": "status"},
                {"field": "*", "aggregate": "COUNT", "alias": "count"},
            ],
            "filters": [],
            "config": {"data_source": "projects", "group_by": ["status"]},
        }

        query, params = custom_reports.build_report_query(report)
        assert "GROUP BY status" in query

    def test_build_query_with_order_by(self):
        """Test building query with ORDER BY."""
        report = {
            "data_source": "projects",
            "columns": [{"field": "name"}],
            "filters": [],
            "config": {"data_source": "projects", "order_by": [{"field": "name", "desc": False}]},
        }

        query, params = custom_reports.build_report_query(report)
        assert "ORDER BY name ASC" in query

    def test_build_query_with_limit(self):
        """Test building query with LIMIT."""
        report = {
            "data_source": "projects",
            "columns": [{"field": "name"}],
            "filters": [],
            "config": {"data_source": "projects", "limit": 10},
        }

        query, params = custom_reports.build_report_query(report)
        assert "LIMIT 10" in query

    def test_build_query_between_operator(self):
        """Test BETWEEN operator in filters."""
        report = {
            "data_source": "projects",
            "columns": [{"field": "name"}],
            "filters": [{"field": "priority", "operator": "between", "value": [1, 5]}],
            "config": {"data_source": "projects"},
        }

        query, params = custom_reports.build_report_query(report)
        assert "BETWEEN" in query
        assert 1 in params
        assert 5 in params

    def test_build_query_in_operator(self):
        """Test IN operator in filters."""
        report = {
            "data_source": "projects",
            "columns": [{"field": "name"}],
            "filters": [{"field": "status", "operator": "in", "value": ["active", "pending"]}],
            "config": {"data_source": "projects"},
        }

        query, params = custom_reports.build_report_query(report)
        assert "IN" in query
        assert "active" in params
        assert "pending" in params


class TestReportExecution:
    """Test report execution."""

    @pytest.fixture
    def db_with_data(self, tmp_path):
        """Create database with test data."""
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE custom_reports (
                id INTEGER PRIMARY KEY,
                name TEXT,
                description TEXT,
                data_source TEXT,
                columns TEXT,
                filters TEXT,
                config TEXT,
                schedule TEXT,
                owner_id INTEGER,
                is_public INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );

            CREATE TABLE report_runs (
                id INTEGER PRIMARY KEY,
                report_id INTEGER,
                row_count INTEGER,
                duration_seconds REAL,
                status TEXT,
                error TEXT,
                run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT
            );
            INSERT INTO users (id, username) VALUES (1, 'testuser');

            CREATE TABLE projects (
                id INTEGER PRIMARY KEY,
                name TEXT,
                status TEXT,
                priority INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            INSERT INTO projects VALUES
                (1, 'Alpha', 'active', 1, datetime('now')),
                (2, 'Beta', 'active', 2, datetime('now')),
                (3, 'Gamma', 'completed', 3, datetime('now'));
        """
        )
        conn.commit()
        conn.close()
        return db_path

    def test_run_report(self, db_with_data):
        """Test running a report."""
        conn = sqlite3.connect(db_with_data)

        # Create a report
        report_id = custom_reports.create_report(
            conn,
            name="All Projects",
            data_source="projects",
            columns=[{"field": "name"}, {"field": "status"}],
        )
        conn.commit()

        # Run the report
        result = custom_reports.run_report(conn, report_id)
        conn.commit()

        assert "error" not in result or result.get("error") is None
        assert len(result["results"]) == 3
        assert result["row_count"] == 3
        conn.close()

    def test_run_report_with_filters(self, db_with_data):
        """Test running a report with filters."""
        conn = sqlite3.connect(db_with_data)

        report_id = custom_reports.create_report(
            conn,
            name="Active Projects",
            data_source="projects",
            columns=[{"field": "name"}],
            filters=[{"field": "status", "operator": "eq", "value": "active"}],
        )
        conn.commit()

        result = custom_reports.run_report(conn, report_id)
        conn.commit()

        assert len(result["results"]) == 2
        conn.close()

    def test_run_report_with_runtime_filters(self, db_with_data):
        """Test running a report with runtime filters."""
        conn = sqlite3.connect(db_with_data)

        report_id = custom_reports.create_report(
            conn, name="Projects", data_source="projects", columns=[{"field": "name"}]
        )
        conn.commit()

        result = custom_reports.run_report(conn, report_id, runtime_filters={"status": "completed"})
        conn.commit()

        assert len(result["results"]) == 1
        assert result["results"][0]["name"] == "Gamma"
        conn.close()

    def test_preview_report(self, db_with_data):
        """Test previewing a report without saving."""
        conn = sqlite3.connect(db_with_data)

        result = custom_reports.preview_report(
            conn,
            {"data_source": "projects", "columns": [{"field": "name"}], "filters": []},
            limit=2,
        )

        assert result["preview"] is True
        assert len(result["results"]) <= 2
        conn.close()


class TestCSVExport:
    """Test CSV export functionality."""

    def test_export_to_csv(self):
        """Test exporting results to CSV."""
        results = [
            {"name": "Project A", "status": "active"},
            {"name": "Project B", "status": "completed"},
        ]

        csv_str = custom_reports.export_to_csv(results)

        assert "name,status" in csv_str
        assert "Project A,active" in csv_str
        assert "Project B,completed" in csv_str

    def test_export_to_csv_with_columns(self):
        """Test CSV export with custom column headers."""
        results = [{"name": "Alpha", "cnt": 5}]
        columns = [{"field": "name", "alias": "project_name"}, {"field": "cnt", "alias": "count"}]

        csv_str = custom_reports.export_to_csv(results, columns)

        assert "project_name,count" in csv_str

    def test_export_empty_results(self):
        """Test exporting empty results."""
        csv_str = custom_reports.export_to_csv([])
        assert csv_str == ""


class TestReportTemplates:
    """Test report templates."""

    def test_get_templates(self):
        """Test getting available templates."""
        templates = custom_reports.get_report_templates()

        assert len(templates) > 0
        assert "project_summary" in templates
        assert "bug_status_report" in templates

    def test_template_structure(self):
        """Test template structure."""
        templates = custom_reports.get_report_templates()

        for template_id, template in templates.items():
            assert "id" in template
            assert "name" in template
            assert "description" in template
            assert "data_source" in template

    def test_create_from_template(self, tmp_path):
        """Test creating a report from template."""
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE custom_reports (
                id INTEGER PRIMARY KEY,
                name TEXT,
                description TEXT,
                data_source TEXT,
                columns TEXT,
                filters TEXT,
                config TEXT,
                schedule TEXT,
                owner_id INTEGER,
                is_public INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);
            INSERT INTO users VALUES (1, 'testuser');
        """
        )
        conn.commit()

        report_id = custom_reports.create_report_from_template(
            conn, "project_summary", name="My Project Summary", owner_id=1
        )
        conn.commit()

        report = custom_reports.get_report(conn, report_id)

        assert report is not None
        assert report["name"] == "My Project Summary"
        assert report["data_source"] == "projects"
        conn.close()

    def test_create_from_invalid_template(self, tmp_path):
        """Test creating from non-existent template."""
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE custom_reports (
                id INTEGER PRIMARY KEY,
                name TEXT,
                data_source TEXT,
                columns TEXT,
                filters TEXT,
                config TEXT
            )
        """
        )

        with pytest.raises(ValueError):
            custom_reports.create_report_from_template(conn, "nonexistent_template")
        conn.close()


class TestComputedFields:
    """Test computed fields."""

    def test_computed_fields_exist(self):
        """Test that computed fields are defined."""
        fields = custom_reports.get_computed_fields()

        assert "age_days" in fields
        assert "resolution_time_days" in fields
        assert "success_rate" in fields

    def test_computed_field_structure(self):
        """Test computed field structure."""
        fields = custom_reports.get_computed_fields()

        for name, config in fields.items():
            assert "expression" in config
            assert "description" in config


class TestQuickQueries:
    """Test quick query convenience functions."""

    @pytest.fixture
    def db_with_data(self, tmp_path):
        """Create database with test data."""
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY,
                name TEXT,
                status TEXT,
                priority INTEGER
            );

            INSERT INTO projects VALUES
                (1, 'A', 'active', 1),
                (2, 'B', 'active', 2),
                (3, 'C', 'completed', 1);
        """
        )
        conn.commit()
        conn.close()
        return db_path

    def test_quick_count(self, db_with_data):
        """Test quick count query."""
        conn = sqlite3.connect(db_with_data)

        count = custom_reports.quick_count(conn, "projects")
        assert count == 3

        count_filtered = custom_reports.quick_count(
            conn, "projects", [{"field": "status", "operator": "eq", "value": "active"}]
        )
        assert count_filtered == 2
        conn.close()

    def test_quick_aggregate(self, db_with_data):
        """Test quick aggregate query."""
        conn = sqlite3.connect(db_with_data)

        # Count by status
        results = custom_reports.quick_aggregate(conn, "projects", "*", "COUNT", group_by="status")

        assert len(results) == 2  # active and completed
        conn.close()


class TestReportScheduling:
    """Test report scheduling."""

    @pytest.fixture
    def db_with_report(self, tmp_path):
        """Create database with a report."""
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE custom_reports (
                id INTEGER PRIMARY KEY,
                name TEXT,
                description TEXT,
                data_source TEXT,
                columns TEXT,
                filters TEXT,
                config TEXT,
                schedule TEXT,
                owner_id INTEGER,
                is_public INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);
            INSERT INTO users VALUES (1, 'testuser');
        """
        )
        conn.commit()

        custom_reports.create_report(conn, "Scheduled Report", "projects", [], 1)
        conn.commit()
        conn.close()
        return db_path

    def test_schedule_daily_report(self, db_with_report):
        """Test scheduling a daily report."""
        conn = sqlite3.connect(db_with_report)

        success = custom_reports.schedule_report(
            conn, 1, frequency="daily", time_of_day="09:00", recipients=["test@example.com"]
        )
        conn.commit()

        assert success is True

        report = custom_reports.get_report(conn, 1)
        schedule = report.get("schedule")

        assert schedule is not None
        assert schedule["frequency"] == "daily"
        assert schedule["time_of_day"] == "09:00"
        conn.close()

    def test_schedule_weekly_report(self, db_with_report):
        """Test scheduling a weekly report."""
        conn = sqlite3.connect(db_with_report)

        success = custom_reports.schedule_report(
            conn, 1, frequency="weekly", day_of_week=0  # Monday
        )
        conn.commit()

        report = custom_reports.get_report(conn, 1)
        schedule = report.get("schedule")

        assert schedule["frequency"] == "weekly"
        assert schedule["day_of_week"] == 0
        conn.close()


class TestReportHistory:
    """Test report run history."""

    @pytest.fixture
    def db_with_runs(self, tmp_path):
        """Create database with report run history."""
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE custom_reports (
                id INTEGER PRIMARY KEY,
                name TEXT,
                data_source TEXT,
                columns TEXT,
                filters TEXT,
                config TEXT
            );

            CREATE TABLE report_runs (
                id INTEGER PRIMARY KEY,
                report_id INTEGER,
                row_count INTEGER,
                duration_seconds REAL,
                status TEXT,
                error TEXT,
                run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            INSERT INTO custom_reports (id, name, data_source, columns)
            VALUES (1, 'Test Report', 'projects', '[]');

            INSERT INTO report_runs (report_id, row_count, duration_seconds, status)
            VALUES
                (1, 10, 0.5, 'success'),
                (1, 15, 0.6, 'success'),
                (1, 0, 0.1, 'failed');
        """
        )
        conn.commit()
        conn.close()
        return db_path

    def test_get_report_history(self, db_with_runs):
        """Test getting report run history."""
        conn = sqlite3.connect(db_with_runs)

        history = custom_reports.get_report_history(conn, 1)

        assert len(history) == 3
        conn.close()

    def test_get_report_history_limit(self, db_with_runs):
        """Test limiting report history."""
        conn = sqlite3.connect(db_with_runs)

        history = custom_reports.get_report_history(conn, 1, limit=2)

        assert len(history) == 2
        conn.close()


class TestExportImport:
    """Test report export/import."""

    @pytest.fixture
    def db_with_report(self, tmp_path):
        """Create database with a report."""
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE custom_reports (
                id INTEGER PRIMARY KEY,
                name TEXT,
                description TEXT,
                data_source TEXT,
                columns TEXT,
                filters TEXT,
                config TEXT,
                schedule TEXT,
                owner_id INTEGER,
                is_public INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);
            INSERT INTO users VALUES (1, 'testuser'), (2, 'testuser2');
        """
        )

        custom_reports.create_report(
            conn,
            name="Export Test",
            data_source="projects",
            columns=[{"field": "name"}],
            owner_id=1,
            description="Test description",
            filters=[{"field": "status", "operator": "eq", "value": "active"}],
        )
        conn.commit()
        conn.close()
        return db_path

    def test_export_report_config(self, db_with_report):
        """Test exporting report configuration."""
        conn = sqlite3.connect(db_with_report)

        config = custom_reports.export_report_config(conn, 1)

        assert config is not None
        assert config["name"] == "Export Test"
        assert config["data_source"] == "projects"
        assert "exported_at" in config
        assert "version" in config
        conn.close()

    def test_import_report_config(self, db_with_report):
        """Test importing report configuration."""
        conn = sqlite3.connect(db_with_report)

        config = {
            "name": "Imported Report",
            "data_source": "bugs",
            "columns": [{"field": "title"}],
            "filters": [],
        }

        report_id = custom_reports.import_report_config(conn, config, 2)
        conn.commit()

        report = custom_reports.get_report(conn, report_id)

        assert report["name"] == "Imported Report"
        assert report["data_source"] == "bugs"
        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
