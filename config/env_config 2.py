"""
Environment Variable Configuration with Validation

Provides centralized environment variable management with:
- Type validation (str, int, bool, float, path, list)
- Default values
- Required variable enforcement
- Validation rules (min/max, choices, patterns)
- Startup validation with clear error messages

Usage:
    from config.env_config import Config, validate_config

    # Access validated config
    port = Config.PORT
    debug = Config.DEBUG

    # Validate all at startup (raises ConfigError if invalid)
    validate_config()

    # Get config as dict
    config_dict = Config.to_dict()
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Base directory for relative paths
BASE_DIR = Path(__file__).resolve().parent.parent


class ConfigError(Exception):
    """Raised when configuration validation fails."""

    pass


@dataclass
class EnvVar:
    """Environment variable definition with validation."""

    name: str
    default: Any = None
    var_type: str = "str"  # str, int, bool, float, path, list
    required: bool = False
    description: str = ""
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    choices: Optional[List[Any]] = None
    pattern: Optional[str] = None  # Regex pattern for str validation
    validator: Optional[Callable[[Any], bool]] = None  # Custom validator
    sensitive: bool = False  # Don't log value if True
    deprecated: bool = False
    deprecated_message: str = ""

    def parse(self, value: str) -> Any:
        """Parse string value to target type."""
        if value is None:
            return None

        if self.var_type == "str":
            return value
        elif self.var_type == "int":
            try:
                return int(value)
            except ValueError:
                raise ConfigError(f"{self.name}: '{value}' is not a valid integer")
        elif self.var_type == "float":
            try:
                return float(value)
            except ValueError:
                raise ConfigError(f"{self.name}: '{value}' is not a valid float")
        elif self.var_type == "bool":
            return value.lower() in ("true", "1", "yes", "on")
        elif self.var_type == "path":
            path = Path(value)
            if not path.is_absolute():
                path = BASE_DIR / path
            return path
        elif self.var_type == "list":
            return [item.strip() for item in value.split(",") if item.strip()]
        else:
            return value

    def validate(self, value: Any) -> tuple[bool, str]:
        """Validate parsed value. Returns (is_valid, error_message)."""
        if value is None:
            if self.required:
                return False, f"{self.name} is required but not set"
            return True, ""

        # Check deprecated
        if self.deprecated:
            logger.warning(
                f"Environment variable {self.name} is deprecated. {self.deprecated_message}"
            )

        # Type-specific validation
        if self.var_type in ("int", "float"):
            if self.min_value is not None and value < self.min_value:
                return False, f"{self.name}: value {value} is below minimum {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"{self.name}: value {value} exceeds maximum {self.max_value}"

        if self.choices is not None and value not in self.choices:
            return (
                False,
                f"{self.name}: '{value}' is not a valid choice. Must be one of: {self.choices}",
            )

        if self.pattern and self.var_type == "str":
            if not re.match(self.pattern, value):
                return False, f"{self.name}: '{value}' does not match required pattern"

        if self.validator:
            try:
                if not self.validator(value):
                    return False, f"{self.name}: custom validation failed for value '{value}'"
            except Exception as e:
                return False, f"{self.name}: validation error - {e}"

        return True, ""

    def get_value(self) -> Any:
        """Get validated value from environment."""
        raw_value = os.environ.get(self.name)

        if raw_value is None:
            if self.required:
                raise ConfigError(f"Required environment variable {self.name} is not set")
            return self.default

        parsed = self.parse(raw_value)
        is_valid, error = self.validate(parsed)

        if not is_valid:
            raise ConfigError(error)

        return parsed


# Define all environment variables
ENV_VARS: Dict[str, EnvVar] = {
    # Application settings
    "APP_ENV": EnvVar(
        name="APP_ENV",
        default="prod",
        choices=["dev", "prod", "test", "staging"],
        description="Application environment",
    ),
    "DEBUG": EnvVar(name="DEBUG", default=False, var_type="bool", description="Enable debug mode"),
    "PORT": EnvVar(
        name="PORT",
        default=8080,
        var_type="int",
        min_value=1,
        max_value=65535,
        description="Server port",
    ),
    "HOST": EnvVar(name="HOST", default="0.0.0.0", description="Server host"),
    # Database settings
    "DATA_DIR": EnvVar(
        name="DATA_DIR",
        default=None,  # Computed based on APP_ENV
        var_type="path",
        description="Data directory path",
    ),
    "DB_PATH": EnvVar(
        name="DB_PATH",
        default=None,  # Computed based on DATA_DIR
        var_type="path",
        description="SQLite database path",
    ),
    # Security settings
    "SECRET_KEY": EnvVar(
        name="SECRET_KEY",
        default="architect-dashboard-secret-key-change-in-production",
        sensitive=True,
        description="Flask secret key for sessions",
    ),
    "ARCHITECT_USER": EnvVar(
        name="ARCHITECT_USER", default="architect", description="Admin username"
    ),
    "ARCHITECT_PASSWORD": EnvVar(
        name="ARCHITECT_PASSWORD", default="peace5", sensitive=True, description="Admin password"
    ),
    "SESSION_COOKIE_SECURE": EnvVar(
        name="SESSION_COOKIE_SECURE",
        default=False,
        var_type="bool",
        description="Use secure cookies (HTTPS only)",
    ),
    "SESSION_TIMEOUT": EnvVar(
        name="SESSION_TIMEOUT",
        default=3600,
        var_type="int",
        min_value=60,
        max_value=86400,
        description="Session timeout in seconds",
    ),
    # Network settings
    "TAILSCALE_IP": EnvVar(
        name="TAILSCALE_IP",
        default="100.112.58.92",
        pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
        description="Tailscale IP address",
    ),
    "ARCHITECT_URL": EnvVar(
        name="ARCHITECT_URL",
        default=None,  # Computed from TAILSCALE_IP
        description="Architect dashboard URL",
    ),
    "DASHBOARD_URL": EnvVar(
        name="DASHBOARD_URL",
        default=None,  # Computed from TAILSCALE_IP (alias for ARCHITECT_URL)
        description="Dashboard URL (alias for ARCHITECT_URL)",
    ),
    "VAULT_URL": EnvVar(
        name="VAULT_URL",
        default=None,  # Computed from TAILSCALE_IP
        description="Vault service URL",
    ),
    # Worker settings
    "WORKER_ID": EnvVar(name="WORKER_ID", default=None, description="Worker identifier"),
    "NODE_ID": EnvVar(name="NODE_ID", default=None, description="Node identifier"),
    "AGENT_NAME": EnvVar(
        name="AGENT_NAME", default=None, description="Agent name for identification"
    ),
    # Request logging
    "REQUEST_LOG_ENABLED": EnvVar(
        name="REQUEST_LOG_ENABLED",
        default=True,
        var_type="bool",
        description="Enable request logging",
    ),
    "REQUEST_LOG_LEVEL": EnvVar(
        name="REQUEST_LOG_LEVEL",
        default="info",
        choices=["debug", "info", "minimal"],
        description="Request logging verbosity",
    ),
    "REQUEST_LOG_FILE": EnvVar(
        name="REQUEST_LOG_FILE",
        default="/tmp/architect_requests.log",
        var_type="path",
        description="Request log file path",
    ),
    "REQUEST_LOG_MAX_BODY": EnvVar(
        name="REQUEST_LOG_MAX_BODY",
        default=1000,
        var_type="int",
        min_value=0,
        max_value=100000,
        description="Max request body size to log",
    ),
    "REQUEST_LOG_EXCLUDE": EnvVar(
        name="REQUEST_LOG_EXCLUDE",
        default="/health,/api/metrics,/socket.io",
        var_type="list",
        description="Paths to exclude from logging",
    ),
    # Chrome/browser settings
    "CHROME_DEBUG_PORT": EnvVar(
        name="CHROME_DEBUG_PORT",
        default=None,
        var_type="int",
        min_value=1,
        max_value=65535,
        description="Chrome debug port",
    ),
    "CHROME_HEADLESS": EnvVar(
        name="CHROME_HEADLESS",
        default=True,
        var_type="bool",
        description="Run Chrome in headless mode",
    ),
    "CHROME_PROFILE": EnvVar(
        name="CHROME_PROFILE", default=None, description="Chrome profile path"
    ),
    # LLM settings
    "LLM_PROVIDER": EnvVar(
        name="LLM_PROVIDER",
        default="anthropic",
        choices=["anthropic", "openai", "ollama"],
        description="LLM provider",
    ),
    "ANTHROPIC_API_KEY": EnvVar(
        name="ANTHROPIC_API_KEY", default=None, sensitive=True, description="Anthropic API key"
    ),
    "CLAUDE_MODEL": EnvVar(
        name="CLAUDE_MODEL",
        default="claude-sonnet-4-5-20250929",
        choices=[
            "claude-sonnet-4-5-20250929",  # Premium (this session)
            "claude-3-5-sonnet-20241022",  # Mid-tier
            "claude-3-5-haiku-20241022",  # Cheapest (~80% cost savings)
            "claude-opus-4-5-20251101",  # Most expensive
        ],
        description="Default Claude model for LLM client",
    ),
    "OPENAI_API_KEY": EnvVar(
        name="OPENAI_API_KEY",
        default=None,
        sensitive=True,
        description="OpenAI API key for GPT-4 failover",
    ),
    "OLLAMA_HOST": EnvVar(
        name="OLLAMA_HOST", default="http://100.112.58.92:11434", description="Ollama server host"
    ),
    "OLLAMA_MODEL": EnvVar(name="OLLAMA_MODEL", default="llama2", description="Ollama model name"),
    # LLM Failover settings
    "LLM_FAILOVER_ENABLED": EnvVar(
        name="LLM_FAILOVER_ENABLED",
        default=True,
        var_type="bool",
        description="Enable LLM provider failover",
    ),
    "LLM_DEFAULT_PROVIDER": EnvVar(
        name="LLM_DEFAULT_PROVIDER",
        default="claude",
        choices=["claude", "ollama", "openai"],
        description="Primary LLM provider",
    ),
    "LLM_PROVIDERS_CONFIG": EnvVar(
        name="LLM_PROVIDERS_CONFIG",
        default=None,
        var_type="path",
        description="Path to LLM providers config YAML",
    ),
    "LLM_FAILOVER_POLICY_CONFIG": EnvVar(
        name="LLM_FAILOVER_POLICY_CONFIG",
        default=None,
        var_type="path",
        description="Path to LLM failover policy config YAML",
    ),
    # Error daemon settings
    "ERROR_DAEMON_SESSION": EnvVar(
        name="ERROR_DAEMON_SESSION",
        default="error_fixer",
        description="tmux session for error daemon",
    ),
    # Deployment settings
    "DEPLOY_APPROVED": EnvVar(
        name="DEPLOY_APPROVED",
        default=False,
        var_type="bool",
        description="Deployment approval flag",
    ),
}


class ConfigMeta(type):
    """Metaclass to provide attribute access to config values."""

    _cache: Dict[str, Any] = {}
    _validated: bool = False

    def __getattr__(cls, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)

        if name in cls._cache:
            return cls._cache[name]

        if name in ENV_VARS:
            value = ENV_VARS[name].get_value()
            cls._cache[name] = value
            return value

        raise AttributeError(f"Unknown config variable: {name}")


class Config(metaclass=ConfigMeta):
    """
    Configuration class with environment variable access.

    Access config values as class attributes:
        Config.PORT  # Returns int
        Config.DEBUG  # Returns bool
        Config.APP_ENV  # Returns str
    """

    @classmethod
    def get(cls, name: str, default: Any = None) -> Any:
        """Get config value with optional default."""
        try:
            return getattr(cls, name)
        except AttributeError:
            return default

    @classmethod
    def to_dict(cls, include_sensitive: bool = False) -> Dict[str, Any]:
        """Get all config values as dictionary."""
        result = {}
        for name, env_var in ENV_VARS.items():
            try:
                value = env_var.get_value()
                if env_var.sensitive and not include_sensitive:
                    value = "***" if value else None
                result[name] = value
            except ConfigError:
                result[name] = None
        return result

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the config cache (useful for testing)."""
        cls._cache.clear()
        cls._validated = False

    @classmethod
    def reload(cls) -> None:
        """Reload all config values from environment."""
        cls.clear_cache()
        for name in ENV_VARS:
            try:
                getattr(cls, name)
            except ConfigError:
                pass


def validate_config(strict: bool = False) -> Dict[str, Any]:
    """
    Validate all environment variables at startup.

    Args:
        strict: If True, raise on any validation error.
                If False, log warnings for optional vars.

    Returns:
        Dict of validated config values

    Raises:
        ConfigError: If required variables are missing or invalid
    """
    errors = []
    warnings = []
    validated = {}

    for name, env_var in ENV_VARS.items():
        try:
            value = env_var.get_value()
            validated[name] = value

            # Log the value (mask sensitive)
            if env_var.sensitive:
                log_value = "***" if value else "not set"
            else:
                log_value = value
            logger.debug(f"Config: {name} = {log_value}")

        except ConfigError as e:
            if env_var.required or strict:
                errors.append(str(e))
            else:
                warnings.append(str(e))

    # Apply computed defaults
    if validated.get("DATA_DIR") is None:
        app_env = validated.get("APP_ENV", "prod")
        validated["DATA_DIR"] = BASE_DIR / "data" / app_env

    if validated.get("DB_PATH") is None:
        data_dir = validated.get("DATA_DIR", BASE_DIR / "data" / "prod")
        validated["DB_PATH"] = data_dir / "architect.db"

    if validated.get("TAILSCALE_IP"):
        tailscale_ip = validated["TAILSCALE_IP"]
        if validated.get("ARCHITECT_URL") is None:
            validated["ARCHITECT_URL"] = f"http://{tailscale_ip}:8080"
        if validated.get("DASHBOARD_URL") is None:
            validated["DASHBOARD_URL"] = f"http://{tailscale_ip}:8080"
        if validated.get("VAULT_URL") is None:
            validated["VAULT_URL"] = f"http://{tailscale_ip}:9000"

    # Log warnings
    for warning in warnings:
        logger.warning(f"Config warning: {warning}")

    # Raise if there are errors
    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(error_msg)
        raise ConfigError(error_msg)

    logger.info(f"Configuration validated: {len(validated)} variables loaded")
    Config._validated = True

    return validated


def get_env_var_docs() -> str:
    """Generate documentation for all environment variables."""
    lines = ["# Environment Variables\n"]

    # Group by category
    categories = {
        "Application": ["APP_ENV", "DEBUG", "PORT", "HOST"],
        "Database": ["DATA_DIR", "DB_PATH"],
        "Security": [
            "SECRET_KEY",
            "ARCHITECT_USER",
            "ARCHITECT_PASSWORD",
            "SESSION_COOKIE_SECURE",
            "SESSION_TIMEOUT",
        ],
        "Network": ["TAILSCALE_IP", "ARCHITECT_URL", "VAULT_URL"],
        "Workers": ["WORKER_ID", "NODE_ID", "AGENT_NAME"],
        "Request Logging": [
            "REQUEST_LOG_ENABLED",
            "REQUEST_LOG_LEVEL",
            "REQUEST_LOG_FILE",
            "REQUEST_LOG_MAX_BODY",
            "REQUEST_LOG_EXCLUDE",
        ],
        "Browser": ["CHROME_DEBUG_PORT", "CHROME_HEADLESS", "CHROME_PROFILE"],
        "LLM": [
            "LLM_PROVIDER",
            "ANTHROPIC_API_KEY",
            "CLAUDE_MODEL",
            "OPENAI_API_KEY",
            "OLLAMA_HOST",
            "OLLAMA_MODEL",
            "LLM_FAILOVER_ENABLED",
            "LLM_DEFAULT_PROVIDER",
            "LLM_PROVIDERS_CONFIG",
            "LLM_FAILOVER_POLICY_CONFIG",
        ],
        "Other": ["ERROR_DAEMON_SESSION", "DEPLOY_APPROVED"],
    }

    for category, var_names in categories.items():
        lines.append(f"\n## {category}\n")
        lines.append("| Variable | Type | Default | Description |")
        lines.append("|----------|------|---------|-------------|")

        for name in var_names:
            if name in ENV_VARS:
                ev = ENV_VARS[name]
                default = "***" if ev.sensitive else (ev.default or "-")
                required = " (required)" if ev.required else ""
                lines.append(
                    f"| `{name}` | {ev.var_type} | {default} | {ev.description}{required} |"
                )

    return "\n".join(lines)


# Convenience functions for common patterns
def is_production() -> bool:
    """Check if running in production environment."""
    return Config.APP_ENV == "prod"


def is_development() -> bool:
    """Check if running in development environment."""
    return Config.APP_ENV in ("dev", "development")


def is_testing() -> bool:
    """Check if running in test environment."""
    return Config.APP_ENV in ("test", "testing")


def require_production_secret() -> None:
    """Raise error if using default secret key in production."""
    if is_production():
        default_secret = "architect-dashboard-secret-key-change-in-production"
        if Config.SECRET_KEY == default_secret:
            raise ConfigError(
                "Using default SECRET_KEY in production is not allowed. "
                "Set the SECRET_KEY environment variable."
            )
