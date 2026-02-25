"""
Database Migration System for Architect Dashboard

This module provides a lightweight migration system that:
- Tracks applied migrations in schema_versions table
- Preserves existing data during schema changes
- Backs up database before each migration
- Supports forward migrations only
"""

from .manager import MigrationManager, run_migrations

__all__ = ["MigrationManager", "run_migrations"]
