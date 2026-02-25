"""
SQLAlchemy ORM Session Management

Provides a SQLAlchemy session that integrates with the connection pool
defined in db.py. This enables ORM-based database access while maintaining
the pooling and performance benefits.
"""

import logging
from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from db import get_db_path, POOL_CONFIG

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine with pooled connections
# Using NullPool since we manage pooling via db.py
DB_PATH = get_db_path("main")

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    # Use NullPool because we have our own pooling in db.py
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
    # Optimize for SQLite
    echo=False,
    execution_options={
        "timeout": 30,
        "isolation_level": None,  # Autocommit mode
    },
)

# Apply SQLite pragmas
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Apply SQLite pragma settings for better performance."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA cache_size=-64000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db_session() -> Session:
    """
    Get a new SQLAlchemy session.

    Returns:
        SQLAlchemy Session instance

    Example:
        session = get_db_session()
        try:
            task = session.query(BrowserTask).filter(...).first()
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    """
    return SessionLocal()


# Module-level session for backward compatibility
db_session = SessionLocal()


def close_db_session():
    """Close the module-level session."""
    global db_session
    if db_session:
        try:
            db_session.close()
        except Exception:
            pass
        db_session = None


def init_db():
    """Initialize database tables."""
    from models.browser_automation import Base

    # Create all tables
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database initialized at {DB_PATH}")


def get_engine():
    """Get the SQLAlchemy engine."""
    return engine


# Register cleanup on shutdown
import atexit
atexit.register(close_db_session)
