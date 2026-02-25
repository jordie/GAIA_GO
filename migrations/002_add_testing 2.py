"""
Migration 002: Add Testing and Deployment Tables

This migration adds tables for:
- Test runs and results tracking
- Deployment history with test gates
"""

DESCRIPTION = "Add testing framework and deployment tracking tables"


def upgrade(conn):
    """Apply the migration."""

    # Test Runs table - tracks test execution sessions
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS test_runs (
            id INTEGER PRIMARY KEY,
            run_id TEXT UNIQUE NOT NULL,
            project_id INTEGER,
            environment TEXT,
            triggered_by TEXT,
            trigger_type TEXT DEFAULT 'manual',
            status TEXT DEFAULT 'running',
            total_tests INTEGER DEFAULT 0,
            passed INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            skipped INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            duration_seconds REAL,
            output TEXT,
            category TEXT DEFAULT 'all',
            coverage INTEGER DEFAULT 0,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """
    )

    # Test Results table - individual test outcomes
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL,
            test_name TEXT NOT NULL,
            test_file TEXT,
            test_class TEXT,
            status TEXT NOT NULL,
            duration_seconds REAL,
            error_message TEXT,
            stack_trace TEXT,
            stdout TEXT,
            stderr TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES test_runs(run_id)
        )
    """
    )

    # Deployments table - deployment history with test gates
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deployments (
            id INTEGER PRIMARY KEY,
            deployment_id TEXT UNIQUE NOT NULL,
            project_id INTEGER,
            tag TEXT,
            commit_hash TEXT,
            branch TEXT,
            source_environment TEXT,
            target_environment TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            test_run_id TEXT,
            tests_passed INTEGER DEFAULT 0,
            tests_required INTEGER DEFAULT 1,
            deployed_by TEXT,
            approved_by TEXT,
            notes TEXT,
            error_message TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (test_run_id) REFERENCES test_runs(run_id)
        )
    """
    )

    # Deployment Gates table - defines requirements for each environment
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deployment_gates (
            id INTEGER PRIMARY KEY,
            environment TEXT UNIQUE NOT NULL,
            requires_tests INTEGER DEFAULT 1,
            min_test_pass_rate REAL DEFAULT 100.0,
            requires_approval INTEGER DEFAULT 0,
            approvers TEXT,
            auto_deploy INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Insert default deployment gates
    conn.execute(
        """
        INSERT OR IGNORE INTO deployment_gates (environment, requires_tests, min_test_pass_rate, requires_approval, auto_deploy)
        VALUES
            ('dev', 0, 0.0, 0, 1),
            ('qa', 1, 80.0, 0, 0),
            ('prod', 1, 100.0, 1, 0)
    """
    )

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_test_runs_project ON test_runs(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_test_runs_status ON test_runs(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_test_runs_environment ON test_runs(environment)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_test_results_run ON test_results(run_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_test_results_status ON test_results(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_deployments_project ON deployments(project_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_deployments_environment ON deployments(target_environment)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status)")

    conn.commit()
