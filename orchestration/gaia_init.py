#!/usr/bin/env python3
"""
GAIA Initialization System
==========================

Initializes GAIA orchestration with:
- Architect agent group setup
- Manager session groups
- Worker session pools
- Lock system initialization
- Metrics collection setup

GAIA runs from: /Users/jgirmay/Desktop/gitrepo/GAIA_HOME/
Repositories are worked on via lock-based task assignment
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

GAIA_HOME = Path("/Users/jgirmay/Desktop/gitrepo/GAIA_HOME")
ORCHESTRATION_DIR = GAIA_HOME / "orchestration"
LOCKS_DIR = GAIA_HOME / "locks"
SESSIONS_DIR = GAIA_HOME / "sessions"
METRICS_DIR = GAIA_HOME / "metrics"


class ArchitectAgentGroup:
    """Architect agent group for strategic coordination"""

    def __init__(self, group_name: str, role: str, sessions: List[str]):
        self.group_name = group_name
        self.role = role  # "strategic", "tactical", "oversight"
        self.sessions = sessions
        self.created_at = datetime.now().isoformat()
        self.status = "initialized"

    def to_dict(self) -> Dict:
        return {
            "group_name": self.group_name,
            "role": self.role,
            "sessions": self.sessions,
            "created_at": self.created_at,
            "status": self.status,
        }


class ManagerGroup:
    """Manager session group for tactical execution with architect oversight"""

    def __init__(
        self,
        group_name: str,
        module: str,
        manager_sessions: List[str],
        architect_oversight: List[str],
    ):
        self.group_name = group_name
        self.module = module  # "reading", "math", "piano", "typing", "dashboard"
        self.manager_sessions = manager_sessions
        self.architect_oversight = architect_oversight
        self.created_at = datetime.now().isoformat()
        self.status = "initialized"

    def to_dict(self) -> Dict:
        return {
            "group_name": self.group_name,
            "module": self.module,
            "manager_sessions": self.manager_sessions,
            "architect_oversight": self.architect_oversight,
            "created_at": self.created_at,
            "status": self.status,
        }


class WorkerPool:
    """Worker session pool for task execution with architect oversight"""

    def __init__(
        self,
        pool_name: str,
        provider: str,
        session_count: int,
        base_name: str,
        architect_oversight: Optional[List[str]] = None,
    ):
        self.pool_name = pool_name
        self.provider = provider  # "claude", "codex", "comet", "ollama"
        self.session_count = session_count
        self.base_name = base_name
        self.sessions = [f"{base_name}_{i}" for i in range(1, session_count + 1)]
        self.architect_oversight = architect_oversight or [
            "gaia_linter",
            "inspector",
        ]  # Default oversight
        self.created_at = datetime.now().isoformat()
        self.status = "initialized"

    def to_dict(self) -> Dict:
        return {
            "pool_name": self.pool_name,
            "provider": self.provider,
            "session_count": self.session_count,
            "base_name": self.base_name,
            "sessions": self.sessions,
            "architect_oversight": self.architect_oversight,
            "created_at": self.created_at,
            "status": self.status,
        }


class GAIAOrchestrator:
    """Main GAIA orchestration system"""

    def __init__(self):
        self.gaia_home = GAIA_HOME
        self.architect_groups: List[ArchitectAgentGroup] = []
        self.manager_groups: List[ManagerGroup] = []
        self.worker_pools: List[WorkerPool] = []
        self.initialized_at = datetime.now().isoformat()

        logger.info(f"GAIA Orchestrator initialized at {self.gaia_home}")

    def setup_architect_agents(self):
        """Initialize architect agent groups"""
        logger.info("Setting up Architect Agent Groups...")

        # Strategic Level - System-wide decisions
        strategic = ArchitectAgentGroup(
            group_name="Architect-Strategic",
            role="strategic",
            sessions=[
                "arch_lead",  # Leadership
                "claude_architect",  # Architecture decisions
                "gaia_orchestrator",  # GAIA controller
            ],
        )
        self.architect_groups.append(strategic)
        logger.info(f"✓ {strategic.group_name} initialized")

        # Oversight Level - Monitor and validate
        oversight = ArchitectAgentGroup(
            group_name="Architect-Oversight",
            role="oversight",
            sessions=[
                "inspector",  # Code inspection
                "gaia_linter",  # Code quality
                "pr_review1",  # PR oversight
                "pr_review2",
                "pr_review3",
            ],
        )
        self.architect_groups.append(oversight)
        logger.info(f"✓ {oversight.group_name} initialized")

        # Coordination Level - Cross-cutting concerns
        coordination = ArchitectAgentGroup(
            group_name="Architect-Coordination",
            role="tactical",
            sessions=[
                "foundation",  # Foundation/integration
                "comparison",  # Comparative analysis
                "codex_worker",  # Code generation coordination
            ],
        )
        self.architect_groups.append(coordination)
        logger.info(f"✓ {coordination.group_name} initialized")

        return self.architect_groups

    def setup_manager_groups(self):
        """Initialize manager groups per module with architect oversight"""
        logger.info("Setting up Manager Groups with Architect Oversight...")

        modules = [
            ("reading", ["reading_architect", "reading_impl1", "reading_impl2", "reading_test"]),
            ("math", ["inspector", "dev_math_1", "dev_math_2"]),
            ("piano", ["foundation", "dev_piano_1", "dev_piano_2"]),
            ("typing", ["comparison", "dev_typing_1", "dev_typing_2"]),
            ("dashboard", ["claude_architect", "dev_dashboard_1", "dev_dashboard_2"]),
        ]

        for module, architect_agents in modules:
            manager_group = ManagerGroup(
                group_name=f"Manager-{module.capitalize()}",
                module=module,
                manager_sessions=[
                    f"manager_{module}",  # Primary manager
                    f"dev_{module}_1",  # Developer 1
                    f"dev_{module}_2",  # Developer 2
                    f"tester_{module}",  # Tester
                ],
                architect_oversight=architect_agents,  # Architect oversight per module
            )
            self.manager_groups.append(manager_group)
            logger.info(
                f"✓ {manager_group.group_name} initialized with "
                f"oversight: {', '.join(architect_agents)}"
            )

        return self.manager_groups

    def setup_worker_pools(self):
        """Initialize worker session pools"""
        logger.info("Setting up Worker Pools...")

        # Claude AI workers
        claude_pool = WorkerPool(
            pool_name="Claude-Workers",
            provider="claude",
            session_count=5,
            base_name="dev_worker",
        )
        self.worker_pools.append(claude_pool)
        logger.info(f"✓ {claude_pool.pool_name} ({len(claude_pool.sessions)} sessions)")

        # Codex workers
        codex_pool = WorkerPool(
            pool_name="Codex-Workers",
            provider="codex",
            session_count=3,
            base_name="codex_worker",
        )
        self.worker_pools.append(codex_pool)
        logger.info(f"✓ {codex_pool.pool_name} ({len(codex_pool.sessions)} sessions)")

        # PR implementation workers (with PR review oversight)
        pr_impl_pool = WorkerPool(
            pool_name="PR-Implementation",
            provider="codex",
            session_count=4,
            base_name="pr_impl",
            architect_oversight=["pr_review1", "pr_review2", "pr_review3", "inspector"],
        )
        self.worker_pools.append(pr_impl_pool)
        logger.info(
            f"✓ {pr_impl_pool.pool_name} ({len(pr_impl_pool.sessions)} sessions) "
            f"with PR review oversight"
        )

        # PR integration workers (with integration oversight)
        pr_integ_pool = WorkerPool(
            pool_name="PR-Integration",
            provider="claude",
            session_count=3,
            base_name="pr_integ",
            architect_oversight=["foundation", "comparison", "gaia_linter"],
        )
        self.worker_pools.append(pr_integ_pool)
        logger.info(
            f"✓ {pr_integ_pool.pool_name} ({len(pr_integ_pool.sessions)} sessions) "
            f"with integration oversight"
        )

        return self.worker_pools

    def save_configuration(self):
        """Save GAIA configuration to file"""
        config = {
            "gaia_home": str(GAIA_HOME),
            "initialized_at": self.initialized_at,
            "architect_groups": [g.to_dict() for g in self.architect_groups],
            "manager_groups": [g.to_dict() for g in self.manager_groups],
            "worker_pools": [p.to_dict() for p in self.worker_pools],
            "lock_system": {
                "enabled": True,
                "locks_dir": str(LOCKS_DIR),
                "auto_cleanup": True,
                "lock_timeout_hours": 2,
            },
            "metrics": {
                "enabled": True,
                "metrics_dir": str(METRICS_DIR),
                "collection_interval": 60,
            },
        }

        config_file = ORCHESTRATION_DIR / "gaia_config.json"
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        logger.info(f"✓ Configuration saved to {config_file}")
        return config

    def initialize(self):
        """Full GAIA initialization"""
        logger.info("=" * 70)
        logger.info("GAIA ORCHESTRATION INITIALIZATION")
        logger.info("=" * 70)

        # Create directories
        GAIA_HOME.mkdir(parents=True, exist_ok=True)
        ORCHESTRATION_DIR.mkdir(parents=True, exist_ok=True)
        LOCKS_DIR.mkdir(parents=True, exist_ok=True)
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        METRICS_DIR.mkdir(parents=True, exist_ok=True)

        # Setup groups
        self.setup_architect_agents()
        self.setup_manager_groups()
        self.setup_worker_pools()

        # Save configuration
        config = self.save_configuration()

        logger.info("")
        logger.info("GAIA INITIALIZATION COMPLETE ✓")
        logger.info("=" * 70)
        logger.info(f"Architect Agent Groups: {len(self.architect_groups)}")
        logger.info(f"Manager Groups: {len(self.manager_groups)}")
        logger.info(f"Worker Pools: {len(self.worker_pools)}")
        logger.info(f"Total Worker Sessions: {sum(p.session_count for p in self.worker_pools)}")
        logger.info("")
        logger.info(f"GAIA Home: {GAIA_HOME}")
        logger.info(f"Config: {ORCHESTRATION_DIR}/gaia_config.json")
        logger.info("")

        return config


def main():
    """Initialize GAIA"""
    try:
        orchestrator = GAIAOrchestrator()
        config = orchestrator.initialize()

        # Print summary
        print("\n" + "=" * 70)
        print("GAIA SYSTEM READY FOR AUTONOMOUS OPERATION")
        print("=" * 70)
        print(f"\nArchitect Agent Groups ({len(config['architect_groups'])}):")
        for group in config["architect_groups"]:
            print(f"  • {group['group_name']} ({group['role']})")
            print(f"    Sessions: {', '.join(group['sessions'][:3])}...")

        print(f"\nManager Groups ({len(config['manager_groups'])}):")
        for group in config["manager_groups"]:
            print(f"  • {group['group_name']} (module: {group['module']})")

        print(f"\nWorker Pools ({len(config['worker_pools'])}):")
        for pool in config["worker_pools"]:
            print(f"  • {pool['pool_name']} ({pool['provider']}): {pool['session_count']} sessions")

        print(f"\nLock System:")
        print(f"  • Enabled: {config['lock_system']['enabled']}")
        print(f"  • Directory: {config['lock_system']['locks_dir']}")
        print(f"  • Timeout: {config['lock_system']['lock_timeout_hours']} hours")

        print("\n✓ GAIA is ready to orchestrate autonomous development")
        print("=" * 70 + "\n")

    except Exception as e:
        logger.error(f"Failed to initialize GAIA: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
