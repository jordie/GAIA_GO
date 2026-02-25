"""
Service Registry for distributed system.

Maintains a catalog of services, their endpoints, health status,
and provides service discovery for load balancing.
"""

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service health status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    STOPPING = "stopping"
    UNKNOWN = "unknown"


@dataclass
class ServiceInstance:
    """Represents a single service instance."""

    id: str
    service_name: str
    host: str
    port: int
    node_id: str
    status: ServiceStatus = ServiceStatus.UNKNOWN
    health_endpoint: str = "/health"
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    last_health_check: float = 0
    consecutive_failures: int = 0
    weight: int = 100  # Load balancing weight

    @property
    def endpoint(self) -> str:
        """Get the full service endpoint URL."""
        return f"http://{self.host}:{self.port}"

    @property
    def health_url(self) -> str:
        """Get the health check URL."""
        return f"{self.endpoint}{self.health_endpoint}"

    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self.status == ServiceStatus.HEALTHY


@dataclass
class ServiceDefinition:
    """Definition of a service type."""

    name: str
    type: str = "web"  # web, ai, database, etc.
    default_port: int = 8000
    health_endpoint: str = "/health"
    replicas: int = 1
    failover: str = "automatic"
    shared: bool = False
    max_concurrent: int = 0  # 0 = unlimited
    start_command: str = ""
    stop_command: str = ""
    dependencies: List[str] = field(default_factory=list)


class ServiceRegistry:
    """
    Central registry for all services in the distributed system.

    Provides service discovery, health tracking, and failover management.
    """

    def __init__(self, health_check_interval: int = 30, failure_threshold: int = 3):
        """
        Initialize the service registry.

        Args:
            health_check_interval: Seconds between health checks
            failure_threshold: Consecutive failures before marking unhealthy
        """
        self._instances: Dict[str, ServiceInstance] = {}
        self._definitions: Dict[str, ServiceDefinition] = {}
        self._by_service: Dict[str, List[str]] = defaultdict(list)
        self._by_node: Dict[str, List[str]] = defaultdict(list)
        self._lock = threading.RLock()

        self.health_check_interval = health_check_interval
        self.failure_threshold = failure_threshold

        self._health_checker_running = False
        self._health_checker_thread: Optional[threading.Thread] = None

    def register_definition(self, definition: ServiceDefinition) -> None:
        """Register a service definition."""
        with self._lock:
            self._definitions[definition.name] = definition
            logger.info(f"Registered service definition: {definition.name}")

    def get_definition(self, service_name: str) -> Optional[ServiceDefinition]:
        """Get a service definition by name."""
        return self._definitions.get(service_name)

    def register(self, instance: ServiceInstance) -> str:
        """
        Register a service instance.

        Args:
            instance: The service instance to register

        Returns:
            Instance ID
        """
        with self._lock:
            self._instances[instance.id] = instance
            self._by_service[instance.service_name].append(instance.id)
            self._by_node[instance.node_id].append(instance.id)

            logger.info(
                f"Registered service instance: {instance.id} "
                f"({instance.service_name} at {instance.endpoint})"
            )

            return instance.id

    def deregister(self, instance_id: str) -> bool:
        """
        Remove a service instance from the registry.

        Args:
            instance_id: ID of the instance to remove

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            instance = self._instances.pop(instance_id, None)
            if instance:
                if instance_id in self._by_service[instance.service_name]:
                    self._by_service[instance.service_name].remove(instance_id)
                if instance_id in self._by_node[instance.node_id]:
                    self._by_node[instance.node_id].remove(instance_id)
                logger.info(f"Deregistered service instance: {instance_id}")
                return True
            return False

    def get_instance(self, instance_id: str) -> Optional[ServiceInstance]:
        """Get a service instance by ID."""
        return self._instances.get(instance_id)

    def get_instances(self, service_name: str, healthy_only: bool = True) -> List[ServiceInstance]:
        """
        Get all instances of a service.

        Args:
            service_name: Name of the service
            healthy_only: Only return healthy instances

        Returns:
            List of service instances
        """
        with self._lock:
            instance_ids = self._by_service.get(service_name, [])
            instances = [self._instances[id] for id in instance_ids if id in self._instances]

            if healthy_only:
                instances = [i for i in instances if i.is_healthy()]

            return instances

    def get_instances_on_node(self, node_id: str) -> List[ServiceInstance]:
        """Get all service instances running on a node."""
        with self._lock:
            instance_ids = self._by_node.get(node_id, [])
            return [self._instances[id] for id in instance_ids if id in self._instances]

    def get_endpoint(self, service_name: str) -> Optional[str]:
        """
        Get a healthy endpoint for a service (simple round-robin).

        Args:
            service_name: Name of the service

        Returns:
            Endpoint URL or None if no healthy instances
        """
        instances = self.get_instances(service_name, healthy_only=True)
        if not instances:
            return None

        # Simple selection - first healthy instance
        # LoadBalancer provides more sophisticated selection
        return instances[0].endpoint

    def get_all_endpoints(self, service_name: str) -> List[str]:
        """Get all healthy endpoints for a service."""
        instances = self.get_instances(service_name, healthy_only=True)
        return [i.endpoint for i in instances]

    def update_health(self, instance_id: str, healthy: bool) -> None:
        """
        Update health status of a service instance.

        Args:
            instance_id: Instance to update
            healthy: Whether the instance is healthy
        """
        with self._lock:
            instance = self._instances.get(instance_id)
            if not instance:
                return

            instance.last_health_check = time.time()

            if healthy:
                instance.status = ServiceStatus.HEALTHY
                instance.consecutive_failures = 0
            else:
                instance.consecutive_failures += 1
                if instance.consecutive_failures >= self.failure_threshold:
                    if instance.status != ServiceStatus.UNHEALTHY:
                        logger.warning(
                            f"Service instance {instance_id} marked unhealthy "
                            f"after {instance.consecutive_failures} failures"
                        )
                    instance.status = ServiceStatus.UNHEALTHY

    def check_health(self, instance: ServiceInstance) -> bool:
        """
        Perform health check on a service instance.

        Args:
            instance: Instance to check

        Returns:
            True if healthy
        """
        import urllib.error
        import urllib.request

        try:
            req = urllib.request.Request(instance.health_url, method="GET")
            req.add_header("Connection", "close")

            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except (urllib.error.URLError, urllib.error.HTTPError, Exception) as e:
            logger.debug(f"Health check failed for {instance.id}: {e}")
            return False

    def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._health_checker_running:
            try:
                with self._lock:
                    instances = list(self._instances.values())

                for instance in instances:
                    if not self._health_checker_running:
                        break

                    healthy = self.check_health(instance)
                    self.update_health(instance.id, healthy)

            except Exception as e:
                logger.error(f"Health check error: {e}")

            # Sleep in small increments for responsive shutdown
            for _ in range(self.health_check_interval):
                if not self._health_checker_running:
                    break
                time.sleep(1)

    def start_health_checker(self) -> None:
        """Start the background health checker."""
        if self._health_checker_running:
            return

        self._health_checker_running = True
        self._health_checker_thread = threading.Thread(
            target=self._health_check_loop, daemon=True, name="ServiceRegistry-HealthChecker"
        )
        self._health_checker_thread.start()
        logger.info("Started health checker thread")

    def stop_health_checker(self) -> None:
        """Stop the background health checker."""
        self._health_checker_running = False
        if self._health_checker_thread:
            self._health_checker_thread.join(timeout=5)
            self._health_checker_thread = None
            logger.info("Stopped health checker thread")

    def get_service_status(self) -> Dict[str, Any]:
        """Get status summary of all services."""
        with self._lock:
            services = {}

            for service_name in self._by_service:
                instances = self.get_instances(service_name, healthy_only=False)
                healthy_count = sum(1 for i in instances if i.is_healthy())

                services[service_name] = {
                    "total_instances": len(instances),
                    "healthy_instances": healthy_count,
                    "unhealthy_instances": len(instances) - healthy_count,
                    "endpoints": [i.endpoint for i in instances if i.is_healthy()],
                    "instances": [
                        {
                            "id": i.id,
                            "endpoint": i.endpoint,
                            "status": i.status.value,
                            "node_id": i.node_id,
                            "last_check": i.last_health_check,
                        }
                        for i in instances
                    ],
                }

            return services

    def to_dict(self) -> Dict[str, Any]:
        """Export registry state as dictionary."""
        with self._lock:
            return {
                "instances": {
                    id: {
                        "id": i.id,
                        "service_name": i.service_name,
                        "host": i.host,
                        "port": i.port,
                        "node_id": i.node_id,
                        "status": i.status.value,
                        "endpoint": i.endpoint,
                        "health_endpoint": i.health_endpoint,
                        "registered_at": i.registered_at,
                        "last_health_check": i.last_health_check,
                        "weight": i.weight,
                    }
                    for id, i in self._instances.items()
                },
                "definitions": {
                    name: {
                        "name": d.name,
                        "type": d.type,
                        "default_port": d.default_port,
                        "health_endpoint": d.health_endpoint,
                        "replicas": d.replicas,
                        "failover": d.failover,
                        "shared": d.shared,
                        "max_concurrent": d.max_concurrent,
                    }
                    for name, d in self._definitions.items()
                },
            }


# Global registry instance
_registry: Optional[ServiceRegistry] = None


def get_registry() -> ServiceRegistry:
    """Get or create the global service registry."""
    global _registry
    if _registry is None:
        _registry = ServiceRegistry()
    return _registry
