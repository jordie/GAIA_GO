#!/usr/bin/env python3
"""
Tests for Real-Time Collaboration Features

Verifies:
- TypingIndicatorManager functionality
- Presence tracking
- Entity viewing/leaving
- Cleanup of stale indicators
"""

import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing_indicators import PRESENCE_TIMEOUT, TYPING_TIMEOUT, TypingIndicatorManager


class TestTypingIndicatorManager(unittest.TestCase):
    """Test TypingIndicatorManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = TypingIndicatorManager()

    def tearDown(self):
        """Clean up."""
        self.manager.stop_cleanup_thread()

    def test_set_typing(self):
        """Test setting typing indicator."""
        result = self.manager.set_typing(
            user_id="user1",
            username="Alice",
            entity_type="feature",
            entity_id="123",
            field="description",
        )

        self.assertEqual(result["status"], "typing")
        self.assertIn("entity_key", result)
        self.assertEqual(result["entity_key"], "feature:123:description")

    def test_clear_typing(self):
        """Test clearing typing indicator."""
        # Set typing first
        self.manager.set_typing(
            user_id="user1", username="Alice", entity_type="feature", entity_id="123"
        )

        # Clear it
        result = self.manager.clear_typing(user_id="user1", entity_type="feature", entity_id="123")

        self.assertEqual(result["status"], "cleared")
        self.assertIn("feature:123", result["cleared"])

    def test_clear_all_typing_for_user(self):
        """Test clearing all typing indicators for a user."""
        # Set typing in multiple entities
        self.manager.set_typing("user1", "Alice", "feature", "1")
        self.manager.set_typing("user1", "Alice", "bug", "2")
        self.manager.set_typing("user1", "Alice", "task", "3")

        # Clear all for user
        result = self.manager.clear_typing(user_id="user1")

        self.assertEqual(result["status"], "cleared")
        self.assertEqual(len(result["cleared"]), 3)

    def test_get_typing_users(self):
        """Test getting users typing in an entity."""
        self.manager.set_typing("user1", "Alice", "feature", "123")
        self.manager.set_typing("user2", "Bob", "feature", "123")

        users = self.manager.get_typing_users("feature", "123")

        self.assertEqual(len(users), 2)
        usernames = [u["username"] for u in users]
        self.assertIn("Alice", usernames)
        self.assertIn("Bob", usernames)

    def test_get_typing_users_excludes_self(self):
        """Test that exclude_user works."""
        self.manager.set_typing("user1", "Alice", "feature", "123")
        self.manager.set_typing("user2", "Bob", "feature", "123")

        users = self.manager.get_typing_users("feature", "123", exclude_user="user1")

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["username"], "Bob")

    def test_set_viewing(self):
        """Test setting viewing status."""
        result = self.manager.set_viewing(
            user_id="user1", username="Alice", entity_type="feature", entity_id="123"
        )

        self.assertEqual(result["status"], "viewing")
        self.assertEqual(result["entity_key"], "feature:123")

    def test_clear_viewing(self):
        """Test clearing viewing status."""
        self.manager.set_viewing("user1", "Alice", "feature", "123")

        result = self.manager.clear_viewing(user_id="user1", entity_type="feature", entity_id="123")

        self.assertEqual(result["status"], "cleared")
        self.assertIn("feature:123", result["cleared"])

    def test_get_entity_activity(self):
        """Test getting all activity for an entity."""
        # Set up some activity
        self.manager.set_viewing("user1", "Alice", "feature", "123")
        self.manager.set_viewing("user2", "Bob", "feature", "123")
        self.manager.set_typing("user1", "Alice", "feature", "123", field="title")

        activity = self.manager.get_entity_activity("feature", "123")

        self.assertEqual(activity["entity_type"], "feature")
        self.assertEqual(activity["entity_id"], "123")
        self.assertGreaterEqual(activity["viewer_count"], 2)
        self.assertEqual(activity["typing_count"], 1)
        self.assertIn("title", activity["typing_by_field"])

    def test_typing_expiration(self):
        """Test that typing indicators expire."""
        # Set typing
        self.manager.set_typing("user1", "Alice", "feature", "123")

        # Manually expire the indicator
        entity_key = "feature:123"
        self.manager._indicators[entity_key]["user1"]["last_update"] = (
            time.time() - TYPING_TIMEOUT - 1
        )

        # Get typing users (should be empty due to expiration)
        users = self.manager.get_typing_users("feature", "123")
        self.assertEqual(len(users), 0)

    def test_presence_tracking(self):
        """Test presence is updated when typing/viewing."""
        self.manager.set_typing("user1", "Alice", "feature", "123")

        # Check presence was recorded
        self.assertIn("user1", self.manager._presence)
        self.assertEqual(self.manager._presence["user1"]["username"], "Alice")

    def test_cleanup_stale(self):
        """Test cleanup of stale indicators."""
        # Set typing
        self.manager.set_typing("user1", "Alice", "feature", "123")

        # Manually expire the indicator
        entity_key = "feature:123"
        self.manager._indicators[entity_key]["user1"]["last_update"] = (
            time.time() - TYPING_TIMEOUT - 1
        )

        # Run cleanup
        self.manager.cleanup_stale()

        # Should be cleaned up
        self.assertNotIn("user1", self.manager._indicators.get(entity_key, {}))

    def test_concurrent_access(self):
        """Test thread safety with concurrent access."""
        errors = []
        results = []

        def worker(user_id):
            try:
                for i in range(10):
                    self.manager.set_typing(user_id, f"User{user_id}", "feature", "123")
                    time.sleep(0.01)
                    self.manager.get_typing_users("feature", "123")
                    self.manager.clear_typing(user_id, "feature", "123")
                results.append(True)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(f"user{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 5)
        self.assertEqual(len(errors), 0)

    def test_cleanup_thread(self):
        """Test that cleanup thread starts and stops."""
        self.manager.start_cleanup_thread()
        self.assertTrue(self.manager._running)
        self.assertIsNotNone(self.manager._cleanup_thread)

        self.manager.stop_cleanup_thread()
        self.assertFalse(self.manager._running)

    def test_multiple_fields_same_entity(self):
        """Test tracking different fields in the same entity."""
        self.manager.set_typing("user1", "Alice", "feature", "123", field="title")
        self.manager.set_typing("user2", "Bob", "feature", "123", field="description")

        activity = self.manager.get_entity_activity("feature", "123")

        self.assertEqual(activity["typing_count"], 2)
        self.assertIn("title", activity["typing_by_field"])
        self.assertIn("description", activity["typing_by_field"])

    def test_avatar_url_stored(self):
        """Test that avatar URL is stored and returned."""
        self.manager.set_typing(
            user_id="user1",
            username="Alice",
            entity_type="feature",
            entity_id="123",
            avatar_url="https://example.com/avatar.png",
        )

        users = self.manager.get_typing_users("feature", "123")
        self.assertEqual(users[0]["avatar_url"], "https://example.com/avatar.png")

    def test_get_online_users(self):
        """Test getting list of online users."""
        self.manager.set_typing("user1", "Alice", "feature", "123")
        self.manager.set_viewing("user2", "Bob", "bug", "456")

        online = self.manager.get_online_users()

        self.assertGreaterEqual(len(online), 2)
        user_ids = [u["user_id"] for u in online]
        self.assertIn("user1", user_ids)
        self.assertIn("user2", user_ids)


class TestEntityKeys(unittest.TestCase):
    """Test entity key generation."""

    def setUp(self):
        self.manager = TypingIndicatorManager()

    def test_entity_key_without_field(self):
        """Test entity key generation without field."""
        key = self.manager._make_entity_key("feature", "123")
        self.assertEqual(key, "feature:123")

    def test_entity_key_with_field(self):
        """Test entity key generation with field."""
        key = self.manager._make_entity_key("feature", "123", "description")
        self.assertEqual(key, "feature:123:description")

    def test_entity_key_handles_strings(self):
        """Test entity key handles string IDs."""
        key = self.manager._make_entity_key("bug", "bug-uuid-12345", "title")
        self.assertEqual(key, "bug:bug-uuid-12345:title")


if __name__ == "__main__":
    unittest.main(verbosity=2)
