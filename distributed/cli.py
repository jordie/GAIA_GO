#!/usr/bin/env python3
"""
CLI for managing the distributed cluster.

Usage:
    python3 -m distributed.cli <command> [options]

Commands:
    init                Initialize the cluster
    status              Show cluster status
    node add            Add a node to the cluster
    node remove         Remove a node from the cluster
    node list           List all nodes
    service list        List all services
    deploy              Deploy to nodes
    resource allocate   Allocate a shared resource
    resource release    Release a resource
    failover            Trigger manual failover
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from distributed.load_balancer import LoadBalancer, get_load_balancer
from distributed.resource_manager import (
    NodeConfig,
    NodeRole,
    NodeStatus,
    ResourceManager,
    get_manager,
)
from distributed.service_registry import (
    ServiceDefinition,
    ServiceInstance,
    ServiceRegistry,
    get_registry,
)
from distributed.ssh_client import SSHClient, SSHConfig, get_client


class Colors:
    """Terminal colors."""

    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


def color(text: str, c: str) -> str:
    """Apply color to text."""
    return f"{c}{text}{Colors.END}"


def status_color(status: str) -> str:
    """Get colored status string."""
    status_lower = status.lower()
    if status_lower in ("online", "healthy", "running"):
        return color(status, Colors.GREEN)
    elif status_lower in ("offline", "unhealthy", "stopped"):
        return color(status, Colors.RED)
    elif status_lower in ("degraded", "starting", "stopping"):
        return color(status, Colors.YELLOW)
    return status


def print_header(text: str) -> None:
    """Print a header."""
    print(f"\n{color(text, Colors.BOLD + Colors.CYAN)}")
    print("=" * len(text))


def print_success(text: str) -> None:
    """Print success message."""
    print(color(f"[OK] {text}", Colors.GREEN))


def print_error(text: str) -> None:
    """Print error message."""
    print(color(f"[ERROR] {text}", Colors.RED))


def print_warning(text: str) -> None:
    """Print warning message."""
    print(color(f"[WARN] {text}", Colors.YELLOW))


def print_info(text: str) -> None:
    """Print info message."""
    print(color(f"[INFO] {text}", Colors.BLUE))


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize the cluster."""
    print_header("Initializing Cluster")

    manager = get_manager()

    # Load configuration if exists
    config_file = Path(__file__).parent / "config" / "nodes.yaml"
    if config_file.exists():
        print_info(f"Loading configuration from {config_file}")
        # TODO: Implement YAML loading
    else:
        print_info("No configuration file found. Creating default cluster.")

    print_success(f"Cluster '{manager.cluster_name}' initialized")
    print_info(f"Database: {manager._db_path}")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show cluster status."""
    manager = get_manager()
    manager.load_from_database()

    status = manager.get_cluster_status()

    print_header(f"Cluster: {status['cluster_name']}")

    # Summary
    print(f"\nNodes: {status['online_nodes']}/{status['total_nodes']} online")
    if status["overloaded_nodes"] > 0:
        print_warning(f"Overloaded nodes: {status['overloaded_nodes']}")

    # Node details
    if status["nodes"]:
        print_header("Nodes")
        for node in status["nodes"]:
            status_str = status_color(node["status"])
            overloaded = color(" [OVERLOADED]", Colors.RED) if node["is_overloaded"] else ""

            print(f"\n  {color(node['id'], Colors.BOLD)} ({node['hostname']})")
            print(f"    Status: {status_str}{overloaded}")
            print(f"    Role: {node['role']}")
            print(f"    IP: {node['ip_address']}")
            print(f"    CPU: {node['cpu_usage']:.1f}%  Memory: {node['memory_usage']:.1f}%")
            print(f"    Services: {', '.join(node['services']) or 'none'}")
            if node["active_services"]:
                print(f"    Active: {', '.join(node['active_services'])}")
    else:
        print_info("No nodes registered. Use 'node add' to add nodes.")

    # Allocations
    if status["active_allocations"] > 0:
        print(f"\nActive resource allocations: {status['active_allocations']}")

    return 0


def cmd_node_add(args: argparse.Namespace) -> int:
    """Add a node to the cluster."""
    manager = get_manager()

    # Parse role
    try:
        role = NodeRole(args.role)
    except ValueError:
        print_error(f"Invalid role: {args.role}. Must be: primary, secondary, worker")
        return 1

    # Generate node ID
    node_id = args.name or f"{args.role}-{args.host.replace('.', '-')}"

    config = NodeConfig(
        id=node_id,
        hostname=args.host,
        ip_address=args.host,
        ssh_port=args.port,
        ssh_user=args.user,
        ssh_key_file=args.key,
        role=role,
        services=args.services.split(",") if args.services else [],
    )

    manager.register_node(config)
    print_success(f"Added node: {node_id}")

    # Test connection if requested
    if args.test:
        print_info("Testing SSH connection...")
        client = get_client(
            host=config.ip_address,
            user=config.ssh_user,
            port=config.ssh_port,
            key_file=config.ssh_key_file,
        )
        if client.test_connection():
            print_success("SSH connection successful")
        else:
            print_warning("SSH connection failed")

    return 0


def cmd_node_remove(args: argparse.Namespace) -> int:
    """Remove a node from the cluster."""
    manager = get_manager()
    manager.load_from_database()

    if manager.deregister_node(args.node_id):
        print_success(f"Removed node: {args.node_id}")
        return 0
    else:
        print_error(f"Node not found: {args.node_id}")
        return 1


def cmd_node_list(args: argparse.Namespace) -> int:
    """List all nodes."""
    manager = get_manager()
    manager.load_from_database()

    nodes = manager.get_all_nodes()

    if not nodes:
        print_info("No nodes registered")
        return 0

    print_header("Cluster Nodes")

    for config in nodes:
        state = manager.get_node_state(config.id)
        status_str = status_color(state.status.value if state else "unknown")

        print(f"\n  {color(config.id, Colors.BOLD)}")
        print(f"    Host: {config.hostname} ({config.ip_address}:{config.ssh_port})")
        print(f"    Role: {config.role.value}")
        print(f"    Status: {status_str}")
        print(f"    User: {config.ssh_user}")
        print(f"    Services: {', '.join(config.services) or 'none'}")

        if state and state.cpu_usage > 0:
            print(f"    Resources: CPU {state.cpu_usage:.1f}%, Memory {state.memory_usage:.1f}%")

    return 0


def cmd_service_list(args: argparse.Namespace) -> int:
    """List all services."""
    registry = get_registry()
    status = registry.get_service_status()

    if not status:
        print_info("No services registered")
        return 0

    print_header("Services")

    for service_name, info in status.items():
        healthy = info["healthy_instances"]
        total = info["total_instances"]

        health_color = (
            Colors.GREEN if healthy == total else Colors.YELLOW if healthy > 0 else Colors.RED
        )
        print(f"\n  {color(service_name, Colors.BOLD)}")
        print(f"    Instances: {color(f'{healthy}/{total}', health_color)} healthy")

        for inst in info["instances"]:
            inst_status = status_color(inst["status"])
            print(f"      - {inst['endpoint']} [{inst_status}] on {inst['node_id']}")

    return 0


def cmd_deploy(args: argparse.Namespace) -> int:
    """Deploy to nodes."""
    manager = get_manager()
    manager.load_from_database()

    if args.all:
        nodes = manager.get_all_nodes()
    elif args.node:
        node = manager.get_node(args.node)
        if not node:
            print_error(f"Node not found: {args.node}")
            return 1
        nodes = [node]
    else:
        print_error("Specify --all or --node <node_id>")
        return 1

    print_header(f"Deploying to {len(nodes)} node(s)")

    success_count = 0
    for config in nodes:
        print_info(f"Deploying to {config.hostname}...")

        client = get_client(
            host=config.ip_address,
            user=config.ssh_user,
            port=config.ssh_port,
            key_file=config.ssh_key_file,
        )

        if not client.test_connection():
            print_error(f"Cannot connect to {config.hostname}")
            continue

        # Get system info
        info = client.get_system_info()
        print_info(
            f"  {info.get('hostname', 'unknown')}: {info.get('cpu_cores', '?')} cores, "
            f"{info.get('memory_mb', '?')}MB RAM"
        )

        # Update state with metrics
        manager.heartbeat(
            config.id,
            {
                "cpu_cores": info.get("cpu_cores", 0),
                "memory_mb": info.get("memory_mb", 0),
                "disk_free_mb": info.get("disk_free_mb", 0),
                "cpu_usage": info.get("cpu_usage", 0),
                "memory_usage": info.get("memory_usage", 0),
            },
        )

        # Deploy services (placeholder - would copy files and start services)
        for service in config.services:
            print_info(f"  Deploying {service}...")
            # TODO: Implement actual deployment

        success_count += 1
        print_success(f"Deployed to {config.hostname}")

    print(f"\nDeployed to {success_count}/{len(nodes)} nodes")
    return 0 if success_count == len(nodes) else 1


def cmd_resource_allocate(args: argparse.Namespace) -> int:
    """Allocate a shared resource."""
    manager = get_manager()
    manager.load_from_database()

    allocation = manager.allocate_resource(
        resource_type=args.resource,
        requester=args.requester or os.environ.get("USER", "unknown"),
        preferred_node=args.node,
        priority=args.priority,
    )

    if allocation:
        print_success(f"Allocated {args.resource}")
        print_info(f"  Allocation ID: {allocation.id}")
        print_info(f"  Node: {allocation.node_id}")
        return 0
    else:
        print_error(f"Failed to allocate {args.resource}")
        return 1


def cmd_resource_release(args: argparse.Namespace) -> int:
    """Release a resource allocation."""
    manager = get_manager()

    if manager.release_resource(args.allocation_id):
        print_success(f"Released allocation: {args.allocation_id}")
        return 0
    else:
        print_error(f"Allocation not found: {args.allocation_id}")
        return 1


def cmd_failover(args: argparse.Namespace) -> int:
    """Trigger manual failover."""
    manager = get_manager()
    manager.load_from_database()

    target = manager.trigger_failover(args.from_node, args.to_node)

    if target:
        print_success(f"Failover triggered: {args.from_node} -> {target}")
        return 0
    else:
        print_error("Failover failed - no suitable target node")
        return 1


def cmd_test_ssh(args: argparse.Namespace) -> int:
    """Test SSH connection to a host."""
    print_info(f"Testing SSH connection to {args.host}...")

    client = get_client(host=args.host, user=args.user, port=args.port, key_file=args.key)

    if client.test_connection():
        print_success("SSH connection successful")

        info = client.get_system_info()
        print_header("System Information")
        for key, value in info.items():
            print(f"  {key}: {value}")

        return 0
    else:
        print_error("SSH connection failed")
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Distributed cluster management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init
    subparsers.add_parser("init", help="Initialize the cluster")

    # status
    subparsers.add_parser("status", help="Show cluster status")

    # node
    node_parser = subparsers.add_parser("node", help="Node management")
    node_sub = node_parser.add_subparsers(dest="node_command")

    # node add
    node_add = node_sub.add_parser("add", help="Add a node")
    node_add.add_argument("role", choices=["primary", "secondary", "worker"], help="Node role")
    node_add.add_argument("host", help="Host address")
    node_add.add_argument("--name", help="Node name/ID")
    node_add.add_argument("--port", type=int, default=22, help="SSH port")
    node_add.add_argument("--user", help="SSH username")
    node_add.add_argument("--key", help="SSH key file")
    node_add.add_argument("--services", help="Comma-separated services")
    node_add.add_argument("--test", action="store_true", help="Test connection")

    # node remove
    node_remove = node_sub.add_parser("remove", help="Remove a node")
    node_remove.add_argument("node_id", help="Node ID to remove")

    # node list
    node_sub.add_parser("list", help="List all nodes")

    # service
    service_parser = subparsers.add_parser("service", help="Service management")
    service_sub = service_parser.add_subparsers(dest="service_command")
    service_sub.add_parser("list", help="List all services")

    # deploy
    deploy_parser = subparsers.add_parser("deploy", help="Deploy to nodes")
    deploy_parser.add_argument("--all", action="store_true", help="Deploy to all nodes")
    deploy_parser.add_argument("--node", help="Deploy to specific node")

    # resource
    resource_parser = subparsers.add_parser("resource", help="Resource management")
    resource_sub = resource_parser.add_subparsers(dest="resource_command")

    # resource allocate
    res_alloc = resource_sub.add_parser("allocate", help="Allocate a resource")
    res_alloc.add_argument("resource", help="Resource type (e.g., ollama, gpu)")
    res_alloc.add_argument("--requester", help="Requester name")
    res_alloc.add_argument("--node", help="Preferred node")
    res_alloc.add_argument("--priority", default="normal", choices=["low", "normal", "high"])

    # resource release
    res_release = resource_sub.add_parser("release", help="Release a resource")
    res_release.add_argument("allocation_id", help="Allocation ID")

    # failover
    failover_parser = subparsers.add_parser("failover", help="Trigger failover")
    failover_parser.add_argument("--from", dest="from_node", required=True, help="Source node")
    failover_parser.add_argument("--to", dest="to_node", help="Target node")

    # test-ssh
    test_ssh_parser = subparsers.add_parser("test-ssh", help="Test SSH connection")
    test_ssh_parser.add_argument("host", help="Host to connect to")
    test_ssh_parser.add_argument("--port", type=int, default=22, help="SSH port")
    test_ssh_parser.add_argument("--user", help="SSH username")
    test_ssh_parser.add_argument("--key", help="SSH key file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Route to command handlers
    if args.command == "init":
        return cmd_init(args)
    elif args.command == "status":
        return cmd_status(args)
    elif args.command == "node":
        if args.node_command == "add":
            return cmd_node_add(args)
        elif args.node_command == "remove":
            return cmd_node_remove(args)
        elif args.node_command == "list":
            return cmd_node_list(args)
        else:
            node_parser.print_help()
            return 1
    elif args.command == "service":
        if args.service_command == "list":
            return cmd_service_list(args)
        else:
            service_parser.print_help()
            return 1
    elif args.command == "deploy":
        return cmd_deploy(args)
    elif args.command == "resource":
        if args.resource_command == "allocate":
            return cmd_resource_allocate(args)
        elif args.resource_command == "release":
            return cmd_resource_release(args)
        else:
            resource_parser.print_help()
            return 1
    elif args.command == "failover":
        return cmd_failover(args)
    elif args.command == "test-ssh":
        return cmd_test_ssh(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
