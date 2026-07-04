import json
import hashlib
import time
from typing import Optional, Dict, Any
from urllib.parse import urlencode, parse_qsl, urlparse
from redis.asyncio import Redis

class CacheManager:
    """
    Handles Redis-based response caching with canonical key generation.
    """
    def __init__(self, redis_client: Redis, default_ttl: int = 60):
        self.redis_client = redis_client
        self.default_ttl = default_ttl
        self.prefix = "cache"

    def generate_key(self, url: str) -> str:
        """
        Generates a canonical cache key from the URL.
        Sorted query params ensure consistent keys for the same request.
        """
        parsed = urlparse(url)
        # Sort query parameters
        query_params = sorted(parse_qsl(parsed.query))
        canonical_query = urlencode(query_params)
        
        # Build normalized URL
        normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{canonical_query}"
        
        # Use MD5 hash for fixed-length keys
        url_hash = hashlib.md5(normalized_url.encode('utf-8')).hexdigest()
        return f"{self.prefix}:{url_hash}"

    async def set(self, key: str, response_data: Dict[str, Any], ttl: Optional[int] = None):
        """
        Stores response data with a soft expiry for SWR.
        Actual Redis TTL is extended by a grace period.
        """
        ttl = ttl if ttl is not None else self.default_ttl
        grace_period = 30 # SWR window
        
        # Add metadata for SWR
        response_data["soft_expiry"] = time.time() + ttl
        
        await self.redis_client.setex(
            key,
            ttl + grace_period,
            json.dumps(response_data)
        )

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieves cached response data for a key, or None on miss."""
        data = await self.redis_client.get(key)
        return json.loads(data) if data else None

    async def acquire_lock(self, key: str, ttl: int = 5) -> bool:
        """Acquires a distributed lock for a cache key to prevent stampede."""
        lock_key = f"lock:{key}"
        # Set if not exists, with a safety TTL
        return await self.redis_client.set(lock_key, "1", ex=ttl, nx=True)

    async def release_lock(self, key: str):
        """Releases the distributed lock."""
        await self.redis_client.delete(f"lock:{key}")

    def parse_cache_control(self, cache_control: str) -> Optional[int]:
        """Simple parser for Cache-Control: max-age=N."""
        if not cache_control:
            return None
        
        parts = [p.strip() for p in cache_control.split(',')]
        for part in parts:
            if part.startswith("max-age="):
                try:
                    return int(part.split('=')[1])
                except (IndexError, ValueError):
                    return None
        return None
