import json
import time
import asyncio
import logging
from urllib.parse import urlparse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from fastapi import Request, Response
from gateway.cache.manager import CacheManager
from gateway.metrics.collector import cache_hit_total, cache_miss_total, cache_swr_hit_total
import httpx

logger = logging.getLogger(__name__)

# Internal header used to bypass cache during SWR background revalidation.
# Requests carrying this header skip all caching logic to prevent recursion.
_REVALIDATE_HEADER = "x-internal-cache-revalidate"


class ResponseCacheMiddleware(BaseHTTPMiddleware):
    """
    Middleware that caches successful idempotent GET responses in Redis.
    Implements Stale-While-Revalidate (SWR): stale responses are served
    immediately while a background task refreshes the cache via an internal
    self-request (httpx + ASGITransport).
    """
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip caching entirely for internal SWR revalidation calls
        if request.headers.get(_REVALIDATE_HEADER) == "1":
            return await call_next(request)

        cache: CacheManager | None = getattr(request.app.state, "cache", None)

        # Skip if no cache, not a GET, or exempt path
        if not cache or request.method != "GET" or request.url.path.rstrip("/") in ["", "/metrics", "/health"]:
            return await call_next(request)

        cache_key = cache.generate_key(str(request.url))

        # Check cache — bypass gracefully on Redis error
        try:
            cached_response = await cache.get(cache_key)
        except Exception:
            return await call_next(request)

        if cached_response:
            soft_expiry = cached_response.get("soft_expiry", 0)

            # Case A: Fresh hit — serve from cache
            if time.time() < soft_expiry:
                cache_hit_total.inc()
                return self._build_cached_response(cached_response, "HIT")

            # Stale hit (SWR) — serve stale immediately,
            # trigger background refresh via internal self-request
            cache_swr_hit_total.inc()
            asyncio.create_task(
                self._revalidate_in_background(cache_key, cache, request)
            )
            return self._build_cached_response(cached_response, "STALE")

        # Case C: Cache miss — call downstream and cache the result
        cache_miss_total.inc()
        response = await call_next(request)

        if response.status_code == 200:
            body = await self._read_body(response)
            ttl = cache.parse_cache_control(response.headers.get("Cache-Control", ""))
            exclude_headers = {"content-length", "x-cache"}
            headers = {
                k: v for k, v in response.headers.items()
                if k.lower() not in exclude_headers
            }
            try:
                await cache.set(cache_key, {
                    "content": body.decode("utf-8", errors="ignore"),
                    "status_code": response.status_code,
                    "headers": headers,
                    "media_type": response.media_type,
                }, ttl=ttl)
            except Exception as e:
                logger.warning(f"Cache write failed for {cache_key}: {e}")

            return Response(
                content=body,
                status_code=response.status_code,
                headers={**headers, "X-Cache": "MISS"},
                media_type=response.media_type,
            )

        return response

    def _build_cached_response(self, cached_data: dict, x_cache: str) -> Response:
        return Response(
            content=cached_data["content"],
            status_code=cached_data["status_code"],
            headers={**cached_data["headers"], "X-Cache": x_cache},
            media_type=cached_data["media_type"],
        )

    @staticmethod
    async def _read_body(response: Response) -> bytes:
        """Reads the full response body from a streaming or buffered response."""
        if hasattr(response, "body_iterator"):
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            return body
        return response.body

    async def _revalidate_in_background(
        self, cache_key: str, cache: CacheManager, request: Request
    ):
        """
        Refreshes the cache via an internal self-request using httpx.ASGITransport.
        """
        if not await cache.acquire_lock(cache_key):
            return  # Another request is already revalidating

        try:
            # Reconstruct the path+query from the original URL
            parsed = urlparse(str(request.url))
            path = parsed.path
            query = parsed.query
            full_path = f"{path}?{query}" if query else path

            # Forward original headers but mark this as an internal revalidation
            # so the cache middleware (and metrics) skip processing it
            headers = {
                k: v for k, v in request.headers.items()
                if k.lower() not in ("host", "content-length")
            }
            headers[_REVALIDATE_HEADER] = "1"

            transport = httpx.ASGITransport(app=request.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://internal"
            ) as client:
                resp = await client.get(full_path, headers=headers)

            if resp.status_code == 200:
                ttl = cache.parse_cache_control(
                    resp.headers.get("cache-control", "")
                )
                exclude_headers = {
                    "content-length", "x-cache", _REVALIDATE_HEADER
                }
                filtered_headers = {
                    k: v for k, v in resp.headers.items()
                    if k.lower() not in exclude_headers
                }
                await cache.set(cache_key, {
                    "content": resp.text,
                    "status_code": resp.status_code,
                    "headers": filtered_headers,
                    "media_type": resp.headers.get("content-type"),
                }, ttl=ttl)
        except Exception as e:
            logger.error(f"SWR background revalidation failed for {cache_key}: {e}")
        finally:
            await cache.release_lock(cache_key)
