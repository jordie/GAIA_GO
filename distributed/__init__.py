"""
Distributed System Module for Educational Apps Platform.

This module provides distributed deployment, resource management,
and high availability features for running the platform across
multiple servers.

Components:
- ResourceManager: Central coordinator for cluster resources
- ServiceRegistry: Service discovery and health tracking
- LoadBalancer: Request distribution across nodes
- SSHClient: Secure remote command execution

Usage:
    # Initialize cluster
    python3 -m distributed.cli init

    # Add a node
    python3 -m distributed.cli node add primary 192.168.1.231

    # Deploy to all nodes
    python3 -m distributed.cli deploy --all

    # Check cluster status
    python3 -m distributed.cli status
"""

__version__ = "1.0.0"

from .cluster_coordinator import (
    ClusterConfig,
    ClusterCoordinator,
    ClusterState,
    NodeInfo,
    NodeRole,
    get_coordinator,
    init_coordinator,
)
from .load_balancer import LoadBalancer, LoadBalancingStrategy, get_load_balancer
from .log_maintenance import (
    LogAction,
    LogFileInfo,
    LogMaintenance,
    MaintenancePolicy,
    get_project_logs,
    trim_large_logs,
)
from .resource_manager import NodeConfig, NodeRole, NodeStatus, ResourceManager, get_manager
from .service_registry import (
    ServiceDefinition,
    ServiceInstance,
    ServiceRegistry,
    ServiceStatus,
    get_registry,
)
from .ssh_client import SSHClient, SSHConfig, SSHConnectionPool, get_client

__all__ = [
    # Resource Manager
    "ResourceManager",
    "NodeConfig",
    "NodeRole",
    "NodeStatus",
    "get_manager",
    # Service Registry
    "ServiceRegistry",
    "ServiceInstance",
    "ServiceDefinition",
    "ServiceStatus",
    "get_registry",
    # Load Balancer
    "LoadBalancer",
    "LoadBalancingStrategy",
    "get_load_balancer",
    # SSH Client
    "SSHClient",
    "SSHConfig",
    "SSHConnectionPool",
    "get_client",
    # Log Maintenance
    "LogMaintenance",
    "LogFileInfo",
    "MaintenancePolicy",
    "LogAction",
    "get_project_logs",
    "trim_large_logs",
    # Cluster Coordinator
    "ClusterCoordinator",
    "ClusterConfig",
    "ClusterState",
    "NodeRole",
    "NodeInfo",
    "get_coordinator",
    "init_coordinator",
]
