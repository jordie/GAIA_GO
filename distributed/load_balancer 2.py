"""
Load Balancer for distributed system.

Distributes requests across service instances using various
algorithms (round-robin, weighted, least-connections).
"""

import logging
import random
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .service_registry import ServiceInstance, ServiceRegistry, get_registry

logger = logging.getLogger(__name__)


class LoadBalancingStrategy(Enum):
    """Load balancing algorithms."""

    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    IP_HASH = "ip_hash"


@dataclass
class ConnectionStats:
    """Connection statistics for an instance."""

    instance_id: str
    active_connections: int = 0
    total_requests: int = 0
    total_errors: int = 0
    avg_response_time_ms: float = 0
    last_request_time: float = 0


class LoadBalancer:
    """
    Distributes requests across service instances.

    Supports multiple load balancing strategies and tracks
    connection statistics for intelligent routing.
    """

    def __init__(
        self,
        registry: ServiceRegistry = None,
        default_strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
    ):
        """
        Initialize the load balancer.

        Args:
            registry: Service registry to use
            default_strategy: Default load balancing strategy
        """
        self.registry = registry or get_registry()
        self.default_strategy = default_strategy

        self._service_strategies: Dict[str, LoadBalancingStrategy] = {}
        self._round_robin_index: Dict[str, int] = defaultdict(int)
        self._connection_stats: Dict[str, ConnectionStats] = {}
        self._lock = threading.RLock()

    def set_strategy(self, service_name: str, strategy: LoadBalancingStrategy) -> None:
        """Set load balancing strategy for a service."""
        with self._lock:
            self._service_strategies[service_name] = strategy
            logger.info(f"Set {strategy.value} strategy for {service_name}")

    def get_strategy(self, service_name: str) -> LoadBalancingStrategy:
        """Get load balancing strategy for a service."""
        return self._service_strategies.get(service_name, self.default_strategy)

    def _get_stats(self, instance_id: str) -> ConnectionStats:
        """Get or create connection stats for an instance."""
        if instance_id not in self._connection_stats:
            self._connection_stats[instance_id] = ConnectionStats(instance_id=instance_id)
        return self._connection_stats[instance_id]

    def get_instance(self, service_name: str, client_ip: str = None) -> Optional[ServiceInstance]:
        """
        Select a service instance using the configured strategy.

        Args:
            service_name: Name of the service
            client_ip: Client IP for IP hash strategy

        Returns:
            Selected instance or None
        """
        instances = self.registry.get_instances(service_name, healthy_only=True)
        if not instances:
            logger.warning(f"No healthy instances for {service_name}")
            return None

        strategy = self.get_strategy(service_name)

        with self._lock:
            if strategy == LoadBalancingStrategy.ROUND_ROBIN:
                return self._select_round_robin(service_name, instances)
            elif strategy == LoadBalancingStrategy.WEIGHTED:
                return self._select_weighted(instances)
            elif strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
                return self._select_least_connections(instances)
            elif strategy == LoadBalancingStrategy.RANDOM:
                return random.choice(instances)
            elif strategy == LoadBalancingStrategy.IP_HASH:
                return self._select_ip_hash(instances, client_ip)
            else:
                return instances[0]

    def _select_round_robin(
        self, service_name: str, instances: List[ServiceInstance]
    ) -> ServiceInstance:
        """Select using round-robin."""
        index = self._round_robin_index[service_name]
        instance = instances[index % len(instances)]
        self._round_robin_index[service_name] = (index + 1) % len(instances)
        return instance

    def _select_weighted(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Select using weighted random selection."""
        total_weight = sum(i.weight for i in instances)
        if total_weight == 0:
            return random.choice(instances)

        r = random.uniform(0, total_weight)
        cumulative = 0

        for instance in instances:
            cumulative += instance.weight
            if r <= cumulative:
                return instance

        return instances[-1]

    def _select_least_connections(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Select instance with least active connections."""
        min_connections = float("inf")
        selected = instances[0]

        for instance in instances:
            stats = self._get_stats(instance.id)
            if stats.active_connections < min_connections:
                min_connections = stats.active_connections
                selected = instance

        return selected

    def _select_ip_hash(
        self, instances: List[ServiceInstance], client_ip: str = None
    ) -> ServiceInstance:
        """Select based on client IP hash for session affinity."""
        if not client_ip:
            return random.choice(instances)

        hash_value = hash(client_ip)
        index = hash_value % len(instances)
        return instances[index]

    def record_request_start(self, instance_id: str) -> None:
        """Record the start of a request to an instance."""
        with self._lock:
            stats = self._get_stats(instance_id)
            stats.active_connections += 1
            stats.total_requests += 1
            stats.last_request_time = time.time()

    def record_request_end(
        self, instance_id: str, response_time_ms: float, success: bool = True
    ) -> None:
        """
        Record the end of a request.

        Args:
            instance_id: Instance that handled the request
            response_time_ms: Response time in milliseconds
            success: Whether the request succeeded
        """
        with self._lock:
            stats = self._get_stats(instance_id)
            stats.active_connections = max(0, stats.active_connections - 1)

            if not success:
                stats.total_errors += 1

            # Update average response time (exponential moving average)
            alpha = 0.1  # Smoothing factor
            if stats.avg_response_time_ms == 0:
                stats.avg_response_time_ms = response_time_ms
            else:
                stats.avg_response_time_ms = (
                    alpha * response_time_ms + (1 - alpha) * stats.avg_response_time_ms
                )

    def get_endpoint(self, service_name: str, client_ip: str = None) -> Optional[str]:
        """
        Get a load-balanced endpoint for a service.

        Args:
            service_name: Name of the service
            client_ip: Client IP for IP hash strategy

        Returns:
            Endpoint URL or None
        """
        instance = self.get_instance(service_name, client_ip)
        return instance.endpoint if instance else None

    def get_all_endpoints(self, service_name: str) -> List[str]:
        """Get all healthy endpoints for a service."""
        instances = self.registry.get_instances(service_name, healthy_only=True)
        return [i.endpoint for i in instances]

    def get_stats(self, service_name: str = None) -> Dict[str, Any]:
        """
        Get load balancer statistics.

        Args:
            service_name: Optional filter by service

        Returns:
            Statistics dictionary
        """
        with self._lock:
            if service_name:
                instances = self.registry.get_instances(service_name, healthy_only=False)
                instance_ids = {i.id for i in instances}
                stats = {id: s for id, s in self._connection_stats.items() if id in instance_ids}
            else:
                stats = dict(self._connection_stats)

            return {
                "instances": {
                    id: {
                        "active_connections": s.active_connections,
                        "total_requests": s.total_requests,
                        "total_errors": s.total_errors,
                        "error_rate": s.total_errors / max(s.total_requests, 1),
                        "avg_response_time_ms": round(s.avg_response_time_ms, 2),
                        "last_request": s.last_request_time,
                    }
                    for id, s in stats.items()
                },
                "total_requests": sum(s.total_requests for s in stats.values()),
                "total_errors": sum(s.total_errors for s in stats.values()),
                "total_active": sum(s.active_connections for s in stats.values()),
            }

    def reset_stats(self, instance_id: str = None) -> None:
        """Reset statistics for one or all instances."""
        with self._lock:
            if instance_id:
                if instance_id in self._connection_stats:
                    del self._connection_stats[instance_id]
            else:
                self._connection_stats.clear()
                self._round_robin_index.clear()


class RequestProxy:
    """
    Proxy for making load-balanced requests to services.

    Handles automatic instance selection, retries, and circuit breaking.
    """

    def __init__(self, load_balancer: LoadBalancer, max_retries: int = 2, timeout: int = 30):
        """
        Initialize the request proxy.

        Args:
            load_balancer: LoadBalancer instance
            max_retries: Maximum retry attempts
            timeout: Request timeout in seconds
        """
        self.lb = load_balancer
        self.max_retries = max_retries
        self.timeout = timeout

    def request(
        self,
        service_name: str,
        path: str,
        method: str = "GET",
        data: Any = None,
        headers: Dict[str, str] = None,
        client_ip: str = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Make a load-balanced request to a service.

        Args:
            service_name: Target service name
            path: Request path
            method: HTTP method
            data: Request body data
            headers: Additional headers
            client_ip: Client IP for session affinity

        Returns:
            Response data or None on failure
        """
        import json as json_lib
        import urllib.error
        import urllib.request

        last_error = None

        for attempt in range(self.max_retries + 1):
            instance = self.lb.get_instance(service_name, client_ip)
            if not instance:
                logger.error(f"No instance available for {service_name}")
                return None

            url = f"{instance.endpoint}{path}"
            start_time = time.time()

            try:
                self.lb.record_request_start(instance.id)

                req_data = None
                if data:
                    req_data = json_lib.dumps(data).encode("utf-8")

                req = urllib.request.Request(url, data=req_data, method=method)
                req.add_header("Content-Type", "application/json")
                if headers:
                    for key, value in headers.items():
                        req.add_header(key, value)

                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    response_time = (time.time() - start_time) * 1000
                    self.lb.record_request_end(instance.id, response_time, success=True)

                    content = response.read().decode("utf-8")
                    return json_lib.loads(content) if content else {}

            except urllib.error.HTTPError as e:
                response_time = (time.time() - start_time) * 1000
                self.lb.record_request_end(instance.id, response_time, success=False)

                last_error = e
                logger.warning(f"Request to {url} failed (HTTP {e.code}): {e.reason}")

                # Don't retry on client errors (4xx)
                if 400 <= e.code < 500:
                    break

            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                self.lb.record_request_end(instance.id, response_time, success=False)

                last_error = e
                logger.warning(f"Request to {url} failed: {e}")

        if last_error:
            logger.error(f"All retries failed for {service_name}{path}: {last_error}")

        return None


# Global load balancer instance
_load_balancer: Optional[LoadBalancer] = None


def get_load_balancer() -> LoadBalancer:
    """Get or create the global load balancer."""
    global _load_balancer
    if _load_balancer is None:
        _load_balancer = LoadBalancer()
    return _load_balancer
