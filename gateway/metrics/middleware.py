import time
import logging
import contextvars
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from fastapi import Request, Response
from gateway.metrics.collector import (
    gateway_requests_total,
    gateway_request_duration_seconds,
    gateway_overhead_seconds,
    active_requests
)
from gateway.analyzer.stats import StatsCollector

logger = logging.getLogger(__name__)

# Internal header set by the SWR revalidation path. Skip metric recording
# for these internal calls to avoid double-counting genuine user requests.
_REVALIDATE_HEADER = "x-internal-cache-revalidate"

# Context variable to accumulate downstream request durations in the async task scope.
downstream_duration_var = contextvars.ContextVar("downstream_duration", default=0.0)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track global request metrics and lightweight per-key statistics.
    """
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Exempt health and metrics from tracking to avoid noise.
        # Also skip internal SWR revalidation calls (avoid double-counting).
        if request.url.path in ["/health", "/metrics"] or \
                request.headers.get(_REVALIDATE_HEADER) == "1":
            return await call_next(request)

        active_requests.inc()
        # Initialize/reset downstream duration for this request flow
        token = downstream_duration_var.set(0.0)

        start_time = time.perf_counter()
        endpoint = request.url.path

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception:
            status_code = "500"
            raise
        finally:
            process_time = time.perf_counter() - start_time
            active_requests.dec()

            # api_key injected by AuthMiddleware (or "anonymous" if unauthenticated)
            api_key = getattr(request.state, "api_key", "anonymous")

            gateway_requests_total.labels(
                endpoint=endpoint,
                status=status_code,
                api_key=api_key,
            ).inc()
            gateway_request_duration_seconds.labels(endpoint=endpoint).observe(process_time)

            downstream_duration = downstream_duration_var.get()
            overhead = max(0.0, process_time - downstream_duration)
            gateway_overhead_seconds.labels(endpoint=endpoint).observe(overhead)
            downstream_duration_var.reset(token)

            if api_key != "anonymous":
                stats: StatsCollector | None = getattr(
                    request.app.state, "stats", None
                )
                if stats:
                    try:
                        await stats.record_request(api_key)
                    except Exception as e:
                        logger.warning(f"Stats recording failed for {api_key}: {e}")

        return response

