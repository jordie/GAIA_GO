"""
Process Supervisor Module

Advanced process supervision system for managing critical services.

Usage:
    # Start supervisor daemon
    python3 -m supervisor.process_supervisor --daemon

    # Use CLI
    python3 -m supervisor.supervisorctl status

    # Import in Python
    from supervisor.process_supervisor import ProcessSupervisor
    from supervisor.health_checks import HealthChecker
    from supervisor.supervisor_integration import SupervisorIntegration

    # Initialize supervisor
    supervisor = ProcessSupervisor()
    supervisor.start()
"""

__version__ = "1.0.0"
__author__ = "Architect Dashboard"

from .health_checks import HealthChecker, HealthStatus
from .process_supervisor import ProcessSupervisor, ServiceState
from .supervisor_integration import SupervisorIntegration

__all__ = [
    "ProcessSupervisor",
    "ServiceState",
    "HealthChecker",
    "HealthStatus",
    "SupervisorIntegration",
]
