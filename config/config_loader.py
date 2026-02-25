#!/usr/bin/env python3
"""
Configuration Loader - Proof of Concept
Demonstrates data-driven architecture by loading business logic from YAML files
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class ConfigLoader:
    """Load and merge configuration from YAML files."""

    def __init__(self, config_dir: str = "config", environment: str = "development"):
        self.config_dir = Path(config_dir)
        self.environment = environment
        self._cache = {}

    def load(self, config_name: str) -> Dict[str, Any]:
        """
        Load configuration from YAML files with environment overrides.

        Loading order:
        1. config/base/{config_name}.yaml
        2. config/environments/{environment}.yaml (overrides)
        3. config/local/overrides.yaml (overrides, gitignored)

        Args:
            config_name: Name of config file (without .yaml extension)

        Returns:
            Merged configuration dictionary
        """
        if config_name in self._cache:
            return self._cache[config_name]

        # Load base config
        base_path = self.config_dir / "base" / f"{config_name}.yaml"
        if not base_path.exists():
            raise FileNotFoundError(f"Base config not found: {base_path}")

        with open(base_path) as f:
            config = yaml.safe_load(f)

        # Apply environment overrides (optional)
        env_path = self.config_dir / "environments" / f"{self.environment}.yaml"
        if env_path.exists():
            with open(env_path) as f:
                env_config = yaml.safe_load(f)
                config = self._merge_config(config, env_config.get(config_name, {}))

        # Apply local overrides (optional)
        local_path = self.config_dir / "local" / "overrides.yaml"
        if local_path.exists():
            with open(local_path) as f:
                local_config = yaml.safe_load(f)
                config = self._merge_config(config, local_config.get(config_name, {}))

        self._cache[config_name] = config
        return config

    def _merge_config(self, base: Dict, override: Dict) -> Dict:
        """Deep merge override config into base config."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result


# ============================================================================
# Example Usage: SLA Rules
# ============================================================================

class SLAManager:
    """Manage task SLA rules from YAML configuration."""

    def __init__(self, config_loader: ConfigLoader):
        self.config = config_loader.load("sla_rules")
        self.sla_targets = self.config["sla_targets"]
        self.escalation_rules = self.config["escalation_rules"]

    def get_task_sla(self, task_type: str) -> Dict[str, Any]:
        """Get SLA configuration for a task type."""
        return self.sla_targets.get(task_type, self.sla_targets["default"])

    def calculate_sla_status(
        self,
        task_type: str,
        created_at: datetime,
        completed_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate SLA status for a task.

        Returns:
            status: 'ok', 'warning', 'breached'
            elapsed_minutes: Time elapsed since creation
            target_minutes: SLA target
            percent_used: Percentage of SLA time used
            remaining_minutes: Time remaining (negative if breached)
        """
        sla = self.get_task_sla(task_type)
        target = sla["target_minutes"]
        warning_threshold = sla["warning_percent"]
        critical_threshold = sla["critical_percent"]

        now = completed_at or datetime.now()
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        elapsed = (now - created_at).total_seconds() / 60
        percent_used = (elapsed / target) * 100 if target > 0 else 100

        # Determine status based on escalation rules
        status = "ok"
        for rule in self.escalation_rules:
            condition = rule["condition"]
            if "critical_percent" in condition and percent_used >= critical_threshold:
                status = "breached"
                break
            elif "warning_percent" in condition and percent_used >= warning_threshold:
                status = "warning"

        return {
            "status": status,
            "elapsed_minutes": round(elapsed, 1),
            "target_minutes": target,
            "percent_used": round(percent_used, 1),
            "remaining_minutes": round(target - elapsed, 1),
            "warning_threshold": warning_threshold,
            "critical_threshold": critical_threshold,
        }


# ============================================================================
# Example Usage: Routing Rules
# ============================================================================

class TaskRouter:
    """Route tasks to Claude sessions based on YAML rules."""

    def __init__(self, config_loader: ConfigLoader):
        self.config = config_loader.load("routing_rules")
        self.routing_rules = self.config["environment_routing"]
        self.excluded_sessions = set(self.config["excluded_sessions"])
        self.supported_providers = {
            p["name"]: p for p in self.config["supported_providers"]
        }

    def get_routing_rule(self, task_type: str) -> Dict[str, Any]:
        """Get routing rule for a task type."""
        if task_type not in self.routing_rules:
            # Fallback to default routing
            return self.routing_rules.get("feature_development", {})
        return self.routing_rules[task_type]

    def route_task(self, task_type: str, priority: int = 5) -> Dict[str, Any]:
        """
        Route a task to the appropriate session.

        Returns:
            preferred_sessions: List of session names
            requires_env: Whether to create test environment
            timeout_minutes: Task timeout
            priority: Adjusted priority
        """
        rule = self.get_routing_rule(task_type)

        return {
            "task_type": task_type,
            "preferred_sessions": rule.get("preferred_sessions", []),
            "requires_env": rule.get("requires_env", False),
            "port_range": rule.get("port_range", [6001, 6010]),
            "auto_create_env": rule.get("auto_create_env", True),
            "merge_via_pr": rule.get("merge_via_pr", True),
            "priority": max(priority, rule.get("priority", 5)),
            "timeout_minutes": rule.get("timeout_minutes", 30),
            "max_retries": rule.get("max_retries", 3),
        }

    def is_session_excluded(self, session_name: str) -> bool:
        """Check if session should be excluded from task assignment."""
        return session_name in self.excluded_sessions


# ============================================================================
# Example Usage: Query Templates
# ============================================================================

class QueryManager:
    """Manage database queries from YAML templates."""

    def __init__(self, config_loader: ConfigLoader):
        self.config = config_loader.load("queries")
        self.queries = self.config["queries"]
        self.indexes = self.config["indexes"]

    def get_query(self, query_name: str) -> Dict[str, Any]:
        """Get query definition by name."""
        if query_name not in self.queries:
            raise ValueError(f"Query '{query_name}' not found in configuration")
        return self.queries[query_name]

    def build_query(self, query_name: str, params: Dict[str, Any]) -> str:
        """
        Build SQL query with parameters.

        Args:
            query_name: Name of query template
            params: Parameter values

        Returns:
            SQL query string with parameters substituted
        """
        query_def = self.get_query(query_name)
        sql = query_def["sql"]

        # Validate required parameters
        for param_def in query_def.get("params", []):
            param_name = param_def["name"]
            if param_def.get("required", False) and param_name not in params:
                raise ValueError(f"Required parameter '{param_name}' not provided")

            # Apply defaults
            if param_name not in params and "default" in param_def:
                params[param_name] = param_def["default"]

        return sql, params

    def get_cache_ttl(self, query_name: str) -> int:
        """Get cache TTL for a query."""
        query_def = self.get_query(query_name)
        return query_def.get("cache_ttl", self.config["optimization"]["default_cache_ttl"])


# ============================================================================
# Demo
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Data-Driven Architecture - Proof of Concept")
    print("=" * 70)

    # Initialize config loader
    loader = ConfigLoader(config_dir=".", environment="development")

    # Demo 1: SLA Manager
    print("\n[Demo 1] SLA Manager")
    print("-" * 70)
    sla_manager = SLAManager(loader)

    # Check SLA for a bug fix task
    created = datetime.now()
    completed = datetime.now()  # Completed immediately
    sla_status = sla_manager.calculate_sla_status("bug_fix", created, completed)
    print(f"Task Type: bug_fix")
    print(f"SLA Status: {sla_status['status']}")
    print(f"Elapsed: {sla_status['elapsed_minutes']} min")
    print(f"Target: {sla_status['target_minutes']} min")
    print(f"Percent Used: {sla_status['percent_used']}%")

    # Demo 2: Task Router
    print("\n[Demo 2] Task Router")
    print("-" * 70)
    router = TaskRouter(loader)

    # Route a bug fix task
    routing = router.route_task("bug_fix", priority=9)
    print(f"Task Type: {routing['task_type']}")
    print(f"Preferred Sessions: {routing['preferred_sessions']}")
    print(f"Requires Env: {routing['requires_env']}")
    print(f"Priority: {routing['priority']}")
    print(f"Timeout: {routing['timeout_minutes']} min")

    # Demo 3: Query Manager
    print("\n[Demo 3] Query Manager")
    print("-" * 70)
    query_manager = QueryManager(loader)

    # Get a query template
    query_name = "tasks_by_status"
    query_def = query_manager.get_query(query_name)
    print(f"Query: {query_name}")
    print(f"Description: {query_def['description']}")
    print(f"Cache TTL: {query_manager.get_cache_ttl(query_name)} seconds")

    sql, params = query_manager.build_query(query_name, {"status": "pending", "limit": 10})
    print(f"\nGenerated SQL:")
    print(sql.strip())
    print(f"\nParameters: {params}")

    print("\n" + "=" * 70)
    print("✅ All demos completed successfully!")
    print("=" * 70)
    print("\nBenefits demonstrated:")
    print("  • Business logic in YAML files, not code")
    print("  • Change rules without code deployment")
    print("  • Environment-specific overrides")
    print("  • Centralized query management")
    print("  • Easy A/B testing of rules")
