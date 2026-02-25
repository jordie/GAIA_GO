"""
Browser Automation Task Handler for Assigner Worker Integration

Handles task claims, progress reporting, and completion for browser automation tasks.
Integrates with the Assigner Worker system for distributed task execution.
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BrowserAutomationTaskHandler:
    """
    Handles browser automation tasks claimed from the Assigner Worker queue.

    Task Lifecycle:
    1. PENDING: Task sits in queue waiting for worker
    2. CLAIMED: Worker claims task via claim_task()
    3. IN_PROGRESS: Worker reports progress via update_progress()
    4. COMPLETED: Worker reports success via report_completion()
    5. FAILED: Task failed, recovery handler decides next step
    """

    def __init__(self, db_session, assigner_client):
        """
        Initialize task handler.

        Args:
            db_session: SQLAlchemy database session
            assigner_client: Client for Assigner Worker communication
        """
        self.db_session = db_session
        self.assigner_client = assigner_client

    def claim_task(self, worker_id: str, max_tasks: int = 1) -> Dict[str, Any]:
        """
        Claim pending browser automation tasks from queue.

        Worker calls this to get the next task to execute.

        Args:
            worker_id: ID of the worker claiming tasks
            max_tasks: Maximum number of tasks to claim at once

        Returns:
            {
                'tasks': [
                    {
                        'task_id': '550e8400-e29b-41d4-a716-446655440000',
                        'goal': 'Register for swimming',
                        'site_url': 'https://aquatechswim.com',
                        'priority': 5,
                        'timeout_seconds': 1800,
                        'metadata': {}
                    }
                ],
                'count': 1
            }
        """
        try:
            from models.browser_automation import BrowserTask, BrowserTaskStatus

            # Find pending tasks (limit to max_tasks)
            pending_tasks = self.db_session.query(BrowserTask).filter(
                BrowserTask.status == BrowserTaskStatus.PENDING
            ).order_by(BrowserTask.metadata['priority'].desc()).limit(max_tasks).all()

            if not pending_tasks:
                logger.info(f"No pending tasks for worker {worker_id}")
                return {'tasks': [], 'count': 0}

            tasks_data = []
            for task in pending_tasks:
                # Update task status to IN_PROGRESS
                task.status = BrowserTaskStatus.IN_PROGRESS
                task.started_at = datetime.utcnow()

                tasks_data.append({
                    'task_id': task.id,
                    'goal': task.goal,
                    'site_url': task.site_url,
                    'priority': task.metadata.get('priority', 5) if task.metadata else 5,
                    'timeout_seconds': task.metadata.get('timeout_seconds', 1800) if task.metadata else 1800,
                    'metadata': task.metadata or {},
                    'cached_path': task.metadata.get('cached_path') if task.metadata else None,
                })

            self.db_session.commit()

            logger.info(f"Worker {worker_id} claimed {len(tasks_data)} tasks")
            return {
                'tasks': tasks_data,
                'count': len(tasks_data),
                'worker_id': worker_id,
                'claimed_at': datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error claiming task for worker {worker_id}: {e}")
            self.db_session.rollback()
            return {'error': str(e), 'tasks': [], 'count': 0}

    def update_progress(self, task_id: str, step_number: int, action: str,
                       ai_level: int, ai_used: str, duration_ms: int,
                       cost: float, result: str, error_details: Optional[str] = None) -> Dict[str, Any]:
        """
        Report execution progress for a task step.

        Worker calls this as it executes each step of the automation.

        Args:
            task_id: Task ID
            step_number: Which step in the task (1, 2, 3, ...)
            action: Description of what was done
            ai_level: AI routing level (1=Ollama, 2=Claude, 3=Codex, 4=Gemini)
            ai_used: Which AI provider was used
            duration_ms: How long the step took in milliseconds
            cost: Cost of this step in dollars
            result: Result status ('success', 'error', 'retry', etc.)
            error_details: Error details if result was 'error'

        Returns:
            {
                'success': True,
                'task_id': '550e8400-e29b-41d4-a716-446655440000',
                'step_number': 1,
                'total_cost_so_far': 0.015
            }
        """
        try:
            from models.browser_automation import BrowserTask, BrowserExecutionLog, AILevel

            task = self.db_session.query(BrowserTask).filter(
                BrowserTask.id == task_id
            ).first()

            if not task:
                logger.error(f"Task {task_id} not found")
                return {'error': 'Task not found', 'success': False}

            # Create execution log entry
            log_entry = BrowserExecutionLog(
                task_id=task_id,
                step_number=step_number,
                action=action,
                ai_level=AILevel(ai_level),
                ai_used=ai_used,
                duration_ms=duration_ms,
                cost=cost,
                result=result,
                error_details=error_details,
            )

            self.db_session.add(log_entry)

            # Update task counters
            task.total_steps = step_number
            task.total_time_seconds += duration_ms / 1000.0
            task.total_cost += cost

            self.db_session.commit()

            logger.debug(f"Recorded step {step_number} for task {task_id}")

            return {
                'success': True,
                'task_id': task_id,
                'step_number': step_number,
                'total_cost_so_far': task.total_cost,
                'total_time_so_far': task.total_time_seconds,
            }

        except Exception as e:
            logger.error(f"Error updating progress for task {task_id}: {e}")
            self.db_session.rollback()
            return {'error': str(e), 'success': False}

    def report_completion(self, task_id: str, final_result: str, cache_path_used: bool = False,
                         cache_time_saved_seconds: float = 0.0) -> Dict[str, Any]:
        """
        Report that a task completed successfully.

        Worker calls this when the automation goal is achieved.

        Args:
            task_id: Task ID
            final_result: Summary of what was accomplished
            cache_path_used: Whether cached path was used
            cache_time_saved_seconds: Time saved by using cache

        Returns:
            {
                'success': True,
                'task_id': '550e8400-e29b-41d4-a716-446655440000',
                'status': 'completed',
                'total_time_seconds': 45.3,
                'total_cost': 0.02,
                'cache_hit': true,
                'completed_at': '2026-02-17T12:35:00Z'
            }
        """
        try:
            from models.browser_automation import BrowserTask, BrowserTaskStatus

            task = self.db_session.query(BrowserTask).filter(
                BrowserTask.id == task_id
            ).first()

            if not task:
                logger.error(f"Task {task_id} not found")
                return {'error': 'Task not found', 'success': False}

            # Mark task as completed
            task.status = BrowserTaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.final_result = final_result
            task.cached_path_used = cache_path_used
            task.cache_time_saved_seconds = cache_time_saved_seconds

            self.db_session.commit()

            logger.info(f"Task {task_id} completed successfully")

            return {
                'success': True,
                'task_id': task_id,
                'status': 'completed',
                'total_time_seconds': task.total_time_seconds,
                'total_cost': task.total_cost,
                'cache_hit': cache_path_used,
                'completed_at': task.completed_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error reporting completion for task {task_id}: {e}")
            self.db_session.rollback()
            return {'error': str(e), 'success': False}

    def report_failure(self, task_id: str, error_message: str, recovery_needed: bool = True) -> Dict[str, Any]:
        """
        Report that a task failed.

        Worker calls this when the automation encounters an unrecoverable error.

        Args:
            task_id: Task ID
            error_message: Description of the error
            recovery_needed: Whether error recovery should be attempted

        Returns:
            {
                'success': True,
                'task_id': '550e8400-e29b-41d4-a716-446655440000',
                'status': 'failed',
                'recovery_attempted': True,
                'recovery_strategy': 'wait_and_retry'
            }
        """
        try:
            from models.browser_automation import BrowserTask, BrowserTaskStatus

            task = self.db_session.query(BrowserTask).filter(
                BrowserTask.id == task_id
            ).first()

            if not task:
                logger.error(f"Task {task_id} not found")
                return {'error': 'Task not found', 'success': False}

            # Mark task as failed
            task.status = BrowserTaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.error_message = error_message

            self.db_session.commit()

            logger.warning(f"Task {task_id} failed: {error_message}")

            recovery_strategy = None
            if recovery_needed and task.recovery_attempts < 3:
                # Trigger recovery handler
                recovery_strategy = self._trigger_recovery(task_id, error_message)

            return {
                'success': True,
                'task_id': task_id,
                'status': 'failed',
                'error': error_message,
                'recovery_attempted': recovery_needed,
                'recovery_strategy': recovery_strategy,
            }

        except Exception as e:
            logger.error(f"Error reporting failure for task {task_id}: {e}")
            self.db_session.rollback()
            return {'error': str(e), 'success': False}

    def _trigger_recovery(self, task_id: str, error_message: str) -> Optional[str]:
        """
        Trigger error recovery for a failed task.

        Routes to appropriate recovery strategy based on error type.

        Args:
            task_id: Task ID
            error_message: Error that occurred

        Returns:
            Recovery strategy used, or None if no recovery attempted
        """
        try:
            from models.browser_automation import BrowserTask

            task = self.db_session.query(BrowserTask).filter(
                BrowserTask.id == task_id
            ).first()

            if not task or task.recovery_attempts >= 3:
                logger.warning(f"Cannot recover task {task_id}: max attempts exceeded")
                return None

            # Analyze error and choose recovery strategy
            strategy = self._choose_recovery_strategy(error_message)

            logger.info(f"Attempting recovery for task {task_id} using strategy: {strategy}")

            # Queue recovery with Assigner Worker
            # This will be picked up by the recovery handler worker
            recovery_prompt = f"""
            Recover failed browser automation task {task_id}
            Strategy: {strategy}
            Error: {error_message}
            """

            # TODO: Send recovery task via assigner_client
            # self.assigner_client.send(recovery_prompt, target='recovery_worker', priority=8)

            return strategy

        except Exception as e:
            logger.error(f"Error triggering recovery: {e}")
            return None

    def _choose_recovery_strategy(self, error_message: str) -> str:
        """
        Choose appropriate recovery strategy based on error type.

        Args:
            error_message: Error that occurred

        Returns:
            Recovery strategy to use
        """
        error_lower = error_message.lower()

        if 'timeout' in error_lower:
            return 'wait_and_retry'
        elif 'modal' in error_lower or 'dialog' in error_lower:
            return 'close_modal_and_retry'
        elif 'auth' in error_lower or 'login' in error_lower or 'session' in error_lower:
            return 're_authenticate'
        elif 'stale' in error_lower or 'navigate' in error_lower or 'element' in error_lower:
            return 'refresh_and_retry'
        else:
            # Default: backoff and retry
            return 'back_off_and_retry'

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get current status of a task.

        Args:
            task_id: Task ID

        Returns:
            {
                'task_id': '550e8400-e29b-41d4-a716-446655440000',
                'status': 'in_progress',
                'progress': 60,
                'total_steps': 5,
                'completed_steps': 3,
                'current_step': 3,
                'total_cost': 0.015,
                'elapsed_time': 30.5
            }
        """
        try:
            from models.browser_automation import BrowserTask

            task = self.db_session.query(BrowserTask).filter(
                BrowserTask.id == task_id
            ).first()

            if not task:
                logger.error(f"Task {task_id} not found")
                return {'error': 'Task not found'}

            progress = 0
            if task.total_steps > 0:
                progress = int((task.total_steps / (task.total_steps + 1)) * 100)

            return {
                'task_id': task_id,
                'status': task.status.value if task.status else 'unknown',
                'progress': progress,
                'total_steps': task.total_steps,
                'total_cost': task.total_cost,
                'elapsed_time': task.total_time_seconds,
                'created_at': task.created_at.isoformat(),
                'started_at': task.started_at.isoformat() if task.started_at else None,
            }

        except Exception as e:
            logger.error(f"Error getting task status for {task_id}: {e}")
            return {'error': str(e)}
