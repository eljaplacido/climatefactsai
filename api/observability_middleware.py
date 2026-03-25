from __future__ import annotations

import time
from uuid import uuid4

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from shared import request_context, telemetry


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Attach request/trace IDs to logs and responses."""

    def __init__(self, app, *, service_name: str = "clilens-api"):
        super().__init__(app)
        telemetry.init_telemetry(service_name=service_name)

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        request_context.set_request_id(request_id)

        try:
            from opentelemetry import propagate, trace
            from opentelemetry.trace import SpanKind
            from opentelemetry.trace.status import Status, StatusCode
        except Exception:
            try:
                response = await call_next(request)
                response.headers["X-Request-ID"] = request_id
                return response
            finally:
                request_context.set_request_id(None)

        try:
            carrier = {k: v for k, v in request.headers.items()}
            ctx = propagate.extract(carrier)
            tracer = trace.get_tracer("clilens.api")

            start = time.perf_counter()
            with tracer.start_as_current_span(
                f"{request.method} {request.url.path}",
                context=ctx,
                kind=SpanKind.SERVER,
            ) as span:
                span.set_attribute("http.method", request.method)
                span.set_attribute("http.target", request.url.path)
                span.set_attribute("http.url", str(request.url))
                span.set_attribute("http.request_id", request_id)

                try:
                    response = await call_next(request)
                except (HTTPException, StarletteHTTPException):
                    # Let FastAPI/Starlette convert known HTTP errors.
                    raise
                except Exception as exc:  # noqa: BLE001
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR))
                    trace_id, _span_id = telemetry.get_trace_ids()
                    headers = {"X-Request-ID": request_id}
                    if trace_id:
                        headers["X-Trace-ID"] = trace_id
                    return JSONResponse(
                        status_code=500,
                        content={
                            "detail": "Internal Server Error",
                            "request_id": request_id,
                            "trace_id": trace_id,
                        },
                        headers=headers,
                    )
                finally:
                    duration_ms = (time.perf_counter() - start) * 1000.0
                    span.set_attribute("http.server_duration_ms", duration_ms)

                response.headers["X-Request-ID"] = request_id
                trace_id, _span_id = telemetry.get_trace_ids()
                if trace_id:
                    response.headers["X-Trace-ID"] = trace_id
                return response
        finally:
            request_context.set_request_id(None)
