#!/usr/bin/env python3
"""
Simple Todo List Manager

A lightweight command-line todo list manager with persistence.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class TodoManager:
    """Manages a simple todo list with persistence."""

    def __init__(self, data_file: Optional[str] = None):
        """
        Initialize the todo manager.

        Args:
            data_file: Path to JSON file for persistence. Defaults to 'todos.json' in current dir.
        """
        if data_file is None:
            data_file = Path(__file__).parent / "data" / "todos.json"
        else:
            data_file = Path(data_file)

        self.data_file = data_file
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.todos: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        """Load todos from the data file."""
        if self.data_file.exists():
            try:
                with open(self.data_file, "r") as f:
                    self.todos = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.todos = []
        else:
            self.todos = []

    def save(self) -> None:
        """Save todos to the data file."""
        with open(self.data_file, "w") as f:
            json.dump(self.todos, f, indent=2)

    def add(self, task: str, priority: str = "medium", tags: List[str] = None) -> Dict[str, Any]:
        """
        Add a new todo item.

        Args:
            task: The task description.
            priority: Task priority (low, medium, high, critical).
            tags: Optional list of tags.

        Returns:
            The created todo item.
        """
        todo_id = max([t["id"] for t in self.todos], default=0) + 1

        todo = {
            "id": todo_id,
            "task": task,
            "priority": priority,
            "status": "pending",
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
        }

        self.todos.append(todo)
        self.save()
        return todo

    def list(
        self, status: Optional[str] = None, priority: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List todos with optional filtering.

        Args:
            status: Filter by status (pending, completed).
            priority: Filter by priority.

        Returns:
            List of matching todos.
        """
        result = self.todos

        if status:
            result = [t for t in result if t["status"] == status]

        if priority:
            result = [t for t in result if t["priority"] == priority]

        return result

    def get(self, todo_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific todo by ID.

        Args:
            todo_id: The todo ID.

        Returns:
            The todo item or None if not found.
        """
        for todo in self.todos:
            if todo["id"] == todo_id:
                return todo
        return None

    def complete(self, todo_id: int) -> bool:
        """
        Mark a todo as completed.

        Args:
            todo_id: The todo ID.

        Returns:
            True if successful, False if todo not found.
        """
        todo = self.get(todo_id)
        if todo:
            todo["status"] = "completed"
            todo["completed_at"] = datetime.now().isoformat()
            self.save()
            return True
        return False

    def delete(self, todo_id: int) -> bool:
        """
        Delete a todo.

        Args:
            todo_id: The todo ID.

        Returns:
            True if successful, False if todo not found.
        """
        for i, todo in enumerate(self.todos):
            if todo["id"] == todo_id:
                self.todos.pop(i)
                self.save()
                return True
        return False

    def update(self, todo_id: int, **kwargs) -> bool:
        """
        Update a todo's properties.

        Args:
            todo_id: The todo ID.
            **kwargs: Fields to update (task, priority, status, tags).

        Returns:
            True if successful, False if todo not found.
        """
        todo = self.get(todo_id)
        if todo:
            for key, value in kwargs.items():
                if key in todo:
                    todo[key] = value
            self.save()
            return True
        return False

    def clear_completed(self) -> int:
        """
        Remove all completed todos.

        Returns:
            Number of todos removed.
        """
        initial_count = len(self.todos)
        self.todos = [t for t in self.todos if t["status"] != "completed"]
        count_removed = initial_count - len(self.todos)
        if count_removed > 0:
            self.save()
        return count_removed


def main():
    """CLI interface for the todo manager."""
    import argparse

    parser = argparse.ArgumentParser(description="Simple Todo List Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new todo")
    add_parser.add_argument("task", help="Task description")
    add_parser.add_argument(
        "-p",
        "--priority",
        default="medium",
        choices=["low", "medium", "high", "critical"],
        help="Task priority",
    )
    add_parser.add_argument("-t", "--tags", nargs="*", help="Tags")

    # List command
    list_parser = subparsers.add_parser("list", help="List todos")
    list_parser.add_argument(
        "-s", "--status", choices=["pending", "completed"], help="Filter by status"
    )
    list_parser.add_argument(
        "-p", "--priority", choices=["low", "medium", "high", "critical"], help="Filter by priority"
    )

    # Complete command
    complete_parser = subparsers.add_parser("complete", help="Mark todo as completed")
    complete_parser.add_argument("id", type=int, help="Todo ID")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a todo")
    delete_parser.add_argument("id", type=int, help="Todo ID")

    # Clear command
    subparsers.add_parser("clear", help="Clear all completed todos")

    args = parser.parse_args()

    manager = TodoManager()

    if args.command == "add":
        todo = manager.add(args.task, args.priority, args.tags)
        print(f"✓ Added todo #{todo['id']}: {todo['task']}")

    elif args.command == "list":
        todos = manager.list(args.status, args.priority)
        if not todos:
            print("No todos found.")
        else:
            print(f"\n{'ID':<5} {'Priority':<10} {'Status':<12} {'Task'}")
            print("-" * 70)
            for todo in todos:
                priority_color = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}.get(
                    todo["priority"], ""
                )

                status_icon = "✓" if todo["status"] == "completed" else "○"

                print(
                    f"{todo['id']:<5} {priority_color} {todo['priority']:<8} {status_icon} {todo['status']:<10} {todo['task']}"
                )

    elif args.command == "complete":
        if manager.complete(args.id):
            print(f"✓ Completed todo #{args.id}")
        else:
            print(f"✗ Todo #{args.id} not found")

    elif args.command == "delete":
        if manager.delete(args.id):
            print(f"✓ Deleted todo #{args.id}")
        else:
            print(f"✗ Todo #{args.id} not found")

    elif args.command == "clear":
        count = manager.clear_completed()
        print(f"✓ Cleared {count} completed todo(s)")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
