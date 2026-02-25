#!/usr/bin/env python3
"""
Autonomous Task Assigner

Monitors idle Go Wrapper agents and automatically assigns roadmap tasks.

Features:
    - Monitors agent status via Go Wrapper API
    - Detects idle agents (no active tasks)
    - Auto-assigns roadmap tasks based on priority
    - Tracks task progress
    - Handles task completion

Usage:
    # Run as daemon
    python3 autonomous_task_assigner.py

    # One-time assignment
    python3 autonomous_task_assigner.py --once

Environment Variables:
    GO_WRAPPER_API - Go Wrapper API URL (default: http://100.112.58.92:8151)
    ARCHITECT_API - Architect Dashboard API URL (default: http://localhost:8080)
    CHECK_INTERVAL - Seconds between checks (default: 30)
    MIN_IDLE_TIME - Minimum idle time before assignment (default: 60)
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.roadmap_api import RoadmapAPI  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
)
logger = logging.getLogger("AutonomousTaskAssigner")


# =============================================================================
# Configuration
# =============================================================================

GO_WRAPPER_API = os.getenv("GO_WRAPPER_API", "http://100.112.58.92:8151")
ARCHITECT_API = os.getenv("ARCHITECT_API", "http://localhost:8080")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))
MIN_IDLE_TIME = int(os.getenv("MIN_IDLE_TIME", "60"))


# =============================================================================
# Autonomous Task Assigner
# =============================================================================


class AutonomousTaskAssigner:
    """Assigns roadmap tasks to idle agents."""

    def __init__(self):
        self.roadmap_api = RoadmapAPI()
        self.assigned_tasks = {}  # agent_id -> task_id
        self.last_check = {}  # agent_id -> timestamp

        logger.info("Autonomous Task Assigner initialized")
        logger.info(f"Go Wrapper API: {GO_WRAPPER_API}")
        logger.info(f"Architect API: {ARCHITECT_API}")

    def get_agents(self):
        """Get agent list from Go Wrapper."""
        try:
            response = requests.get(f"{GO_WRAPPER_API}/api/agents", timeout=5)
            response.raise_for_status()
            data = response.json()

            agents = data.get("agents", [])
            logger.debug(f"Found {len(agents)} agents")
            return agents

        except Exception as e:
            logger.error(f"Failed to get agents: {e}")
            return []

    def is_agent_idle(self, agent):
        """Check if agent is idle."""
        # An agent is idle if:
        # 1. Status is not "busy"
        # 2. Last activity was > MIN_IDLE_TIME seconds ago
        # 3. No current task assigned

        agent_id = agent.get("id") or agent.get("name")
        status = agent.get("status", "unknown")

        if status == "busy":
            return False

        # Check if already has a task
        if agent_id in self.assigned_tasks:
            task_id = self.assigned_tasks[agent_id]
            task_status = self.roadmap_api.get_task_status(task_id)

            # If task is still in progress, not idle
            if task_status and task_status["status"] == "in_progress":
                return False

            # Task completed or not found, remove from tracking
            del self.assigned_tasks[agent_id]

        # Check last activity time
        last_activity = agent.get("last_activity")
        if last_activity:
            # If last activity was recent, not idle
            try:
                activity_time = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
                idle_seconds = (datetime.now() - activity_time.replace(tzinfo=None)).total_seconds()

                if idle_seconds < MIN_IDLE_TIME:
                    return False
            except Exception as e:
                logger.debug(f"Could not parse last_activity: {e}")

        return True

    def assign_task_to_agent(self, agent_id, task):
        """Assign a task to an agent."""
        try:
            # Claim the task
            claimed_task = self.roadmap_api.claim_task(task_id=task.task_id, agent_id=agent_id)

            if not claimed_task:
                logger.warning(f"Failed to claim task {task.task_id} for agent {agent_id}")
                return False

            # Track assignment
            self.assigned_tasks[agent_id] = task.task_id

            logger.info(f"✅ Assigned task {task.task_id} to agent {agent_id}: {task.title}")

            # Send task to agent via Architect API (if available)
            try:
                self.send_task_to_agent(agent_id, task)
            except Exception as e:
                logger.warning(f"Could not send task to agent: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to assign task: {e}")
            return False

    def send_task_to_agent(self, agent_id, task):
        """Send task description to agent via tmux."""
        # Format task message
        message = f"""
=============================================================================
NEW TASK ASSIGNED: {task.task_id}
=============================================================================
Title: {task.title}
Feature: {task.feature}
Priority: {task.priority}
Estimated Hours: {task.estimated_hours}

Description:
{task.description}

Subtasks:
"""
        for i, subtask in enumerate(task.subtasks, 1):
            message += f"  {i}. {subtask}\n"

        message += """
=============================================================================
When complete, update task progress via:
POST /api/roadmap/tasks/{task_id}/complete
{{"agent_id": "{agent_id}", "notes": "completion notes"}}
=============================================================================
""".format(
            task_id=task.task_id, agent_id=agent_id
        )

        # Try to send via Architect API
        try:
            response = requests.post(
                f"{ARCHITECT_API}/architecture/api/tmux/send",
                json={"session": agent_id, "command": f'echo "{message}"'},
                timeout=5,
            )
            if response.ok:
                logger.debug(f"Task message sent to agent {agent_id}")
        except Exception as e:
            logger.debug(f"Could not send via tmux: {e}")

    def check_and_assign(self):
        """Check agents and assign tasks to idle ones."""
        logger.info("Checking for idle agents...")

        # Get agents
        agents = self.get_agents()
        if not agents:
            logger.warning("No agents found")
            return

        # Find idle agents
        idle_agents = []
        for agent in agents:
            agent_id = agent.get("id") or agent.get("name")
            if self.is_agent_idle(agent):
                idle_agents.append(agent_id)

        if not idle_agents:
            logger.info("No idle agents found")
            return

        logger.info(f"Found {len(idle_agents)} idle agents: {', '.join(idle_agents)}")

        # Assign tasks to idle agents
        assigned_count = 0
        for agent_id in idle_agents:
            # Get available tasks
            tasks = self.roadmap_api.get_available_tasks(agent_id=agent_id, limit=1)

            if not tasks:
                logger.debug(f"No available tasks for agent {agent_id}")
                continue

            # Assign first available task
            task = tasks[0]
            if self.assign_task_to_agent(agent_id, task):
                assigned_count += 1

        logger.info(f"✅ Assigned {assigned_count} tasks")

    def run(self, once=False):
        """Run assignment loop."""
        logger.info("Starting autonomous task assignment")
        logger.info(f"Check interval: {CHECK_INTERVAL}s")
        logger.info(f"Min idle time: {MIN_IDLE_TIME}s")
        print()

        # Sync roadmap on startup
        logger.info("Syncing roadmap...")
        synced = self.roadmap_api.sync_from_roadmap()
        logger.info(f"Synced {synced} tasks from roadmap")
        print()

        # Show stats
        stats = self.roadmap_api.get_stats()
        logger.info(f"Roadmap: {stats['pending']} pending, {stats['in_progress']} in progress")
        print()

        if once:
            self.check_and_assign()
            return

        # Run loop
        try:
            while True:
                self.check_and_assign()

                # Wait for next check
                time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Stopped by user")
        except Exception as e:
            logger.error(f"Error in assignment loop: {e}")
            raise


# =============================================================================
# Main
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Autonomous Task Assigner")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    assigner = AutonomousTaskAssigner()
    assigner.run(once=args.once)


if __name__ == "__main__":
    main()
