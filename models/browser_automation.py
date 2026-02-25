"""
SQLAlchemy ORM Models for Browser Automation Phase 3

Defines data models for:
- browser_tasks: Main task tracking
- browser_execution_log: Step-by-step execution details
- browser_navigation_cache: Successful path caching
- browser_task_metrics: Performance aggregation
- browser_recovery_attempts: Recovery strategy tracking
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class BrowserTaskStatus(enum.Enum):
    """Task lifecycle states"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    RECOVERED = "recovered"


class AILevel(enum.Enum):
    """AI routing levels"""
    OLLAMA = 1
    CLAUDE = 2
    CODEX = 3
    GEMINI = 4


class RecoveryStrategy(enum.Enum):
    """Recovery strategies"""
    WAIT_AND_RETRY = "wait_and_retry"
    REFRESH_AND_RETRY = "refresh_and_retry"
    RE_AUTHENTICATE = "re_authenticate"
    CLOSE_MODAL_AND_RETRY = "close_modal_and_retry"
    BACK_OFF_AND_RETRY = "back_off_and_retry"


class BrowserTask(Base):
    """Main browser automation task record"""
    __tablename__ = 'browser_tasks'

    id = Column(String(36), primary_key=True)
    goal = Column(String(500), nullable=False, index=True)
    site_url = Column(String(500), nullable=False, index=True)
    status = Column(Enum(BrowserTaskStatus), default=BrowserTaskStatus.PENDING, nullable=False, index=True)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Execution metrics
    total_steps = Column(Integer, default=0)
    total_time_seconds = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)

    # Caching
    cached_path_used = Column(Boolean, default=False)
    cache_time_saved_seconds = Column(Float, default=0.0)

    # Results
    final_result = Column(String(1000))
    error_message = Column(Text)

    # Recovery
    recovery_attempts = Column(Integer, default=0)
    recovery_succeeded = Column(Boolean, default=False)

    # Metadata
    metadata = Column(JSON)

    # Relationships
    execution_logs = relationship("BrowserExecutionLog", back_populates="task", cascade="all, delete-orphan")
    recovery_attempts_rel = relationship("BrowserRecoveryAttempt", back_populates="task", cascade="all, delete-orphan")

    def is_running(self):
        """Check if task is currently running"""
        return self.status == BrowserTaskStatus.IN_PROGRESS

    def is_complete(self):
        """Check if task finished (success or failure)"""
        return self.status in (BrowserTaskStatus.COMPLETED, BrowserTaskStatus.FAILED)

    def get_duration(self):
        """Get total duration in seconds"""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'goal': self.goal,
            'site_url': self.site_url,
            'status': self.status.value if self.status else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'total_steps': self.total_steps,
            'total_time_seconds': self.total_time_seconds,
            'total_cost': self.total_cost,
            'cached_path_used': self.cached_path_used,
            'cache_time_saved_seconds': self.cache_time_saved_seconds,
            'final_result': self.final_result,
            'error_message': self.error_message,
            'recovery_attempts': self.recovery_attempts,
            'recovery_succeeded': self.recovery_succeeded,
        }


class BrowserExecutionLog(Base):
    """Detailed execution log for each step"""
    __tablename__ = 'browser_execution_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(36), ForeignKey('browser_tasks.id'), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)

    # Action details
    action = Column(String(200), nullable=False)
    ai_level = Column(Enum(AILevel), default=AILevel.OLLAMA)
    ai_used = Column(String(50), index=True)  # ollama, claude, codex, gemini, anythingllm

    # Metrics
    duration_ms = Column(Integer)
    cost = Column(Float, default=0.0)

    # Result
    result = Column(String(200))
    error_details = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    task = relationship("BrowserTask", back_populates="execution_logs")

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'step_number': self.step_number,
            'action': self.action,
            'ai_level': self.ai_level.value if self.ai_level else None,
            'ai_used': self.ai_used,
            'duration_ms': self.duration_ms,
            'cost': self.cost,
            'result': self.result,
            'error_details': self.error_details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class BrowserNavigationCache(Base):
    """Cache for successful navigation paths"""
    __tablename__ = 'browser_navigation_cache'

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_url = Column(String(500), nullable=False, index=True)
    goal_pattern = Column(String(500), nullable=False, index=True)

    # Cached path
    steps_json = Column(Text, nullable=False)  # JSON serialized list of steps

    # Cache metrics
    success_count = Column(Integer, default=1)
    total_time_seconds = Column(Float)

    # Cache lifecycle
    cache_created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    cache_last_used_at = Column(DateTime)
    cache_validity_expires_at = Column(DateTime)

    def is_valid(self):
        """Check if cache entry is still valid"""
        if self.cache_validity_expires_at:
            return datetime.utcnow() < self.cache_validity_expires_at
        return True

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'site_url': self.site_url,
            'goal_pattern': self.goal_pattern,
            'success_count': self.success_count,
            'total_time_seconds': self.total_time_seconds,
            'cache_created_at': self.cache_created_at.isoformat(),
            'cache_last_used_at': self.cache_last_used_at.isoformat() if self.cache_last_used_at else None,
            'is_valid': self.is_valid(),
        }


class BrowserTaskMetrics(Base):
    """Daily performance metrics aggregation"""
    __tablename__ = 'browser_task_metrics'

    metric_id = Column(Integer, primary_key=True, autoincrement=True)
    metric_date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Task completion
    total_tasks_completed = Column(Integer, default=0)
    total_tasks_failed = Column(Integer, default=0)

    # Performance
    avg_task_time_seconds = Column(Float, default=0.0)
    avg_task_cost = Column(Float, default=0.0)

    # Caching effectiveness
    cache_hit_count = Column(Integer, default=0)
    cache_hit_rate = Column(Float, default=0.0)

    # Recovery
    recovery_attempts = Column(Integer, default=0)
    recovery_success_rate = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'metric_id': self.metric_id,
            'metric_date': self.metric_date.isoformat(),
            'total_tasks_completed': self.total_tasks_completed,
            'total_tasks_failed': self.total_tasks_failed,
            'avg_task_time_seconds': self.avg_task_time_seconds,
            'avg_task_cost': self.avg_task_cost,
            'cache_hit_count': self.cache_hit_count,
            'cache_hit_rate': self.cache_hit_rate,
            'recovery_attempts': self.recovery_attempts,
            'recovery_success_rate': self.recovery_success_rate,
        }


class BrowserRecoveryAttempt(Base):
    """Recovery attempt tracking"""
    __tablename__ = 'browser_recovery_attempts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(36), ForeignKey('browser_tasks.id'), nullable=False, index=True)
    error_type = Column(String(100), nullable=False)
    recovery_strategy = Column(Enum(RecoveryStrategy), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    was_successful = Column(Boolean)
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    task = relationship("BrowserTask", back_populates="recovery_attempts_rel")

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'error_type': self.error_type,
            'recovery_strategy': self.recovery_strategy.value if self.recovery_strategy else None,
            'attempt_number': self.attempt_number,
            'was_successful': self.was_successful,
            'details': self.details,
            'created_at': self.created_at.isoformat(),
        }


# Query helpers
class BrowserTaskQueries:
    """Helper queries for browser tasks"""

    @staticmethod
    def get_active_tasks(session):
        """Get all currently running tasks"""
        return session.query(BrowserTask).filter(
            BrowserTask.status == BrowserTaskStatus.IN_PROGRESS
        ).all()

    @staticmethod
    def get_completed_tasks(session, limit=100):
        """Get recently completed tasks"""
        return session.query(BrowserTask).filter(
            BrowserTask.status == BrowserTaskStatus.COMPLETED
        ).order_by(BrowserTask.completed_at.desc()).limit(limit).all()

    @staticmethod
    def get_failed_tasks(session, limit=100):
        """Get failed tasks"""
        return session.query(BrowserTask).filter(
            BrowserTask.status == BrowserTaskStatus.FAILED
        ).order_by(BrowserTask.created_at.desc()).limit(limit).all()

    @staticmethod
    def get_pending_tasks(session):
        """Get tasks waiting to start"""
        return session.query(BrowserTask).filter(
            BrowserTask.status == BrowserTaskStatus.PENDING
        ).all()

    @staticmethod
    def get_tasks_by_site(session, site_url, limit=50):
        """Get tasks for a specific site"""
        return session.query(BrowserTask).filter(
            BrowserTask.site_url == site_url
        ).order_by(BrowserTask.created_at.desc()).limit(limit).all()

    @staticmethod
    def get_tasks_needing_recovery(session):
        """Get tasks that failed but haven't exhausted recovery"""
        return session.query(BrowserTask).filter(
            BrowserTask.status == BrowserTaskStatus.FAILED,
            BrowserTask.recovery_attempts < 3
        ).all()

    @staticmethod
    def calculate_metrics(session):
        """Calculate aggregate metrics across all tasks"""
        from sqlalchemy import func

        completed = session.query(func.count(BrowserTask.id)).filter(
            BrowserTask.status == BrowserTaskStatus.COMPLETED
        ).scalar() or 0

        failed = session.query(func.count(BrowserTask.id)).filter(
            BrowserTask.status == BrowserTaskStatus.FAILED
        ).scalar() or 0

        avg_time = session.query(func.avg(BrowserTask.total_time_seconds)).filter(
            BrowserTask.status.in_([BrowserTaskStatus.COMPLETED, BrowserTaskStatus.FAILED])
        ).scalar() or 0.0

        avg_cost = session.query(func.avg(BrowserTask.total_cost)).filter(
            BrowserTask.status.in_([BrowserTaskStatus.COMPLETED, BrowserTaskStatus.FAILED])
        ).scalar() or 0.0

        total_cost = session.query(func.sum(BrowserTask.total_cost)).filter(
            BrowserTask.status.in_([BrowserTaskStatus.COMPLETED, BrowserTaskStatus.FAILED])
        ).scalar() or 0.0

        cache_hits = session.query(func.count(BrowserTask.id)).filter(
            BrowserTask.cached_path_used == True
        ).scalar() or 0

        total_tasks = completed + failed or 1
        cache_hit_rate = (cache_hits / total_tasks * 100) if total_tasks > 0 else 0.0

        return {
            'total_completed': completed,
            'total_failed': failed,
            'total_tasks': total_tasks,
            'avg_time_seconds': float(avg_time),
            'avg_cost': float(avg_cost),
            'total_cost': float(total_cost),
            'cache_hits': cache_hits,
            'cache_hit_rate': cache_hit_rate,
        }
