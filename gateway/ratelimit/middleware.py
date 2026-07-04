from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from fastapi import Request, Response, status
from gateway.ratelimit.limiter import TokenBucketLimiter
from gateway.metrics.collector import rate_limit_denied_total
import redis.asyncio as redis

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limits using the token bucket algorithm.
    Expects request.state.api_key and request.state.api_key_metadata to be set by AuthMiddleware.
    """
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Get limiter from app state
        limiter = getattr(request.app.state, "limiter", None)
        
        # Exempt health check, docs, and metrics (including trailing slashes)
        path = request.url.path.rstrip("/")
        if path in ("", "/health", "/docs", "/openapi.json", "/metrics"):
            return await call_next(request)

        # Check if authenticated
        api_key = getattr(request.state, "api_key", None)
        metadata = getattr(request.state, "api_key_metadata", None)

        if not api_key or not metadata or not limiter:
            # If no auth context or limiter missing, skip rate limiting
            return await call_next(request)

        # Enforce rate limit
        # capacity: burst_capacity
        # refill_rate: default_qps
        allowed = await limiter.is_allowed(
            key=api_key,
            capacity=metadata.burst_capacity,
            refill_rate=metadata.default_qps,
            tokens_needed=1
        )

        if not allowed:
            # Increment Prometheus metric
            rate_limit_denied_total.labels(api_key=api_key).inc()
            
            return Response(
                content='{"detail": "Rate limit exceeded. Too many requests."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
                headers={"Retry-After": "1"}
            )

        return await call_next(request)
