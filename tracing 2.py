#!/usr/bin/env python3
"""
Distributed Tracing with OpenTelemetry

Provides distributed tracing capabilities for the Architect Dashboard using
OpenTelemetry standards. Integrates with the existing correlation ID system.

Features:
- Automatic request tracing with spans
- Database operation instrumentation
- HTTP client request tracing
- Context propagation across services
- Multiple exporters (console, OTLP, Jaeger, Zipkin)
- Integration with correlation IDs
- Custom span attributes and events

Usage:
    from tracing import init_tracing, trace_span, get_tracer

    # Initialize in Flask app
    init_tracing(app)

    # Create custom spans
    with trace_span("process_data") as span:
        span.set_attribute("item_count", 100)
        process_data()

    # Use decorator
    @trace_function
    def my_function():
        pass

Environment Variables:
    OTEL_ENABLED=true                    # Enable/disable tracing
    OTEL_SERVICE_NAME=architect          # Service name for traces
    OTEL_EXPORTER=console                # Exporter type (console, otlp, jaeger, zipkin)
    OTEL_ENDPOINT=http://localhost:4317  # OTLP endpoint
    OTEL_SAMPLE_RATE=1.0                 # Sampling rate (0.0 to 1.0)
"""

import logging
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Check if OpenTelemetry is available
OTEL_AVAILABLE = False
try:
    from opentelemetry import trace
    from opentelemetry.propagate import extract, inject, set_global_textmap
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import Span, TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )
    from opentelemetry.sdk.trace.sampling import (
        ALWAYS_OFF,
        ALWAYS_ON,
        ParentBased,
        TraceIdRatioBased,
    )
    from opentelemetry.trace import SpanKind, Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    OTEL_AVAILABLE = True
    logger.info("OpenTelemetry SDK available")
except ImportError:
    logger.warning("OpenTelemetry SDK not installed. Using fallback tracing.")

# Try to import optional exporters
OTLP_AVAILABLE = False
JAEGER_AVAILABLE = False
ZIPKIN_AVAILABLE = False

if OTEL_AVAILABLE:
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        OTLP_AVAILABLE = True
    except ImportError:
        pass

    try:
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter

        JAEGER_AVAILABLE = True
    except ImportError:
        pass

    try:
        from opentelemetry.exporter.zipkin.json import ZipkinExporter

        ZIPKIN_AVAILABLE = True
    except ImportError:
        pass

# Configuration
TRACING_ENABLED = os.environ.get("OTEL_ENABLED", "true").lower() == "true"
SERVICE_NAME_VALUE = os.environ.get("OTEL_SERVICE_NAME", "architect-dashboard")
EXPORTER_TYPE = os.environ.get("OTEL_EXPORTER", "console")
OTLP_ENDPOINT = os.environ.get("OTEL_ENDPOINT", "http://localhost:4317")
SAMPLE_RATE = float(os.environ.get("OTEL_SAMPLE_RATE", "1.0"))

# Global tracer instance
_tracer: Optional[Any] = None
_provider: Optional[Any] = None
_initialized = False

# Fallback span storage for when OpenTelemetry is not available
_fallback_spans: Dict[str, Dict] = {}
_fallback_lock = threading.Lock()


class FallbackSpan:
    """
    Fallback span implementation when OpenTelemetry is not available.
    Provides a compatible interface for basic tracing.
    """

    def __init__(self, name: str, parent_id: Optional[str] = None):
        self.name = name
        self.span_id = f"{int(time.time() * 1000000)}-{id(self) % 10000:04d}"
        self.parent_id = parent_id
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.attributes: Dict[str, Any] = {}
        self.events: List[Dict] = []
        self.status = "OK"
        self.status_description = ""

    def set_attribute(self, key: str, value: Any) -> "FallbackSpan":
        """Set a span attribute."""
        self.attributes[key] = value
        return self

    def set_attributes(self, attributes: Dict[str, Any]) -> "FallbackSpan":
        """Set multiple span attributes."""
        self.attributes.update(attributes)
        return self

    def add_event(self, name: str, attributes: Dict[str, Any] = None) -> "FallbackSpan":
        """Add an event to the span."""
        self.events.append({"name": name, "timestamp": time.time(), "attributes": attributes or {}})
        return self

    def set_status(self, status: str, description: str = "") -> "FallbackSpan":
        """Set the span status."""
        self.status = status
        self.status_description = description
        return self

    def record_exception(self, exception: Exception) -> "FallbackSpan":
        """Record an exception in the span."""
        self.add_event(
            "exception",
            {"exception.type": type(exception).__name__, "exception.message": str(exception)},
        )
        self.set_status("ERROR", str(exception))
        return self

    def end(self) -> None:
        """End the span."""
        self.end_time = time.time()
        duration_ms = (self.end_time - self.start_time) * 1000

        # Log span completion
        logger.debug(
            f"Span completed: {self.name} " f"(duration={duration_ms:.2f}ms, status={self.status})"
        )

    def __enter__(self) -> "FallbackSpan":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            self.record_exception(exc_val)
        self.end()

    def to_dict(self) -> Dict:
        """Convert span to dictionary for export."""
        return {
            "name": self.name,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": (self.end_time - self.start_time) * 1000 if self.end_time else None,
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
            "status_description": self.status_description,
        }


def init_tracing(app=None, service_name: str = None, exporter: str = None) -> bool:
    """
    Initialize distributed tracing.

    Args:
        app: Flask application instance
        service_name: Override service name
        exporter: Override exporter type

    Returns:
        True if tracing was initialized successfully
    """
    global _tracer, _provider, _initialized

    if _initialized:
        logger.debug("Tracing already initialized")
        return True

    if not TRACING_ENABLED:
        logger.info("Distributed tracing is disabled")
        _initialized = True
        return False

    svc_name = service_name or SERVICE_NAME_VALUE
    exp_type = exporter or EXPORTER_TYPE

    if OTEL_AVAILABLE:
        try:
            # Create resource with service info
            resource = Resource.create(
                {
                    SERVICE_NAME: svc_name,
                    "service.version": os.environ.get("APP_VERSION", "1.0.0"),
                    "deployment.environment": os.environ.get("APP_ENV", "development"),
                }
            )

            # Create sampler
            if SAMPLE_RATE >= 1.0:
                sampler = ALWAYS_ON
            elif SAMPLE_RATE <= 0.0:
                sampler = ALWAYS_OFF
            else:
                sampler = ParentBased(root=TraceIdRatioBased(SAMPLE_RATE))

            # Create provider
            _provider = TracerProvider(resource=resource, sampler=sampler)

            # Add exporter
            span_exporter = _create_exporter(exp_type)
            if span_exporter:
                if exp_type == "console":
                    # Use simple processor for console (immediate output)
                    _provider.add_span_processor(SimpleSpanProcessor(span_exporter))
                else:
                    # Use batch processor for other exporters
                    _provider.add_span_processor(BatchSpanProcessor(span_exporter))

            # Set as global provider
            trace.set_tracer_provider(_provider)

            # Set up context propagation
            set_global_textmap(TraceContextTextMapPropagator())

            # Get tracer
            _tracer = trace.get_tracer(svc_name)

            logger.info(
                f"OpenTelemetry tracing initialized (service={svc_name}, exporter={exp_type})"
            )

        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry: {e}")
            _tracer = None

    # Register Flask hooks if app provided
    if app:
        _register_flask_hooks(app)

    _initialized = True
    return _tracer is not None


def _create_exporter(exporter_type: str):
    """Create the appropriate span exporter."""
    if exporter_type == "console":
        return ConsoleSpanExporter()

    elif exporter_type == "otlp" and OTLP_AVAILABLE:
        return OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True)

    elif exporter_type == "jaeger" and JAEGER_AVAILABLE:
        return JaegerExporter(
            agent_host_name=os.environ.get("JAEGER_HOST", "localhost"),
            agent_port=int(os.environ.get("JAEGER_PORT", 6831)),
        )

    elif exporter_type == "zipkin" and ZIPKIN_AVAILABLE:
        return ZipkinExporter(
            endpoint=os.environ.get("ZIPKIN_ENDPOINT", "http://localhost:9411/api/v2/spans"),
        )

    else:
        logger.warning(f"Exporter '{exporter_type}' not available, using console")
        return ConsoleSpanExporter()


def _register_flask_hooks(app) -> None:
    """Register Flask before/after request hooks for automatic tracing."""
    from flask import g, request

    @app.before_request
    def start_request_span():
        """Start a span for the incoming request."""
        if not TRACING_ENABLED:
            return

        # Extract trace context from incoming headers
        if OTEL_AVAILABLE and _tracer:
            ctx = extract(request.headers)
            span = _tracer.start_span(
                f"{request.method} {request.path}",
                context=ctx,
                kind=SpanKind.SERVER,
            )
            span.set_attributes(
                {
                    "http.method": request.method,
                    "http.url": request.url,
                    "http.route": request.path,
                    "http.scheme": request.scheme,
                    "http.host": request.host,
                    "http.user_agent": request.headers.get("User-Agent", ""),
                    "http.client_ip": request.remote_addr,
                }
            )

            # Link to correlation ID if available
            try:
                from correlation_id import get_correlation_id

                correlation_id = get_correlation_id()
                if correlation_id:
                    span.set_attribute("correlation_id", correlation_id)
            except ImportError:
                pass

            g.trace_span = span
        else:
            # Fallback span
            g.trace_span = FallbackSpan(f"{request.method} {request.path}")
            g.trace_span.set_attributes(
                {
                    "http.method": request.method,
                    "http.url": request.url,
                    "http.route": request.path,
                }
            )

    @app.after_request
    def end_request_span(response):
        """End the request span and add response info."""
        span = getattr(g, "trace_span", None)
        if span:
            if OTEL_AVAILABLE and hasattr(span, "set_attribute"):
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("http.response_content_length", response.content_length or 0)

                # Set status based on response code
                if response.status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                elif response.status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                else:
                    span.set_status(Status(StatusCode.OK))

                span.end()
            elif isinstance(span, FallbackSpan):
                span.set_attribute("http.status_code", response.status_code)
                if response.status_code >= 400:
                    span.set_status("ERROR", f"HTTP {response.status_code}")
                span.end()

        return response

    @app.teardown_request
    def teardown_request_span(exception):
        """Handle exceptions in request span."""
        span = getattr(g, "trace_span", None)
        if span and exception:
            if OTEL_AVAILABLE and hasattr(span, "record_exception"):
                span.record_exception(exception)
                span.set_status(Status(StatusCode.ERROR, str(exception)))
            elif isinstance(span, FallbackSpan):
                span.record_exception(exception)


def get_tracer(name: str = None):
    """
    Get a tracer instance.

    Args:
        name: Tracer name (defaults to service name)

    Returns:
        Tracer instance or None
    """
    if OTEL_AVAILABLE and _provider:
        return trace.get_tracer(name or SERVICE_NAME_VALUE)
    return None


@contextmanager
def trace_span(name: str, attributes: Dict[str, Any] = None, kind: str = "internal"):
    """
    Context manager for creating a traced span.

    Args:
        name: Span name
        attributes: Initial span attributes
        kind: Span kind (internal, server, client, producer, consumer)

    Yields:
        Span instance

    Usage:
        with trace_span("process_data", {"item_count": 100}) as span:
            process_data()
            span.add_event("checkpoint", {"processed": 50})
    """
    if not TRACING_ENABLED:
        yield FallbackSpan(name)
        return

    if OTEL_AVAILABLE and _tracer:
        # Map kind string to SpanKind
        kind_map = {
            "internal": SpanKind.INTERNAL,
            "server": SpanKind.SERVER,
            "client": SpanKind.CLIENT,
            "producer": SpanKind.PRODUCER,
            "consumer": SpanKind.CONSUMER,
        }
        span_kind = kind_map.get(kind, SpanKind.INTERNAL)

        with _tracer.start_as_current_span(name, kind=span_kind) as span:
            if attributes:
                span.set_attributes(attributes)
            yield span
    else:
        span = FallbackSpan(name)
        if attributes:
            span.set_attributes(attributes)
        try:
            yield span
        finally:
            span.end()


def trace_function(
    name: str = None,
    attributes: Dict[str, Any] = None,
    record_args: bool = False,
    record_result: bool = False,
) -> Callable:
    """
    Decorator to trace a function.

    Args:
        name: Span name (defaults to function name)
        attributes: Static span attributes
        record_args: Whether to record function arguments
        record_result: Whether to record function result

    Usage:
        @trace_function
        def my_function(x, y):
            return x + y

        @trace_function(name="custom_name", record_args=True)
        def another_function(data):
            pass
    """

    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            span_attrs = dict(attributes or {})
            span_attrs["function.name"] = func.__name__
            span_attrs["function.module"] = func.__module__

            if record_args:
                span_attrs["function.args"] = str(args)[:200]
                span_attrs["function.kwargs"] = str(kwargs)[:200]

            with trace_span(span_name, span_attrs) as span:
                try:
                    result = func(*args, **kwargs)
                    if record_result:
                        span.set_attribute("function.result", str(result)[:200])
                    return result
                except Exception as e:
                    if hasattr(span, "record_exception"):
                        span.record_exception(e)
                    raise

        return wrapper

    return decorator


def trace_database(operation: str, table: str = None, query: str = None) -> Callable:
    """
    Context manager decorator for tracing database operations.

    Args:
        operation: Database operation (select, insert, update, delete)
        table: Table name
        query: SQL query (will be truncated)

    Usage:
        with trace_database("select", "users"):
            cursor.execute("SELECT * FROM users")
    """

    @contextmanager
    def db_span():
        span_name = f"db.{operation}"
        attrs = {
            "db.system": "sqlite",
            "db.operation": operation,
        }
        if table:
            attrs["db.table"] = table
        if query:
            attrs["db.statement"] = query[:500]  # Truncate long queries

        with trace_span(span_name, attrs, kind="client") as span:
            yield span

    return db_span()


def trace_http_client(method: str, url: str, headers: Dict = None) -> Dict:
    """
    Prepare headers for traced HTTP client request.

    Injects trace context into headers for propagation.

    Args:
        method: HTTP method
        url: Request URL
        headers: Existing headers

    Returns:
        Headers with trace context

    Usage:
        headers = trace_http_client("GET", "http://api.example.com/data")
        response = requests.get(url, headers=headers)
    """
    if headers is None:
        headers = {}

    if OTEL_AVAILABLE:
        # Inject trace context
        inject(headers)

    return headers


def get_trace_context() -> Dict[str, str]:
    """
    Get current trace context for propagation.

    Returns:
        Dictionary with traceparent and tracestate headers
    """
    context = {}
    if OTEL_AVAILABLE:
        inject(context)
    return context


def get_current_span():
    """
    Get the current active span.

    Returns:
        Current span or None
    """
    if OTEL_AVAILABLE:
        return trace.get_current_span()
    return None


def add_span_event(name: str, attributes: Dict[str, Any] = None) -> None:
    """
    Add an event to the current span.

    Args:
        name: Event name
        attributes: Event attributes
    """
    span = get_current_span()
    if span and hasattr(span, "add_event"):
        span.add_event(name, attributes or {})


def set_span_attribute(key: str, value: Any) -> None:
    """
    Set an attribute on the current span.

    Args:
        key: Attribute key
        value: Attribute value
    """
    span = get_current_span()
    if span and hasattr(span, "set_attribute"):
        span.set_attribute(key, value)


def set_span_error(error: Exception) -> None:
    """
    Record an error on the current span.

    Args:
        error: Exception to record
    """
    span = get_current_span()
    if span:
        if OTEL_AVAILABLE and hasattr(span, "record_exception"):
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))
        elif hasattr(span, "record_exception"):
            span.record_exception(error)


class TracingConfig:
    """Configuration helper for distributed tracing."""

    @staticmethod
    def get_config() -> Dict:
        """Get current tracing configuration."""
        return {
            "enabled": TRACING_ENABLED,
            "otel_available": OTEL_AVAILABLE,
            "service_name": SERVICE_NAME_VALUE,
            "exporter": EXPORTER_TYPE,
            "endpoint": OTLP_ENDPOINT if EXPORTER_TYPE == "otlp" else None,
            "sample_rate": SAMPLE_RATE,
            "initialized": _initialized,
            "exporters_available": {
                "console": True,
                "otlp": OTLP_AVAILABLE,
                "jaeger": JAEGER_AVAILABLE,
                "zipkin": ZIPKIN_AVAILABLE,
            },
        }

    @staticmethod
    def is_enabled() -> bool:
        """Check if tracing is enabled."""
        return TRACING_ENABLED and _initialized


def shutdown_tracing() -> None:
    """Shutdown tracing and flush pending spans."""
    global _provider
    if _provider and hasattr(_provider, "shutdown"):
        _provider.shutdown()
        logger.info("Tracing shutdown complete")
