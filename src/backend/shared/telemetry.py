"""OpenTelemetry bootstrap helpers.

Designed to be safe to import in any process (API, Celery workers, agents).
If OpenTelemetry SDK/exporter deps are missing, this becomes a no-op.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

from .config import get_settings

_initialized = False


def _normalize_http_otlp_traces_endpoint(endpoint: str) -> str:
    endpoint = endpoint.strip()
    if not endpoint:
        return endpoint
    # OTLP HTTP traces default path is /v1/traces.
    if endpoint.endswith("/v1/traces"):
        return endpoint
    if endpoint.endswith("/"):
        return endpoint + "v1/traces"
    return endpoint + "/v1/traces"


def init_telemetry(*, service_name: Optional[str] = None) -> bool:
    """Initialize OpenTelemetry tracing once per process.

    Returns:
        True if telemetry was initialized by this call, False otherwise.
    """
    global _initialized
    if _initialized:
        return False

    if os.getenv("OTEL_ENABLED", "true").lower() in {"0", "false", "no"}:
        _initialized = True
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception:
        # SDK not installed; keep application functional.
        _initialized = True
        return False

    settings = get_settings()
    env_service = os.getenv("OTEL_SERVICE_NAME") or settings.observability.otel_service_name
    resolved_service = service_name or env_service

    protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf").lower()
    endpoint = (
        os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or settings.observability.otel_exporter_otlp_endpoint
    )

    try:
        if protocol.startswith("http"):
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore

            exporter = OTLPSpanExporter(
                endpoint=_normalize_http_otlp_traces_endpoint(endpoint),
            )
        else:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # type: ignore

            exporter = OTLPSpanExporter(
                endpoint=endpoint,
                insecure=True,
            )
    except Exception:
        _initialized = True
        return False

    resource = Resource.create(
        {
            "service.name": resolved_service,
            "deployment.environment": settings.environment,
        }
    )

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _initialized = True
    return True


def get_trace_ids() -> Tuple[Optional[str], Optional[str]]:
    """Return (trace_id, span_id) from the current OpenTelemetry context."""
    try:
        from opentelemetry import trace
    except Exception:
        return None, None

    span = trace.get_current_span()
    if span is None:
        return None, None
    ctx = span.get_span_context()
    if ctx is None or not getattr(ctx, "is_valid", False):
        return None, None
    return f"{ctx.trace_id:032x}", f"{ctx.span_id:016x}"

