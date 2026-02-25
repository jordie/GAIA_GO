"""
Browser Task Service - Goal Engine Integration

Receives browser automation goals from the Goal Engine, creates tasks,
and returns results on completion.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class BrowserTaskPriority(Enum):
    """Task priority levels"""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


class BrowserTaskService:
    """
    Service for managing browser automation tasks.

    Provides interface between Goal Engine and browser automation system.
    """

    def __init__(self, db_session, llm_metrics_client=None):
        """
        Initialize service.

        Args:
            db_session: SQLAlchemy database session
            llm_metrics_client: Optional client for cost tracking
        """
        self.db_session = db_session
        self.llm_metrics_client = llm_metrics_client
        self.task_complete_callbacks = []

    def submit_goal(self, goal: str, site_url: str, priority: int = 5,
                   timeout_minutes: int = 30, metadata: Dict[str, Any] = None,
                   on_complete: Optional[Callable] = None) -> str:
        """
        Submit a browser automation goal to be executed.

        Called by Goal Engine to request browser automation.

        Args:
            goal: Natural language goal (e.g., "Register for swimming classes")
            site_url: Target website URL
            priority: Task priority (1-10, higher = more urgent)
            timeout_minutes: Maximum execution time
            metadata: Optional metadata (user_id, session_id, etc.)
            on_complete: Optional callback when task completes

        Returns:
            task_id: Unique task identifier

        Example:
            task_id = service.submit_goal(
                goal="Register Eden for Tuesday evening swimming",
                site_url="https://aquatechswim.com",
                priority=8,
                metadata={'user_id': 'user123'}
            )
        """
        try:
            from models.browser_automation import BrowserTask, BrowserTaskStatus

            task_id = str(uuid.uuid4())

            # Create task record
            task = BrowserTask(
                id=task_id,
                goal=goal,
                site_url=site_url,
                status=BrowserTaskStatus.PENDING,
                metadata={
                    'priority': priority,
                    'timeout_minutes': timeout_minutes,
                    'timeout_seconds': timeout_minutes * 60,
                    **(metadata or {})
                }
            )

            self.db_session.add(task)
            self.db_session.commit()

            logger.info(f"Created task {task_id}: {goal}")

            # Register completion callback if provided
            if on_complete:
                self.register_complete_callback(task_id, on_complete)

            return task_id

        except Exception as e:
            logger.error(f"Error submitting goal: {e}")
            self.db_session.rollback()
            raise

    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """
        Get the result of a completed task.

        Called by Goal Engine to retrieve results.

        Args:
            task_id: Task ID

        Returns:
            {
                'task_id': '...',
                'status': 'completed',  # pending, in_progress, completed, failed
                'goal': 'Register for swimming',
                'result': 'Successfully registered Eden for Tuesday 5pm class',
                'total_time_seconds': 45.3,
                'total_cost': 0.02,
                'cache_hit': false,
                'completed_at': '2026-02-17T12:35:00Z'
            }
        """
        try:
            from models.browser_automation import BrowserTask, BrowserTaskStatus

            task = self.db_session.query(BrowserTask).filter(
                BrowserTask.id == task_id
            ).first()

            if not task:
                return {'error': 'Task not found', 'task_id': task_id}

            result = {
                'task_id': task_id,
                'status': task.status.value if task.status else 'unknown',
                'goal': task.goal,
                'site_url': task.site_url,
                'total_time_seconds': task.total_time_seconds,
                'total_cost': task.total_cost,
                'cache_hit': task.cached_path_used,
            }

            if task.status == BrowserTaskStatus.COMPLETED:
                result['result'] = task.final_result
                result['completed_at'] = task.completed_at.isoformat() if task.completed_at else None
            elif task.status == BrowserTaskStatus.FAILED:
                result['error'] = task.error_message
                result['recovery_attempts'] = task.recovery_attempts
                result['recovery_succeeded'] = task.recovery_succeeded

            return result

        except Exception as e:
            logger.error(f"Error getting task result for {task_id}: {e}")
            return {'error': str(e), 'task_id': task_id}

    def wait_for_completion(self, task_id: str, timeout_seconds: int = 1800,
                           poll_interval_seconds: int = 2) -> Dict[str, Any]:
        """
        Block until a task completes (with timeout).

        Useful for synchronous workflows.

        Args:
            task_id: Task ID to wait for
            timeout_seconds: Maximum time to wait
            poll_interval_seconds: How often to check status

        Returns:
            Final task result

        Example:
            result = service.wait_for_completion(task_id, timeout_seconds=300)
            if result['status'] == 'completed':
                print(f"Success: {result['result']}")
            else:
                print(f"Failed: {result['error']}")
        """
        import time
        from models.browser_automation import BrowserTaskStatus

        start_time = datetime.utcnow()

        while True:
            # Check elapsed time
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout_seconds:
                logger.warning(f"Task {task_id} timed out after {elapsed} seconds")
                return {
                    'error': 'Timeout waiting for task completion',
                    'task_id': task_id,
                    'elapsed_seconds': elapsed
                }

            # Get task status
            result = self.get_task_result(task_id)

            # Check if done
            status = result.get('status')
            if status in ('completed', 'failed'):
                return result

            # Wait before checking again
            time.sleep(poll_interval_seconds)

    def register_complete_callback(self, task_id: str, callback: Callable):
        """
        Register a callback to be called when task completes.

        Args:
            task_id: Task ID
            callback: Function to call with task result
        """
        self.task_complete_callbacks.append((task_id, callback))

    def check_and_call_callbacks(self):
        """
        Check for completed tasks and call registered callbacks.

        Should be called periodically by a background worker.
        """
        from models.browser_automation import BrowserTaskStatus

        completed_callbacks = []

        for task_id, callback in self.task_complete_callbacks:
            try:
                result = self.get_task_result(task_id)
                status = result.get('status')

                if status in ('completed', 'failed'):
                    # Call the callback
                    try:
                        callback(result)
                        completed_callbacks.append((task_id, callback))
                    except Exception as e:
                        logger.error(f"Error calling callback for task {task_id}: {e}")

            except Exception as e:
                logger.error(f"Error checking task {task_id}: {e}")

        # Remove completed callbacks
        for callback_tuple in completed_callbacks:
            if callback_tuple in self.task_complete_callbacks:
                self.task_complete_callbacks.remove(callback_tuple)

    def get_task_chain_id(self, task_id: str) -> Optional[str]:
        """
        Get the Goal Engine chain ID this task belongs to.

        Used to route results back to the correct Goal Engine prompt.

        Args:
            task_id: Browser task ID

        Returns:
            Chain ID or None
        """
        try:
            from models.browser_automation import BrowserTask

            task = self.db_session.query(BrowserTask).filter(
                BrowserTask.id == task_id
            ).first()

            if task and task.metadata:
                return task.metadata.get('chain_id')

            return None

        except Exception as e:
            logger.error(f"Error getting chain ID for task {task_id}: {e}")
            return None

    def get_active_task_count(self) -> int:
        """
        Get number of currently active (running) tasks.

        Returns:
            Number of tasks with status IN_PROGRESS
        """
        try:
            from models.browser_automation import BrowserTask, BrowserTaskStatus

            count = self.db_session.query(BrowserTask).filter(
                BrowserTask.status == BrowserTaskStatus.IN_PROGRESS
            ).count()

            return count

        except Exception as e:
            logger.error(f"Error getting active task count: {e}")
            return 0

    def get_queue_depth(self) -> int:
        """
        Get number of pending tasks in queue.

        Returns:
            Number of tasks with status PENDING
        """
        try:
            from models.browser_automation import BrowserTask, BrowserTaskStatus

            count = self.db_session.query(BrowserTask).filter(
                BrowserTask.status == BrowserTaskStatus.PENDING
            ).count()

            return count

        except Exception as e:
            logger.error(f"Error getting queue depth: {e}")
            return 0

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary metrics for all browser tasks.

        Returns:
            {
                'total_tasks': 150,
                'completed': 125,
                'failed': 8,
                'active': 2,
                'pending': 15,
                'success_rate': 94.0,
                'avg_time_seconds': 45.2,
                'total_cost': 1.875,
                'cache_hit_rate': 72.0
            }
        """
        try:
            from models.browser_automation import BrowserTaskQueries

            metrics = BrowserTaskQueries.calculate_metrics(self.db_session)

            return {
                'total_tasks': metrics['total_tasks'],
                'completed': metrics['total_completed'],
                'failed': metrics['total_failed'],
                'success_rate': (metrics['total_completed'] / metrics['total_tasks'] * 100) if metrics['total_tasks'] > 0 else 0.0,
                'avg_time_seconds': metrics['avg_time_seconds'],
                'total_cost': metrics['total_cost'],
                'cache_hit_rate': metrics['cache_hit_rate'],
            }

        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}")
            return {'error': str(e)}

    def report_task_cost(self, task_id: str, cost: float, ai_provider: str):
        """
        Report cost for a task to LLM metrics.

        Args:
            task_id: Task ID
            cost: Cost in dollars
            ai_provider: AI provider used (ollama, claude, codex, gemini, anythingllm)
        """
        if not self.llm_metrics_client:
            return

        try:
            self.llm_metrics_client.record_cost(
                provider=ai_provider,
                cost=cost,
                metadata={
                    'task_id': task_id,
                    'source': 'browser_automation'
                }
            )
        except Exception as e:
            logger.error(f"Error reporting cost: {e}")
