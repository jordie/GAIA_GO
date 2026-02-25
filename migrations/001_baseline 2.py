"""
Migration 001: Baseline Schema

This migration represents the initial database schema.
It creates all core tables if they don't exist, preserving any existing data.
"""

DESCRIPTION = "Baseline schema - creates all core tables"


def upgrade(conn):
    """Apply the migration."""

    # Users table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """
    )

    # Projects table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            source_path TEXT,
            status TEXT DEFAULT 'active',
            priority INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Milestones table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY,
            project_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            target_date DATE,
            status TEXT DEFAULT 'open',
            progress INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """
    )

    # Features table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS features (
            id INTEGER PRIMARY KEY,
            project_id INTEGER,
            milestone_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            spec TEXT,
            status TEXT DEFAULT 'draft',
            priority INTEGER DEFAULT 0,
            assigned_to TEXT,
            assigned_node TEXT,
            tmux_session TEXT,
            estimated_hours REAL,
            actual_hours REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (milestone_id) REFERENCES milestones(id)
        )
    """
    )

    # Bugs table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bugs (
            id INTEGER PRIMARY KEY,
            project_id INTEGER,
            milestone_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            severity TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'open',
            source_node TEXT,
            source_error_id INTEGER,
            assigned_to TEXT,
            assigned_node TEXT,
            tmux_session TEXT,
            stack_trace TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (milestone_id) REFERENCES milestones(id)
        )
    """
    )

    # DevOps Tasks table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS devops_tasks (
            id INTEGER PRIMARY KEY,
            project_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            task_type TEXT,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 0,
            assigned_node TEXT,
            tmux_session TEXT,
            schedule TEXT,
            last_run TIMESTAMP,
            next_run TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """
    )

    # Nodes table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY,
            hostname TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            ssh_port INTEGER DEFAULT 22,
            ssh_user TEXT,
            role TEXT DEFAULT 'worker',
            status TEXT DEFAULT 'offline',
            services TEXT,
            cpu_usage REAL,
            memory_usage REAL,
            disk_usage REAL,
            last_heartbeat TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # tmux Sessions table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tmux_sessions (
            id INTEGER PRIMARY KEY,
            node_id TEXT,
            session_name TEXT NOT NULL,
            window_count INTEGER DEFAULT 1,
            attached INTEGER DEFAULT 0,
            purpose TEXT,
            assigned_task_type TEXT,
            assigned_task_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (node_id) REFERENCES nodes(id),
            UNIQUE(node_id, session_name)
        )
    """
    )

    # Errors table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY,
            project_id INTEGER,
            node_id TEXT,
            error_type TEXT,
            message TEXT,
            source TEXT,
            line INTEGER,
            column_num INTEGER,
            stack_trace TEXT,
            url TEXT,
            user_agent TEXT,
            http_status INTEGER,
            context TEXT,
            status TEXT DEFAULT 'open',
            assigned_bug_id INTEGER,
            occurrence_count INTEGER DEFAULT 1,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (node_id) REFERENCES nodes(id),
            FOREIGN KEY (assigned_bug_id) REFERENCES bugs(id)
        )
    """
    )

    # Task Queue table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS task_queue (
            id INTEGER PRIMARY KEY,
            task_type TEXT NOT NULL,
            task_data TEXT,
            priority INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            assigned_node TEXT,
            assigned_worker TEXT,
            retries INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """
    )

    # Workers table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workers (
            id TEXT PRIMARY KEY,
            node_id TEXT,
            worker_type TEXT NOT NULL,
            status TEXT DEFAULT 'offline',
            current_task_id INTEGER,
            last_heartbeat TIMESTAMP,
            tasks_completed INTEGER DEFAULT 0,
            tasks_failed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (node_id) REFERENCES nodes(id),
            FOREIGN KEY (current_task_id) REFERENCES task_queue(id)
        )
    """
    )

    # Activity Log table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """
    )

    # Resource Allocations table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS resource_allocations (
            id INTEGER PRIMARY KEY,
            resource_type TEXT NOT NULL,
            requester TEXT NOT NULL,
            node_id TEXT,
            priority INTEGER DEFAULT 0,
            allocated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            released_at TIMESTAMP,
            metadata TEXT,
            FOREIGN KEY (node_id) REFERENCES nodes(id)
        )
    """
    )

    # Create indexes for performance
    conn.execute("CREATE INDEX IF NOT EXISTS idx_features_project ON features(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_features_milestone ON features(milestone_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_features_status ON features(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bugs_project ON bugs(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bugs_status ON bugs(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_project ON errors(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_status ON errors(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_node ON errors(node_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_queue_status ON task_queue(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_log_created ON activity_log(created_at)")

    conn.commit()
