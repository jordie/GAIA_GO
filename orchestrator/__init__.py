"""
Autopilot Orchestration System

Manages autonomous development loops for applications:
- Planning → Implementing → Testing → Deploying → Monitoring → Investigating

Key components:
- AppManager: Manages app lifecycle and autopilot state
- RunExecutor: Executes autonomous improvement runs
- MilestoneTracker: Tracks and packages milestones for review
- ReviewQueue: Manages items awaiting user action
- AgentBridge: Interfaces with Claude via tmux sessions
"""

from .app_manager import AppManager
from .milestone_tracker import MilestoneTracker
from .review_queue import ReviewQueueManager
from .run_executor import RunExecutor

__all__ = ["AppManager", "RunExecutor", "MilestoneTracker", "ReviewQueueManager"]
