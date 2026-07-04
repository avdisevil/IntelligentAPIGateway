from fastapi import APIRouter, Depends, HTTPException, Request
from gateway.admin.security import IPAllowlist
from gateway.auth.models import APIKeyMetadata
from gateway.metrics.collector import (
    gateway_requests_total, rate_limit_denied_total,
    cache_hit_total, cache_miss_total
)

router = APIRouter(dependencies=[Depends(IPAllowlist(["127.0.0.1"]))])

def init_admin(app) -> None:
    router.app_ref = app


def _get_repo(request: Request):
    repo = getattr(request.app.state, "repo", None)
    if not repo:
        raise HTTPException(status_code=500, detail="Repository not initialized")
    return repo


def _get_cache(request: Request):
    cache = getattr(request.app.state, "cache", None)
    if not cache:
        raise HTTPException(status_code=500, detail="Cache manager not initialized")
    return cache


@router.get("/keys/{key}")
async def get_key(key: str, request: Request):
    """Retrieve metadata for a specific API key."""
    repo = _get_repo(request)
    metadata = await repo.get_key_metadata(key)
    if not metadata:
        raise HTTPException(status_code=404, detail="Key not found")
    return metadata


@router.post("/keys/{key}")
async def update_key(key: str, metadata: APIKeyMetadata, request: Request):
    """Update or create metadata for an API key."""
    repo = _get_repo(request)
    await repo.store_key_metadata(key, metadata)
    return {"status": "success", "message": f"Key {key} updated"}


@router.get("/cache/{cache_key}")
async def get_cache_entry(cache_key: str, request: Request):
    """Inspect a specific cache entry by its raw Redis key."""
    cache = _get_cache(request)
    entry = await cache.get(cache_key)
    if not entry:
        raise HTTPException(status_code=404, detail="Cache entry not found")
    return entry


@router.get("/metrics/summary")
async def get_metrics_summary():
    """
    Returns a JSON summary of key performance indicators.
    Reads from Prometheus counter registries using their sample values.

    Note: This reads from the in-process Prometheus registry. For production
    use, prefer querying the Prometheus HTTP API for accurate aggregated data.
    """
    def _counter_value(counter) -> float:
        """Safely read total value across all label combinations."""
        try:
            return sum(
                sample.value
                for metric in counter.collect()
                for sample in metric.samples
                if sample.name.endswith("_total")
            )
        except Exception:
            return 0.0

    return {
        "requests": {
            "total": _counter_value(gateway_requests_total),
            "rate_limited": _counter_value(rate_limit_denied_total),
        },
        "cache": {
            "hits": _counter_value(cache_hit_total),
            "misses": _counter_value(cache_miss_total),
        },
    }

@router.post("/metrics/reset")
async def reset_metrics():
    """Resets all Prometheus counters cleanly between benchmark runs."""
    
    metrics_to_reset = [
        gateway_requests_total,
        rate_limit_denied_total,
        cache_hit_total,
        cache_miss_total
    ]
    
    for metric in metrics_to_reset:
        # Clear out all labeled children variations
        if hasattr(metric, "_metrics"):
            metric._metrics.clear()
        # Fallback reset for metrics without labels
        if hasattr(metric, "_value"):
            try:
                metric._value.set(0)
            except AttributeError:
                pass

    return {"status": "success", "message": "All Prometheus metrics have been reset"}

@router.post("/redis/reset")
async def reset_redis(request: Request):
    """Flushes the Redis database."""
    redis_client = getattr(request.app.state, "redis", None)
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis client not initialized")
    await redis_client.flushdb()
    return {"status": "success", "message": "Redis database flushed"}

