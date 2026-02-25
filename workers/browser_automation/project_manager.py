#!/usr/bin/env python3
"""
Project management system for browser automation
Orchestrates tab groups, Google Sheets, and Google Docs for project tracking
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path


class ProjectManager:
    def __init__(self, db_path="browser_projects.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Projects table - top level organization
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                template TEXT,
                google_sheet_id TEXT,
                google_doc_id TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tab groups within projects
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tab_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                chrome_group_id INTEGER,
                name TEXT NOT NULL,
                color TEXT,
                description TEXT,
                position INTEGER,
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                sheet_row INTEGER,
                notes TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        ''')

        # Tabs within tab groups
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tabs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tab_group_id INTEGER NOT NULL,
                chrome_tab_id INTEGER,
                url TEXT NOT NULL,
                title TEXT,
                position INTEGER,
                last_data_extracted TEXT,
                extracted_at TIMESTAMP,
                FOREIGN KEY (tab_group_id) REFERENCES tab_groups(id) ON DELETE CASCADE
            )
        ''')

        # Extracted data from tabs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS extracted_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tab_id INTEGER NOT NULL,
                data_type TEXT,
                data JSON,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tab_id) REFERENCES tabs(id) ON DELETE CASCADE
            )
        ''')

        # Project templates
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                tab_group_schema JSON,
                sheet_columns JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Data sync log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                sync_type TEXT,
                status TEXT,
                message TEXT,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        conn.close()

    def create_project(self, name, description="", template=None):
        """Create a new project."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO projects (name, description, template)
                VALUES (?, ?, ?)
                """,
                (name, description, template)
            )
            project_id = cursor.lastrowid
            conn.commit()
            return project_id
        except sqlite3.IntegrityError:
            # Project exists
            cursor.execute("SELECT id FROM projects WHERE name = ?", (name,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def create_tab_group(self, project_id, name, description="", color=None, position=None):
        """Create a tab group within a project."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO tab_groups
            (project_id, name, description, color, position)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, name, description, color, position)
        )

        tab_group_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return tab_group_id

    def add_tab_to_group(self, tab_group_id, url, title="", chrome_tab_id=None):
        """Add a tab to a tab group."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO tabs (tab_group_id, url, title, chrome_tab_id)
            VALUES (?, ?, ?, ?)
            """,
            (tab_group_id, url, title, chrome_tab_id)
        )

        tab_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return tab_id

    def update_tab_group_progress(self, tab_group_id, progress, status=None):
        """Update tab group progress."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if status:
            cursor.execute(
                """
                UPDATE tab_groups
                SET progress = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (progress, status, tab_group_id)
            )
        else:
            cursor.execute(
                """
                UPDATE tab_groups
                SET progress = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (progress, tab_group_id)
            )

        conn.commit()
        conn.close()

    def save_extracted_data(self, tab_id, data, data_type="general"):
        """Save extracted data from a tab."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO extracted_data (tab_id, data_type, data)
            VALUES (?, ?, ?)
            """,
            (tab_id, data_type, json.dumps(data))
        )

        # Update tab's last extracted data
        cursor.execute(
            """
            UPDATE tabs
            SET last_data_extracted = ?, extracted_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(data), tab_id)
        )

        conn.commit()
        conn.close()

    def get_project(self, name):
        """Get project details with all tab groups and tabs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get project
        cursor.execute(
            """
            SELECT id, name, description, template, google_sheet_id,
                   google_doc_id, status, created_at, updated_at
            FROM projects
            WHERE name = ?
            """,
            (name,)
        )

        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        project = {
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'template': row[3],
            'google_sheet_id': row[4],
            'google_doc_id': row[5],
            'status': row[6],
            'created_at': row[7],
            'updated_at': row[8],
            'tab_groups': []
        }

        # Get tab groups
        cursor.execute(
            """
            SELECT id, chrome_group_id, name, color, description,
                   position, status, progress, sheet_row, notes
            FROM tab_groups
            WHERE project_id = ?
            ORDER BY position
            """,
            (project['id'],)
        )

        for tg_row in cursor.fetchall():
            tab_group = {
                'id': tg_row[0],
                'chrome_group_id': tg_row[1],
                'name': tg_row[2],
                'color': tg_row[3],
                'description': tg_row[4],
                'position': tg_row[5],
                'status': tg_row[6],
                'progress': tg_row[7],
                'sheet_row': tg_row[8],
                'notes': tg_row[9],
                'tabs': []
            }

            # Get tabs in group
            cursor.execute(
                """
                SELECT id, chrome_tab_id, url, title, position,
                       last_data_extracted, extracted_at
                FROM tabs
                WHERE tab_group_id = ?
                ORDER BY position
                """,
                (tab_group['id'],)
            )

            for tab_row in cursor.fetchall():
                tab_group['tabs'].append({
                    'id': tab_row[0],
                    'chrome_tab_id': tab_row[1],
                    'url': tab_row[2],
                    'title': tab_row[3],
                    'position': tab_row[4],
                    'last_data_extracted': tab_row[5],
                    'extracted_at': tab_row[6]
                })

            project['tab_groups'].append(tab_group)

        conn.close()
        return project

    def list_projects(self):
        """List all projects."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT p.name, p.description, p.status, p.updated_at,
                   COUNT(DISTINCT tg.id) as group_count,
                   COUNT(DISTINCT t.id) as tab_count,
                   AVG(tg.progress) as avg_progress
            FROM projects p
            LEFT JOIN tab_groups tg ON p.id = tg.project_id
            LEFT JOIN tabs t ON tg.id = t.tab_group_id
            GROUP BY p.id
            ORDER BY p.updated_at DESC
            """
        )

        projects = [
            {
                'name': row[0],
                'description': row[1],
                'status': row[2],
                'updated_at': row[3],
                'group_count': row[4],
                'tab_count': row[5],
                'avg_progress': int(row[6]) if row[6] else 0
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return projects

    def create_template(self, name, description, tab_groups, sheet_columns):
        """
        Create a project template.

        tab_groups: [{"name": "Tickets", "description": "Flight search", "color": "blue"}, ...]
        sheet_columns: ["Task", "Status", "Progress", "Notes", "Links"]
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO templates (name, description, tab_group_schema, sheet_columns)
                VALUES (?, ?, ?, ?)
                """,
                (name, description, json.dumps(tab_groups), json.dumps(sheet_columns))
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def create_project_from_template(self, project_name, template_name):
        """Create a new project from a template."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get template
        cursor.execute(
            "SELECT tab_group_schema FROM templates WHERE name = ?",
            (template_name,)
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        tab_groups = json.loads(row[0])

        # Create project
        project_id = self.create_project(project_name, template=template_name)

        # Create tab groups from template
        for i, tg in enumerate(tab_groups):
            self.create_tab_group(
                project_id,
                tg['name'],
                tg.get('description', ''),
                tg.get('color'),
                i
            )

        conn.close()
        return project_id


if __name__ == "__main__":
    # Demo usage
    pm = ProjectManager()

    # Create a travel template
    pm.create_template(
        "travel-planning",
        "Template for planning trips",
        tab_groups=[
            {"name": "Tickets", "description": "Flight search", "color": "blue"},
            {"name": "Hotels", "description": "Accommodation", "color": "green"},
            {"name": "Activities", "description": "Things to do", "color": "yellow"},
            {"name": "Logistics", "description": "Transport, docs", "color": "red"}
        ],
        sheet_columns=["Task", "Status", "Progress", "Notes", "Links", "Cost"]
    )

    # Create Ethiopia trip project from template
    project_id = pm.create_project_from_template("ethiopia-trip", "travel-planning")

    print(f"Created project: {project_id}")
    print("\nProjects:")
    for p in pm.list_projects():
        print(f"  {p['name']}: {p['group_count']} groups, {p['tab_count']} tabs, {p['avg_progress']}% progress")
