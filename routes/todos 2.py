"""
Todo REST API Endpoints

Provides CRUD operations for todo items:
- GET /api/todos - Retrieve all todos
- POST /api/todos - Create a new todo
- PUT /api/todos/{id} - Update a todo
"""

import sqlite3
from datetime import datetime

from flask import Blueprint, jsonify, request

# Create Blueprint for todo routes
todos_bp = Blueprint("todos", __name__, url_prefix="/api/todos")

# Database initialization
DB_PATH = "data/todos.db"


def init_todos_db():
    """Initialize todos database table."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.commit()
    conn.close()


# Initialize database on module load
init_todos_db()


@todos_bp.route("", methods=["GET"])
def get_todos():
    """
    GET /api/todos - Retrieve all todos for the authenticated user

    Returns:
        JSON array of todos sorted by creation date (newest first)
        Each todo includes: id, title, description, completed, created_at, updated_at
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute(
            "SELECT id, title, description, completed, created_at, updated_at "
            "FROM todos ORDER BY created_at DESC"
        )
        rows = c.fetchall()
        conn.close()

        todos = [
            {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "completed": bool(row["completed"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

        return jsonify({"todos": todos, "count": len(todos)}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@todos_bp.route("", methods=["POST"])
def create_todo():
    """
    POST /api/todos - Create a new todo item with title and optional description

    Request JSON:
        {
            "title": "string (required)",
            "description": "string (optional)"
        }

    Returns:
        Created todo object with id, timestamps, and completed status
    """
    try:
        data = request.get_json()

        # Validate required fields
        if not data or "title" not in data:
            return jsonify({"error": "Title is required"}), 400

        title = data.get("title", "").strip()
        description = data.get("description", "").strip()

        if not title:
            return jsonify({"error": "Title cannot be empty"}), 400

        if len(title) > 500:
            return jsonify({"error": "Title too long (max 500 chars)"}), 400

        # Insert into database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        now = datetime.now().isoformat()
        c.execute(
            "INSERT INTO todos (title, description, created_at, updated_at) " "VALUES (?, ?, ?, ?)",
            (title, description, now, now),
        )
        conn.commit()

        todo_id = c.lastrowid
        conn.close()

        return (
            jsonify(
                {
                    "id": todo_id,
                    "title": title,
                    "description": description,
                    "completed": False,
                    "created_at": now,
                    "updated_at": now,
                }
            ),
            201,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@todos_bp.route("/<int:todo_id>", methods=["PUT"])
def update_todo(todo_id):
    """
    PUT /api/todos/{id} - Update an existing todo (title, description, completion status)

    Request JSON:
        {
            "title": "string (optional)",
            "description": "string (optional)",
            "completed": "boolean (optional)"
        }

    Returns:
        Updated todo object
    """
    try:
        data = request.get_json() or {}

        # Check if todo exists
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT * FROM todos WHERE id = ?", (todo_id,))
        todo = c.fetchone()

        if not todo:
            conn.close()
            return jsonify({"error": f"Todo #{todo_id} not found"}), 404

        # Prepare update values
        title = data.get("title", todo["title"]).strip()
        description = data.get("description", todo["description"]).strip()
        completed = data.get("completed", bool(todo["completed"]))

        # Validate
        if not title:
            conn.close()
            return jsonify({"error": "Title cannot be empty"}), 400

        if len(title) > 500:
            conn.close()
            return jsonify({"error": "Title too long (max 500 chars)"}), 400

        # Update database
        now = datetime.now().isoformat()
        c.execute(
            "UPDATE todos SET title = ?, description = ?, completed = ?, updated_at = ? "
            "WHERE id = ?",
            (title, description, int(completed), now, todo_id),
        )
        conn.commit()
        conn.close()

        return (
            jsonify(
                {
                    "id": todo_id,
                    "title": title,
                    "description": description,
                    "completed": completed,
                    "created_at": todo["created_at"],
                    "updated_at": now,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@todos_bp.route("/<int:todo_id>", methods=["DELETE"])
def delete_todo(todo_id):
    """
    DELETE /api/todos/{id} - Delete a todo item

    Returns:
        Success message with deleted todo ID
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Check if todo exists
        c.execute("SELECT id FROM todos WHERE id = ?", (todo_id,))
        if not c.fetchone():
            conn.close()
            return jsonify({"error": f"Todo #{todo_id} not found"}), 404

        # Delete the todo
        c.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        conn.commit()
        conn.close()

        return jsonify({"message": f"Todo #{todo_id} deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
