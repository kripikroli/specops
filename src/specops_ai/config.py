"""Auto-configuration for SpecOps tracing."""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)

_tracer: trace.Tracer | None = None
_configured = False


def configure(
    service_name: str | None = None,
    endpoint: str | None = None,
    *,
    enabled: bool = True,
) -> None:
    """Configure the SpecOps tracer.

    Falls back to environment variables:
      - OTEL_SERVICE_NAME (default: "specops")
      - OTEL_EXPORTER_OTLP_ENDPOINT (default: None → console exporter)
      - SPECOPS_ENABLED (default: "true")
    """
    global _tracer, _configured  # noqa: PLW0603

    if not enabled or os.environ.get("SPECOPS_ENABLED", "true").lower() == "false":
        _tracer = trace.NoOpTracer()
        _configured = True
        return

    svc = service_name or os.environ.get("OTEL_SERVICE_NAME", "specops")
    resource = Resource.create({"service.name": svc})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    exporter: SpanExporter
    if otlp_endpoint:
        protocol = os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "http/json")
        traces_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        if protocol == "grpc":
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter as GrpcExporter,
                )

                exporter = GrpcExporter(endpoint=traces_endpoint or otlp_endpoint)
            except ImportError:
                exporter = ConsoleSpanExporter()
        else:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter as HttpExporter,
                )

                exporter = HttpExporter(
                    endpoint=traces_endpoint or f"{otlp_endpoint.rstrip('/')}/v1/traces"
                )
            except ImportError:
                exporter = ConsoleSpanExporter()
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracer = provider.get_tracer("specops", "0.1.0")
    _configured = True


def get_tracer() -> trace.Tracer:
    """Get the configured tracer, initializing with defaults if needed."""
    global _tracer  # noqa: PLW0603
    if not _configured:
        configure()
    assert _tracer is not None
    return _tracer


def reset() -> None:
    """Reset configuration (for testing)."""
    global _tracer, _configured  # noqa: PLW0603
    _tracer = None
    _configured = False
