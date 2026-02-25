"""
Real-Time Typing Indicators Module

Provides real-time collaboration features including typing indicators,
presence tracking, and edit awareness for multi-user editing.
"""

import json
import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Typing indicator timeout (seconds)
TYPING_TIMEOUT = 5

# Presence timeout (seconds)
PRESENCE_TIMEOUT = 60

# Maximum typing indicators per entity
MAX_INDICATORS_PER_ENTITY = 10


class TypingIndicatorManager:
    """Manages real-time typing indicators for collaborative editing."""

    def __init__(self):
        # Structure: {entity_key: {user_id: indicator_data}}
        self._indicators: Dict[str, Dict[str, Dict]] = defaultdict(dict)
        # Structure: {user_id: presence_data}
        self._presence: Dict[str, Dict] = {}
        # Structure: {entity_key: set of user_ids}
        self._viewers: Dict[str, Set[str]] = defaultdict(set)
        # Lock for thread safety
        self._lock = threading.RLock()
        # Cleanup thread
        self._cleanup_thread = None
        self._running = False

    def start_cleanup_thread(self):
        """Start background cleanup thread."""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._running = True
            self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
            self._cleanup_thread.start()

    def stop_cleanup_thread(self):
        """Stop background cleanup thread."""
        self._running = False

    def _cleanup_loop(self):
        """Background loop to clean up stale indicators."""
        while self._running:
            try:
                self.cleanup_stale()
            except Exception as e:
                logger.error(f"Typing indicator cleanup error: {e}")
            time.sleep(2)

    def _make_entity_key(self, entity_type: str, entity_id: str, field: str = None) -> str:
        """Create a unique key for an entity location."""
        if field:
            return f"{entity_type}:{entity_id}:{field}"
        return f"{entity_type}:{entity_id}"

    def set_typing(
        self,
        user_id: str,
        username: str,
        entity_type: str,
        entity_id: str,
        field: str = None,
        avatar_url: str = None,
    ) -> Dict:
        """Set a user as typing in an entity field.

        Args:
            user_id: User ID
            username: Display name
            entity_type: Type of entity (project, feature, bug, task, etc.)
            entity_id: Entity ID
            field: Optional field name (title, description, etc.)
            avatar_url: Optional avatar URL

        Returns:
            Dict with typing status and other users typing
        """
        entity_key = self._make_entity_key(entity_type, entity_id, field)

        with self._lock:
            # Create indicator data
            indicator = {
                "user_id": user_id,
                "username": username,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "field": field,
                "started_at": datetime.now().isoformat(),
                "last_update": time.time(),
                "avatar_url": avatar_url,
            }

            # Store indicator
            self._indicators[entity_key][user_id] = indicator

            # Update presence
            self._update_presence(user_id, username, avatar_url)

            # Get other users typing in same entity
            others = self._get_others_typing(entity_key, user_id)

            return {"status": "typing", "entity_key": entity_key, "others_typing": others}

    def clear_typing(
        self, user_id: str, entity_type: str = None, entity_id: str = None, field: str = None
    ) -> Dict:
        """Clear typing indicator for a user.

        Args:
            user_id: User ID
            entity_type: Optional entity type (if None, clears all)
            entity_id: Optional entity ID
            field: Optional field name

        Returns:
            Dict with cleared status
        """
        cleared = []

        with self._lock:
            if entity_type and entity_id:
                # Clear specific entity
                entity_key = self._make_entity_key(entity_type, entity_id, field)
                if user_id in self._indicators.get(entity_key, {}):
                    del self._indicators[entity_key][user_id]
                    if not self._indicators[entity_key]:
                        del self._indicators[entity_key]
                    cleared.append(entity_key)
            else:
                # Clear all typing for user
                keys_to_clean = []
                for entity_key, users in self._indicators.items():
                    if user_id in users:
                        keys_to_clean.append(entity_key)

                for key in keys_to_clean:
                    del self._indicators[key][user_id]
                    if not self._indicators[key]:
                        del self._indicators[key]
                    cleared.append(key)

        return {"status": "cleared", "cleared": cleared}

    def get_typing_users(
        self, entity_type: str, entity_id: str, field: str = None, exclude_user: str = None
    ) -> List[Dict]:
        """Get users currently typing in an entity.

        Args:
            entity_type: Entity type
            entity_id: Entity ID
            field: Optional field name
            exclude_user: Optional user to exclude

        Returns:
            List of typing user info
        """
        entity_key = self._make_entity_key(entity_type, entity_id, field)

        with self._lock:
            users = []
            now = time.time()

            for user_id, indicator in self._indicators.get(entity_key, {}).items():
                if exclude_user and user_id == exclude_user:
                    continue

                # Check if indicator is still valid
                if now - indicator["last_update"] <= TYPING_TIMEOUT:
                    users.append(
                        {
                            "user_id": indicator["user_id"],
                            "username": indicator["username"],
                            "field": indicator.get("field"),
                            "started_at": indicator["started_at"],
                            "avatar_url": indicator.get("avatar_url"),
                        }
                    )

            return users

    def get_entity_activity(self, entity_type: str, entity_id: str) -> Dict:
        """Get all activity for an entity (typing + viewing).

        Args:
            entity_type: Entity type
            entity_id: Entity ID

        Returns:
            Dict with typing and viewing users
        """
        base_key = self._make_entity_key(entity_type, entity_id)
        now = time.time()

        with self._lock:
            typing = []
            typing_by_field = defaultdict(list)

            # Get all typing indicators for this entity
            for entity_key, users in self._indicators.items():
                if entity_key.startswith(base_key):
                    for user_id, indicator in users.items():
                        if now - indicator["last_update"] <= TYPING_TIMEOUT:
                            user_info = {
                                "user_id": indicator["user_id"],
                                "username": indicator["username"],
                                "avatar_url": indicator.get("avatar_url"),
                            }
                            typing.append({**user_info, "field": indicator.get("field")})
                            if indicator.get("field"):
                                typing_by_field[indicator["field"]].append(user_info)

            # Get viewers
            viewers = []
            for user_id in self._viewers.get(base_key, set()):
                if user_id in self._presence:
                    presence = self._presence[user_id]
                    if now - presence.get("last_seen", 0) <= PRESENCE_TIMEOUT:
                        viewers.append(
                            {
                                "user_id": user_id,
                                "username": presence.get("username"),
                                "avatar_url": presence.get("avatar_url"),
                            }
                        )

            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "typing": typing,
                "typing_by_field": dict(typing_by_field),
                "typing_count": len(typing),
                "viewers": viewers,
                "viewer_count": len(viewers),
            }

    def set_viewing(
        self, user_id: str, username: str, entity_type: str, entity_id: str, avatar_url: str = None
    ) -> Dict:
        """Mark a user as viewing an entity.

        Args:
            user_id: User ID
            username: Display name
            entity_type: Entity type
            entity_id: Entity ID
            avatar_url: Optional avatar URL

        Returns:
            Dict with viewing status
        """
        entity_key = self._make_entity_key(entity_type, entity_id)

        with self._lock:
            self._viewers[entity_key].add(user_id)
            self._update_presence(user_id, username, avatar_url)

            # Get other viewers
            other_viewers = []
            for uid in self._viewers[entity_key]:
                if uid != user_id and uid in self._presence:
                    presence = self._presence[uid]
                    other_viewers.append(
                        {
                            "user_id": uid,
                            "username": presence.get("username"),
                            "avatar_url": presence.get("avatar_url"),
                        }
                    )

            return {"status": "viewing", "entity_key": entity_key, "other_viewers": other_viewers}

    def clear_viewing(self, user_id: str, entity_type: str = None, entity_id: str = None) -> Dict:
        """Clear viewing status for a user.

        Args:
            user_id: User ID
            entity_type: Optional entity type
            entity_id: Optional entity ID

        Returns:
            Dict with cleared status
        """
        cleared = []

        with self._lock:
            if entity_type and entity_id:
                entity_key = self._make_entity_key(entity_type, entity_id)
                if user_id in self._viewers.get(entity_key, set()):
                    self._viewers[entity_key].discard(user_id)
                    if not self._viewers[entity_key]:
                        del self._viewers[entity_key]
                    cleared.append(entity_key)
            else:
                # Clear all viewing for user
                keys_to_clean = []
                for entity_key, users in self._viewers.items():
                    if user_id in users:
                        keys_to_clean.append(entity_key)

                for key in keys_to_clean:
                    self._viewers[key].discard(user_id)
                    if not self._viewers[key]:
                        del self._viewers[key]
                    cleared.append(key)

        return {"status": "cleared", "cleared": cleared}

    def _update_presence(self, user_id: str, username: str, avatar_url: str = None):
        """Update user presence."""
        self._presence[user_id] = {
            "user_id": user_id,
            "username": username,
            "avatar_url": avatar_url,
            "last_seen": time.time(),
        }

    def _get_others_typing(self, entity_key: str, exclude_user: str) -> List[Dict]:
        """Get other users typing in an entity."""
        others = []
        now = time.time()

        for user_id, indicator in self._indicators.get(entity_key, {}).items():
            if user_id != exclude_user:
                if now - indicator["last_update"] <= TYPING_TIMEOUT:
                    others.append(
                        {
                            "user_id": indicator["user_id"],
                            "username": indicator["username"],
                            "avatar_url": indicator.get("avatar_url"),
                        }
                    )

        return others

    def cleanup_stale(self) -> int:
        """Remove stale typing indicators and presence.

        Returns:
            Number of indicators cleaned up
        """
        cleaned = 0
        now = time.time()

        with self._lock:
            # Clean up typing indicators
            empty_keys = []
            for entity_key, users in list(self._indicators.items()):
                stale_users = []
                for user_id, indicator in users.items():
                    if now - indicator["last_update"] > TYPING_TIMEOUT:
                        stale_users.append(user_id)

                for user_id in stale_users:
                    del users[user_id]
                    cleaned += 1

                if not users:
                    empty_keys.append(entity_key)

            for key in empty_keys:
                del self._indicators[key]

            # Clean up stale presence
            stale_presence = []
            for user_id, presence in self._presence.items():
                if now - presence.get("last_seen", 0) > PRESENCE_TIMEOUT:
                    stale_presence.append(user_id)

            for user_id in stale_presence:
                del self._presence[user_id]
                # Also remove from all viewers
                for viewers in self._viewers.values():
                    viewers.discard(user_id)

        return cleaned

    def get_online_users(self) -> List[Dict]:
        """Get all currently online users.

        Returns:
            List of online user info
        """
        now = time.time()
        online = []

        with self._lock:
            for user_id, presence in self._presence.items():
                if now - presence.get("last_seen", 0) <= PRESENCE_TIMEOUT:
                    online.append(
                        {
                            "user_id": user_id,
                            "username": presence.get("username"),
                            "avatar_url": presence.get("avatar_url"),
                            "last_seen": datetime.fromtimestamp(
                                presence.get("last_seen", 0)
                            ).isoformat(),
                        }
                    )

        return online

    def get_user_activity(self, user_id: str) -> Dict:
        """Get current activity for a user.

        Args:
            user_id: User ID

        Returns:
            Dict with user's current typing and viewing
        """
        now = time.time()

        with self._lock:
            typing = []
            for entity_key, users in self._indicators.items():
                if user_id in users:
                    indicator = users[user_id]
                    if now - indicator["last_update"] <= TYPING_TIMEOUT:
                        typing.append(
                            {
                                "entity_type": indicator["entity_type"],
                                "entity_id": indicator["entity_id"],
                                "field": indicator.get("field"),
                            }
                        )

            viewing = []
            for entity_key, viewers in self._viewers.items():
                if user_id in viewers:
                    parts = entity_key.split(":")
                    viewing.append(
                        {
                            "entity_type": parts[0] if len(parts) > 0 else None,
                            "entity_id": parts[1] if len(parts) > 1 else None,
                        }
                    )

            presence = self._presence.get(user_id, {})

            return {
                "user_id": user_id,
                "username": presence.get("username"),
                "online": now - presence.get("last_seen", 0) <= PRESENCE_TIMEOUT,
                "typing": typing,
                "viewing": viewing,
            }

    def heartbeat(self, user_id: str, username: str = None, avatar_url: str = None):
        """Update user heartbeat for presence.

        Args:
            user_id: User ID
            username: Optional username update
            avatar_url: Optional avatar URL update
        """
        with self._lock:
            if user_id in self._presence:
                self._presence[user_id]["last_seen"] = time.time()
                if username:
                    self._presence[user_id]["username"] = username
                if avatar_url:
                    self._presence[user_id]["avatar_url"] = avatar_url
            else:
                self._presence[user_id] = {
                    "user_id": user_id,
                    "username": username or user_id,
                    "avatar_url": avatar_url,
                    "last_seen": time.time(),
                }

    def disconnect_user(self, user_id: str) -> Dict:
        """Handle user disconnect - clear all their activity.

        Args:
            user_id: User ID

        Returns:
            Dict with cleared entities
        """
        typing_result = self.clear_typing(user_id)
        viewing_result = self.clear_viewing(user_id)

        with self._lock:
            if user_id in self._presence:
                del self._presence[user_id]

        return {
            "typing_cleared": typing_result.get("cleared", []),
            "viewing_cleared": viewing_result.get("cleared", []),
        }

    def get_stats(self) -> Dict:
        """Get typing indicator statistics.

        Returns:
            Dict with stats
        """
        with self._lock:
            total_typing = sum(len(users) for users in self._indicators.values())
            total_viewing = sum(len(viewers) for viewers in self._viewers.values())

            return {
                "entities_with_typing": len(self._indicators),
                "total_typing_indicators": total_typing,
                "entities_with_viewers": len(self._viewers),
                "total_viewers": total_viewing,
                "online_users": len(
                    [
                        p
                        for p in self._presence.values()
                        if time.time() - p.get("last_seen", 0) <= PRESENCE_TIMEOUT
                    ]
                ),
            }


# Global manager instance
_manager: Optional[TypingIndicatorManager] = None


def get_typing_manager() -> TypingIndicatorManager:
    """Get the global typing indicator manager."""
    global _manager
    if _manager is None:
        _manager = TypingIndicatorManager()
        _manager.start_cleanup_thread()
    return _manager
