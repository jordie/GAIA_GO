#!/usr/bin/env python3
"""
Milestone Planning Worker

Scans active projects and generates development milestone plans.

The worker:
1. Scans directories for active projects
2. Reads TODO files, plans, and code to identify work items
3. Generates milestone plans with multi-day phases
4. Task breakdowns, priority ordering, complexity estimates
5. Outputs to data/milestones/ directory
6. Integrates with architect dashboard task queue

Usage:
    python3 milestone_worker.py                    # Run worker
    python3 milestone_worker.py --daemon           # Run as daemon
    python3 milestone_worker.py --scan             # Scan and generate now
    python3 milestone_worker.py --project <name>   # Scan specific project
"""

import argparse
import json
import logging
import os
import re
import signal
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Setup paths
WORKER_DIR = Path(__file__).parent
BASE_DIR = WORKER_DIR.parent
sys.path.insert(0, str(BASE_DIR))

# Configuration
TAILSCALE_IP = os.environ.get("TAILSCALE_IP", "100.112.58.92")
DASHBOARD_URL = os.environ.get("ARCHITECT_URL", f"http://{TAILSCALE_IP}:8080")
PROJECT_ROOT = Path("/Users/jgirmay/Desktop/gitrepo/pyWork")
MILESTONES_DIR = BASE_DIR / "data" / "milestones"
DB_PATH = BASE_DIR / "data" / "prod" / "architect.db"

PID_FILE = Path("/tmp/architect_milestone_worker.pid")
LOG_FILE = Path("/tmp/architect_milestone_worker.log")

# Ensure directories exist
MILESTONES_DIR.mkdir(parents=True, exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger("MilestoneWorker")

# Active projects to analyze (4 active projects)
ACTIVE_PROJECTS = {
    "architect": {
        "path": PROJECT_ROOT / "architect",
        "description": "Dashboard with testing, deployment, migrations",
        "key_files": ["TODO.md", "OPERATIONS.md", "app.py", ".claude/plans/*.md"],
    },
    "claude_browser_agent": {
        "path": PROJECT_ROOT / "claude_browser_agent",
        "description": "Browser automation framework",
        "key_files": ["README.md", "automation.py", "core/*.py"],
    },
    "basic_edu_apps_final": {
        "path": PROJECT_ROOT / "basic_edu_apps_final",
        "description": "Educational applications suite",
        "key_files": ["TODO.md", "CLAUDE.md", "unified_app.py"],
    },
    "mentor_v2": {
        "path": PROJECT_ROOT / "mentor_v2",
        "description": "Mentor application v2",
        "key_files": ["TODO.md", "CLAUDE.md", "*.py", "templates/*.html"],
    },
}


@dataclass
class Task:
    """A single development task."""

    title: str
    description: str
    priority: int  # 1=highest, 5=lowest
    complexity: str  # simple, medium, complex
    estimated_hours: float
    category: str  # feature, bug, test, deployment, documentation
    dependencies: List[str]
    source_file: str = ""
    line_number: int = 0

    def to_dict(self):
        return asdict(self)


@dataclass
class Milestone:
    """A development milestone grouping related tasks."""

    id: str
    name: str
    description: str
    phase: str  # planning, development, testing, deployment
    start_date: str  # ISO format
    target_date: str  # ISO format
    tasks: List[Task]
    total_hours: float
    status: str = "pending"  # pending, in_progress, completed

    def to_dict(self):
        return {**asdict(self), "tasks": [t.to_dict() for t in self.tasks]}


class MilestoneScanner:
    """Scans projects and extracts work items."""

    def __init__(self, project_config: Dict):
        self.project_name = project_config.get("name", "unknown")
        self.project_path = project_config["path"]
        self.description = project_config.get("description", "")
        self.key_files = project_config.get("key_files", [])

    def scan(self) -> List[Task]:
        """Scan project and return list of tasks."""
        tasks = []

        # Scan TODO files
        tasks.extend(self._scan_todo_files())

        # Scan plan files
        tasks.extend(self._scan_plan_files())

        # Scan code comments
        tasks.extend(self._scan_code_todos())

        # Scan CLAUDE.md guidance files
        tasks.extend(self._scan_claude_files())

        return tasks

    def _scan_todo_files(self) -> List[Task]:
        """Extract tasks from TODO.md files."""
        tasks = []
        todo_files = list(self.project_path.rglob("TODO.md"))

        for todo_file in todo_files:
            try:
                content = todo_file.read_text()
                tasks.extend(self._parse_todo_content(content, str(todo_file)))
            except Exception as e:
                logger.warning(f"Error reading {todo_file}: {e}")

        return tasks

    def _parse_todo_content(self, content: str, source_file: str) -> List[Task]:
        """Parse TODO markdown content into tasks."""
        tasks = []
        lines = content.split("\n")
        current_section = "general"

        for i, line in enumerate(lines, 1):
            # Detect section headers
            if line.startswith("##"):
                current_section = line.strip("#").strip()
                continue

            # Parse checkbox items
            checkbox_match = re.match(r"^- \[([ xX])\]\s+(.+)$", line)
            if checkbox_match:
                is_done = checkbox_match.group(1).lower() == "x"
                if is_done:
                    continue  # Skip completed tasks

                task_text = checkbox_match.group(2)

                # Extract priority and complexity hints
                priority = self._infer_priority(task_text, current_section)
                complexity = self._infer_complexity(task_text)
                category = self._infer_category(task_text, current_section)

                tasks.append(
                    Task(
                        title=task_text[:100],  # Truncate long titles
                        description=task_text,
                        priority=priority,
                        complexity=complexity,
                        estimated_hours=self._estimate_hours(complexity),
                        category=category,
                        dependencies=[],
                        source_file=source_file,
                        line_number=i,
                    )
                )

        return tasks

    def _scan_plan_files(self) -> List[Task]:
        """Extract tasks from plan files in .claude/plans/."""
        tasks = []
        plans_dir = self.project_path / ".claude" / "plans"

        if not plans_dir.exists():
            # Check global plans
            global_plans = Path.home() / ".claude" / "plans"
            if global_plans.exists():
                plans_dir = global_plans
            else:
                return tasks

        for plan_file in plans_dir.glob("*.md"):
            try:
                content = plan_file.read_text()
                tasks.extend(self._parse_plan_content(content, str(plan_file)))
            except Exception as e:
                logger.warning(f"Error reading {plan_file}: {e}")

        return tasks

    def _parse_plan_content(self, content: str, source_file: str) -> List[Task]:
        """Parse plan markdown into tasks."""
        tasks = []
        lines = content.split("\n")
        current_phase = "general"

        for i, line in enumerate(lines, 1):
            # Detect phase headers
            if line.startswith("## Phase") or line.startswith("### Phase"):
                current_phase = line.strip("#").strip()
                continue

            # Look for numbered items or bullet points with action verbs
            item_match = re.match(r"^(\d+\.|[-*])\s+(.+)$", line)
            if item_match:
                task_text = item_match.group(2)

                # Skip completed items marked with checkboxes
                if "[x]" in task_text.lower() or "[X]" in task_text:
                    continue

                # Look for action items
                if any(
                    task_text.lower().startswith(verb)
                    for verb in [
                        "create",
                        "add",
                        "implement",
                        "fix",
                        "update",
                        "modify",
                        "build",
                        "setup",
                    ]
                ):
                    tasks.append(
                        Task(
                            title=task_text[:100],
                            description=task_text,
                            priority=self._infer_priority(task_text, current_phase),
                            complexity=self._infer_complexity(task_text),
                            estimated_hours=self._estimate_hours(self._infer_complexity(task_text)),
                            category=self._infer_category(task_text, current_phase),
                            dependencies=[],
                            source_file=source_file,
                            line_number=i,
                        )
                    )

        return tasks

    def _scan_code_todos(self) -> List[Task]:
        """Find TODO/FIXME comments in code."""
        tasks = []

        # Scan Python files
        for py_file in self.project_path.rglob("*.py"):
            # Skip virtual environments and cache
            if any(
                x in str(py_file) for x in ["venv", "__pycache__", ".pytest_cache", "node_modules"]
            ):
                continue

            try:
                content = py_file.read_text()
                lines = content.split("\n")

                for i, line in enumerate(lines, 1):
                    # Look for TODO, FIXME, HACK, XXX comments
                    match = re.search(r"#\s*(TODO|FIXME|HACK|XXX):?\s*(.+)$", line, re.IGNORECASE)
                    if match:
                        tag = match.group(1).upper()
                        task_text = match.group(2).strip()

                        priority = 2 if tag == "FIXME" else 3

                        tasks.append(
                            Task(
                                title=f"{tag}: {task_text[:80]}",
                                description=task_text,
                                priority=priority,
                                complexity="simple",
                                estimated_hours=1.0,
                                category="bug" if tag == "FIXME" else "feature",
                                dependencies=[],
                                source_file=str(py_file),
                                line_number=i,
                            )
                        )
            except Exception as e:
                logger.debug(f"Error scanning {py_file}: {e}")

        return tasks

    def _scan_claude_files(self) -> List[Task]:
        """Extract guidance from CLAUDE.md files."""
        tasks = []
        claude_files = list(self.project_path.rglob("CLAUDE.md"))

        for claude_file in claude_files:
            try:
                content = claude_file.read_text()
                # Look for "Common Issues" or "Known Issues" sections
                if "Common Issues" in content or "Known Issues" in content:
                    tasks.extend(self._parse_todo_content(content, str(claude_file)))
            except Exception as e:
                logger.warning(f"Error reading {claude_file}: {e}")

        return tasks

    def _infer_priority(self, text: str, section: str) -> int:
        """Infer priority from text and section."""
        text_lower = text.lower()
        section_lower = section.lower()

        # Priority 1: Critical/Urgent
        if any(word in text_lower for word in ["critical", "urgent", "blocking", "asap"]):
            return 1
        if any(word in section_lower for word in ["priority", "critical", "blocking"]):
            return 1

        # Priority 2: High
        if any(word in text_lower for word in ["important", "fix", "bug", "error"]):
            return 2
        if "fix" in section_lower or "bug" in section_lower:
            return 2

        # Priority 3: Medium (default)
        # Priority 4: Low
        if any(word in text_lower for word in ["nice to have", "wish", "future", "someday"]):
            return 4

        # Priority 5: Very low
        if any(word in text_lower for word in ["maybe", "optional"]):
            return 5

        return 3  # Default medium priority

    def _infer_complexity(self, text: str) -> str:
        """Infer task complexity from text."""
        text_lower = text.lower()

        # Complex indicators
        complex_words = [
            "architecture",
            "refactor",
            "migration",
            "framework",
            "integration",
            "system",
            "redesign",
            "rebuild",
        ]
        if any(word in text_lower for word in complex_words):
            return "complex"

        # Simple indicators
        simple_words = ["add", "update", "fix typo", "rename", "document", "comment"]
        if any(word in text_lower for word in simple_words):
            return "simple"

        # Default to medium
        return "medium"

    def _estimate_hours(self, complexity: str) -> float:
        """Estimate hours based on complexity."""
        estimates = {"simple": 1.0, "medium": 4.0, "complex": 16.0}
        return estimates.get(complexity, 4.0)

    def _infer_category(self, text: str, section: str) -> str:
        """Infer task category."""
        text_lower = text.lower()
        section_lower = section.lower()

        if any(word in text_lower for word in ["test", "testing", "verify"]):
            return "test"
        if any(word in text_lower for word in ["deploy", "deployment", "release"]):
            return "deployment"
        if any(word in text_lower for word in ["document", "docs", "readme"]):
            return "documentation"
        if any(word in text_lower for word in ["fix", "bug", "error", "issue"]):
            return "bug"

        return "feature"


class MilestonePlanner:
    """Generates milestone plans from tasks."""

    def __init__(self, project_name: str):
        self.project_name = project_name

    def generate_milestones(self, tasks: List[Task]) -> List[Milestone]:
        """Generate milestone plans from tasks."""
        if not tasks:
            return []

        milestones = []

        # Group tasks by category and priority
        grouped = self._group_tasks(tasks)

        # Create milestones for each logical grouping
        milestones.extend(self._create_planning_milestone(grouped))
        milestones.extend(self._create_development_milestones(grouped))
        milestones.extend(self._create_testing_milestone(grouped))
        milestones.extend(self._create_deployment_milestone(grouped))

        return milestones

    def _group_tasks(self, tasks: List[Task]) -> Dict[str, List[Task]]:
        """Group tasks by category."""
        grouped = defaultdict(list)
        for task in tasks:
            grouped[task.category].append(task)

        # Sort each group by priority
        for category in grouped:
            grouped[category].sort(key=lambda t: (t.priority, -t.estimated_hours))

        return grouped

    def _create_planning_milestone(self, grouped: Dict[str, List[Task]]) -> List[Milestone]:
        """Create planning/setup milestone."""
        planning_tasks = []

        # Documentation tasks
        if "documentation" in grouped:
            planning_tasks.extend(grouped["documentation"][:5])  # Top 5 doc tasks

        # High priority setup tasks
        for category in grouped:
            planning_tasks.extend(
                [
                    t
                    for t in grouped[category]
                    if t.priority == 1 and "setup" in t.description.lower()
                ]
            )

        if not planning_tasks:
            return []

        total_hours = sum(t.estimated_hours for t in planning_tasks)
        start_date = datetime.now()
        target_date = start_date + timedelta(days=max(3, int(total_hours / 8)))

        return [
            Milestone(
                id=f"{self.project_name}_planning",
                name=f"{self.project_name.title()} - Planning & Setup",
                description="Initial planning, documentation, and project setup",
                phase="planning",
                start_date=start_date.isoformat(),
                target_date=target_date.isoformat(),
                tasks=planning_tasks,
                total_hours=total_hours,
            )
        ]

    def _create_development_milestones(self, grouped: Dict[str, List[Task]]) -> List[Milestone]:
        """Create development milestones."""
        milestones = []

        # Features milestone
        if "feature" in grouped and grouped["feature"]:
            features = grouped["feature"]
            # Split into multiple milestones if many features
            chunk_size = 10
            for i in range(0, len(features), chunk_size):
                chunk = features[i : i + chunk_size]
                total_hours = sum(t.estimated_hours for t in chunk)

                start_date = datetime.now() + timedelta(days=7 * len(milestones))
                target_date = start_date + timedelta(days=max(7, int(total_hours / 8)))

                milestones.append(
                    Milestone(
                        id=f"{self.project_name}_dev_{i//chunk_size + 1}",
                        name=f"{self.project_name.title()} - Development Phase {i//chunk_size + 1}",
                        description=f"Feature implementation: {len(chunk)} features",
                        phase="development",
                        start_date=start_date.isoformat(),
                        target_date=target_date.isoformat(),
                        tasks=chunk,
                        total_hours=total_hours,
                    )
                )

        # Bugs milestone
        if "bug" in grouped and grouped["bug"]:
            bugs = grouped["bug"][:15]  # Top 15 bugs
            total_hours = sum(t.estimated_hours for t in bugs)

            start_date = datetime.now() + timedelta(days=7 * len(milestones))
            target_date = start_date + timedelta(days=max(5, int(total_hours / 8)))

            milestones.append(
                Milestone(
                    id=f"{self.project_name}_bugfix",
                    name=f"{self.project_name.title()} - Bug Fixes",
                    description=f"Critical bug fixes: {len(bugs)} issues",
                    phase="development",
                    start_date=start_date.isoformat(),
                    target_date=target_date.isoformat(),
                    tasks=bugs,
                    total_hours=total_hours,
                )
            )

        return milestones

    def _create_testing_milestone(self, grouped: Dict[str, List[Task]]) -> List[Milestone]:
        """Create testing milestone."""
        if "test" not in grouped or not grouped["test"]:
            return []

        test_tasks = grouped["test"][:10]  # Top 10 test tasks
        total_hours = sum(t.estimated_hours for t in test_tasks)

        start_date = datetime.now() + timedelta(days=14)
        target_date = start_date + timedelta(days=max(5, int(total_hours / 8)))

        return [
            Milestone(
                id=f"{self.project_name}_testing",
                name=f"{self.project_name.title()} - Testing",
                description=f"Testing and QA: {len(test_tasks)} test suites",
                phase="testing",
                start_date=start_date.isoformat(),
                target_date=target_date.isoformat(),
                tasks=test_tasks,
                total_hours=total_hours,
            )
        ]

    def _create_deployment_milestone(self, grouped: Dict[str, List[Task]]) -> List[Milestone]:
        """Create deployment milestone."""
        if "deployment" not in grouped or not grouped["deployment"]:
            return []

        deploy_tasks = grouped["deployment"]
        total_hours = sum(t.estimated_hours for t in deploy_tasks)

        start_date = datetime.now() + timedelta(days=21)
        target_date = start_date + timedelta(days=max(3, int(total_hours / 8)))

        return [
            Milestone(
                id=f"{self.project_name}_deployment",
                name=f"{self.project_name.title()} - Deployment",
                description=f"Deployment and release: {len(deploy_tasks)} tasks",
                phase="deployment",
                start_date=start_date.isoformat(),
                target_date=target_date.isoformat(),
                tasks=deploy_tasks,
                total_hours=total_hours,
            )
        ]


class MilestoneWorker:
    """
    Milestone planning worker.

    The worker:
    1. Claims 'milestone' tasks from the architect task queue
    2. Scans active projects for work items
    3. Generates milestone plans
    4. Outputs to milestones directory
    5. Reports results back to architect
    """

    def __init__(self, worker_id: str = None, poll_interval: int = 300):  # 5 minutes
        import uuid

        self.worker_id = worker_id or f"milestone-worker-{uuid.uuid4().hex[:8]}"
        self.poll_interval = poll_interval
        self._running = False
        self._current_task = None

    def start(self):
        """Start the worker."""
        self._running = True
        logger.info(f"Starting Milestone Worker: {self.worker_id}")
        logger.info(f"Dashboard: {DASHBOARD_URL}")
        logger.info(f"Project Root: {PROJECT_ROOT}")
        logger.info(f"Milestones Output: {MILESTONES_DIR}")

        # Register with dashboard
        self._register()

        # Main loop
        while self._running:
            try:
                # Heartbeat
                self._heartbeat()

                # Claim task
                task = self._claim_task()

                if task:
                    self._current_task = task
                    logger.info(f"Processing milestone task: {task.get('id')}")

                    try:
                        result = self._run_milestone_task(task)
                        self._complete_task(task["id"], result)
                    except Exception as e:
                        logger.error(f"Milestone task failed: {e}", exc_info=True)
                        self._fail_task(task["id"], str(e))
                    finally:
                        self._current_task = None
                else:
                    time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                self._running = False
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
                time.sleep(30)

        logger.info("Milestone Worker stopped")

    def stop(self):
        """Stop the worker."""
        self._running = False

    def _register(self):
        """Register with architect dashboard."""
        try:
            import requests

            requests.post(
                f"{DASHBOARD_URL}/api/workers/register",
                json={
                    "id": self.worker_id,
                    "worker_type": "milestone",
                    "capabilities": ["milestone", "planning", "project_scan"],
                },
                timeout=5,
            )
            logger.info("Registered with dashboard")
        except Exception as e:
            logger.warning(f"Could not register: {e}")

    def _heartbeat(self):
        """Send heartbeat."""
        try:
            import requests

            requests.post(
                f"{DASHBOARD_URL}/api/workers/{self.worker_id}/heartbeat",
                json={
                    "status": "busy" if self._current_task else "idle",
                    "current_task_id": self._current_task.get("id") if self._current_task else None,
                },
                timeout=5,
            )
        except Exception:
            pass

    def _claim_task(self) -> Optional[Dict]:
        """Claim a milestone task from the queue."""
        try:
            import requests

            resp = requests.post(
                f"{DASHBOARD_URL}/api/tasks/claim",
                json={
                    "worker_id": self.worker_id,
                    "task_types": ["milestone", "planning", "project_scan"],
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("task")
            return None
        except Exception as e:
            logger.debug(f"Could not claim task: {e}")
            return None

    def _complete_task(self, task_id: int, result: Dict):
        """Mark task completed."""
        try:
            import requests

            requests.post(
                f"{DASHBOARD_URL}/api/tasks/{task_id}/complete",
                json={"worker_id": self.worker_id, "result": result},
                timeout=10,
            )
        except Exception as e:
            logger.error(f"Could not complete task: {e}")

    def _fail_task(self, task_id: int, error: str):
        """Mark task failed."""
        try:
            import requests

            requests.post(
                f"{DASHBOARD_URL}/api/tasks/{task_id}/fail",
                json={"worker_id": self.worker_id, "error": error},
                timeout=10,
            )
        except Exception as e:
            logger.error(f"Could not fail task: {e}")

    def _run_milestone_task(self, task: Dict) -> Dict:
        """Run a milestone planning task."""
        task_data = task.get("task_data", {})

        # What projects to scan?
        project_name = task_data.get("project")

        if project_name:
            # Scan specific project
            projects = {project_name: ACTIVE_PROJECTS.get(project_name)}
            if not projects[project_name]:
                raise ValueError(f"Unknown project: {project_name}")
        else:
            # Scan all active projects
            projects = ACTIVE_PROJECTS

        results = {}

        for name, config in projects.items():
            logger.info(f"Scanning project: {name}")

            # Add name to config
            config_with_name = {**config, "name": name}

            # Scan for tasks
            scanner = MilestoneScanner(config_with_name)
            tasks = scanner.scan()

            logger.info(f"Found {len(tasks)} tasks in {name}")

            # Generate milestones
            planner = MilestonePlanner(name)
            milestones = planner.generate_milestones(tasks)

            logger.info(f"Generated {len(milestones)} milestones for {name}")

            # Save to file
            output_file = (
                MILESTONES_DIR
                / f"{name}_milestones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            output_data = {
                "project": name,
                "generated_at": datetime.now().isoformat(),
                "total_tasks": len(tasks),
                "total_milestones": len(milestones),
                "milestones": [m.to_dict() for m in milestones],
                "tasks_by_category": self._categorize_tasks(tasks),
            }

            output_file.write_text(json.dumps(output_data, indent=2))
            logger.info(f"Saved milestone plan to {output_file}")

            # Generate summary report
            summary_file = MILESTONES_DIR / f"{name}_summary.md"
            self._generate_summary_report(name, milestones, tasks, summary_file)

            results[name] = {
                "tasks_found": len(tasks),
                "milestones_created": len(milestones),
                "output_file": str(output_file),
                "summary_file": str(summary_file),
            }

        return {"success": True, "projects_scanned": list(projects.keys()), "results": results}

    def _categorize_tasks(self, tasks: List[Task]) -> Dict:
        """Categorize tasks for reporting."""
        categories = defaultdict(int)
        priorities = defaultdict(int)
        complexities = defaultdict(int)

        for task in tasks:
            categories[task.category] += 1
            priorities[f"priority_{task.priority}"] += 1
            complexities[task.complexity] += 1

        return {
            "by_category": dict(categories),
            "by_priority": dict(priorities),
            "by_complexity": dict(complexities),
        }

    def _generate_summary_report(
        self, project_name: str, milestones: List[Milestone], tasks: List[Task], output_file: Path
    ):
        """Generate a human-readable summary report."""
        report = []
        report.append(f"# {project_name.title()} - Milestone Plan")
        report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\n## Summary\n")
        report.append(f"- Total Tasks: {len(tasks)}")
        report.append(f"- Total Milestones: {len(milestones)}")
        report.append(f"- Estimated Total Hours: {sum(m.total_hours for m in milestones):.1f}")
        report.append(
            f"- Estimated Duration: {max((m.total_hours for m in milestones), default=0) / 8:.1f} days"
        )

        # Task breakdown
        report.append(f"\n## Task Breakdown\n")
        categories = defaultdict(int)
        priorities = defaultdict(int)
        for task in tasks:
            categories[task.category] += 1
            priorities[task.priority] += 1

        report.append("### By Category")
        for cat, count in sorted(categories.items()):
            report.append(f"- {cat.title()}: {count}")

        report.append("\n### By Priority")
        for pri in range(1, 6):
            count = priorities.get(pri, 0)
            if count > 0:
                report.append(f"- Priority {pri}: {count}")

        # Milestones
        report.append(f"\n## Milestones\n")
        for i, milestone in enumerate(milestones, 1):
            report.append(f"### {i}. {milestone.name}")
            report.append(f"- Phase: {milestone.phase.title()}")
            report.append(f"- Start: {milestone.start_date[:10]}")
            report.append(f"- Target: {milestone.target_date[:10]}")
            report.append(f"- Tasks: {len(milestone.tasks)}")
            report.append(f"- Estimated Hours: {milestone.total_hours:.1f}")
            report.append(f"\n**Tasks:**")

            for task in milestone.tasks[:10]:  # Show first 10
                report.append(f"- [{task.complexity[0].upper()}] {task.title}")

            if len(milestone.tasks) > 10:
                report.append(f"- ... and {len(milestone.tasks) - 10} more")
            report.append("")

        output_file.write_text("\n".join(report))


def scan_now(project_name: Optional[str] = None):
    """Scan projects and generate milestones immediately."""
    logger.info("Running immediate milestone scan...")

    worker = MilestoneWorker()
    task = {"id": 0, "task_data": {"project": project_name} if project_name else {}}

    result = worker._run_milestone_task(task)

    print("\n=== Milestone Scan Results ===\n")
    print(f"Projects scanned: {', '.join(result['projects_scanned'])}")
    print("\nResults:")
    for project, data in result["results"].items():
        print(f"\n{project}:")
        print(f"  Tasks found: {data['tasks_found']}")
        print(f"  Milestones created: {data['milestones_created']}")
        print(f"  Output: {data['output_file']}")
        print(f"  Summary: {data['summary_file']}")


def main():
    parser = argparse.ArgumentParser(description="Milestone Planning Worker")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--scan", action="store_true", help="Scan and generate now")
    parser.add_argument("--project", type=str, help="Scan specific project")
    parser.add_argument(
        "--poll-interval", type=int, default=300, help="Poll interval in seconds (default: 300)"
    )
    args = parser.parse_args()

    if args.scan:
        scan_now(args.project)
        return

    if args.daemon:
        # Daemonize
        if os.fork() > 0:
            sys.exit(0)
        os.setsid()
        if os.fork() > 0:
            sys.exit(0)
        PID_FILE.write_text(str(os.getpid()))

    worker = MilestoneWorker(poll_interval=args.poll_interval)

    def signal_handler(sig, frame):
        worker.stop()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    worker.start()


if __name__ == "__main__":
    main()
