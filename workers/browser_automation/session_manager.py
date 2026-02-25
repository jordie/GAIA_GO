#!/usr/bin/env python3
"""
Session and tab group management for browser automation
Tracks conversation state and allows resuming where you left off
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path


class SessionManager:
    def __init__(self, db_path="browser_sessions.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Sessions table - named collections of tabs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tab groups - tabs within a session
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tab_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                position INTEGER,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        ''')

        # Conversations - Perplexity conversation tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                conversation_url TEXT UNIQUE NOT NULL,
                topic TEXT,
                last_question TEXT,
                last_response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
            )
        ''')

        # Conversation history - track Q&A pairs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                response TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        conn.close()

    def create_session(self, name, description=""):
        """Create a new session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO sessions (name, description) VALUES (?, ?)",
                (name, description)
            )
            session_id = cursor.lastrowid
            conn.commit()
            return session_id
        except sqlite3.IntegrityError:
            # Session already exists, return existing ID
            cursor.execute("SELECT id FROM sessions WHERE name = ?", (name,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def save_tabs(self, session_name, tabs):
        """
        Save tabs to a session.
        tabs: list of dicts with {url, title, position}
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get or create session
        session_id = self.create_session(session_name)

        # Clear existing tabs
        cursor.execute("DELETE FROM tab_groups WHERE session_id = ?", (session_id,))

        # Insert new tabs
        for tab in tabs:
            cursor.execute(
                "INSERT INTO tab_groups (session_id, url, title, position) VALUES (?, ?, ?, ?)",
                (session_id, tab.get('url'), tab.get('title'), tab.get('position'))
            )

        # Update session timestamp
        cursor.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,)
        )

        conn.commit()
        conn.close()

    def load_tabs(self, session_name):
        """Load tabs from a session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT tg.url, tg.title, tg.position
            FROM tab_groups tg
            JOIN sessions s ON tg.session_id = s.id
            WHERE s.name = ?
            ORDER BY tg.position
            """,
            (session_name,)
        )

        tabs = [
            {'url': row[0], 'title': row[1], 'position': row[2]}
            for row in cursor.fetchall()
        ]

        conn.close()
        return tabs

    def save_conversation(self, conversation_url, topic="", last_question="", last_response="", session_name=None):
        """Save or update a Perplexity conversation."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        session_id = None
        if session_name:
            session_id = self.create_session(session_name)

        # Check if conversation exists
        cursor.execute(
            "SELECT id FROM conversations WHERE conversation_url = ?",
            (conversation_url,)
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing
            conversation_id = existing[0]
            cursor.execute(
                """
                UPDATE conversations
                SET topic = ?, last_question = ?, last_response = ?,
                    updated_at = CURRENT_TIMESTAMP, session_id = ?
                WHERE id = ?
                """,
                (topic, last_question, last_response, session_id, conversation_id)
            )
        else:
            # Create new
            cursor.execute(
                """
                INSERT INTO conversations
                (conversation_url, topic, last_question, last_response, session_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_url, topic, last_question, last_response, session_id)
            )
            conversation_id = cursor.lastrowid

        # Add to conversation history if question/response provided
        if last_question:
            cursor.execute(
                """
                INSERT INTO conversation_history
                (conversation_id, question, response)
                VALUES (?, ?, ?)
                """,
                (conversation_id, last_question, last_response)
            )

        conn.commit()
        conn.close()

        return conversation_id

    def get_conversation(self, conversation_url):
        """Get conversation details."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT c.id, c.conversation_url, c.topic, c.last_question,
                   c.last_response, c.created_at, c.updated_at,
                   s.name as session_name
            FROM conversations c
            LEFT JOIN sessions s ON c.session_id = s.id
            WHERE c.conversation_url = ?
            """,
            (conversation_url,)
        )

        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        conversation = {
            'id': row[0],
            'url': row[1],
            'topic': row[2],
            'last_question': row[3],
            'last_response': row[4],
            'created_at': row[5],
            'updated_at': row[6],
            'session': row[7]
        }

        # Get conversation history
        cursor.execute(
            """
            SELECT question, response, timestamp
            FROM conversation_history
            WHERE conversation_id = ?
            ORDER BY timestamp
            """,
            (conversation['id'],)
        )

        conversation['history'] = [
            {'question': r[0], 'response': r[1], 'timestamp': r[2]}
            for r in cursor.fetchall()
        ]

        conn.close()
        return conversation

    def list_sessions(self):
        """List all sessions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT s.name, s.description, s.created_at, s.updated_at,
                   COUNT(tg.id) as tab_count,
                   COUNT(DISTINCT c.id) as conversation_count
            FROM sessions s
            LEFT JOIN tab_groups tg ON s.id = tg.session_id
            LEFT JOIN conversations c ON s.id = c.session_id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
            """
        )

        sessions = [
            {
                'name': row[0],
                'description': row[1],
                'created_at': row[2],
                'updated_at': row[3],
                'tab_count': row[4],
                'conversation_count': row[5]
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return sessions

    def list_conversations(self, session_name=None):
        """List conversations, optionally filtered by session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if session_name:
            cursor.execute(
                """
                SELECT c.conversation_url, c.topic, c.last_question,
                       c.updated_at, s.name
                FROM conversations c
                JOIN sessions s ON c.session_id = s.id
                WHERE s.name = ?
                ORDER BY c.updated_at DESC
                """,
                (session_name,)
            )
        else:
            cursor.execute(
                """
                SELECT c.conversation_url, c.topic, c.last_question,
                       c.updated_at, s.name
                FROM conversations c
                LEFT JOIN sessions s ON c.session_id = s.id
                ORDER BY c.updated_at DESC
                """
            )

        conversations = [
            {
                'url': row[0],
                'topic': row[1],
                'last_question': row[2],
                'updated_at': row[3],
                'session': row[4]
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return conversations

    def delete_session(self, session_name):
        """Delete a session and its tabs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM sessions WHERE name = ?", (session_name,))
        deleted = cursor.rowcount

        conn.commit()
        conn.close()

        return deleted > 0


if __name__ == "__main__":
    # Demo usage
    sm = SessionManager()

    # Create a session
    sm.create_session("aquatech-research", "Researching swim classes")

    # Save some tabs
    sm.save_tabs("aquatech-research", [
        {'url': 'https://aquatechswim.com', 'title': 'AquaTech Swim', 'position': 0},
        {'url': 'https://aquatechswim.com/schedule', 'title': 'Schedule', 'position': 1}
    ])

    # Save a conversation
    sm.save_conversation(
        "https://www.perplexity.ai/search/xyz123",
        topic="Kids swim levels",
        last_question="What swim level are the kids at?",
        last_response="Eden: Tigershark, Saba: Silverfish...",
        session_name="aquatech-research"
    )

    # List sessions
    print("Sessions:")
    for session in sm.list_sessions():
        print(f"  {session['name']}: {session['tab_count']} tabs, {session['conversation_count']} conversations")

    print("\nConversations:")
    for conv in sm.list_conversations():
        print(f"  {conv['topic']}: {conv['url']}")
