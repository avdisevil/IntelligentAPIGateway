import time
from typing import Optional
from redis.asyncio import Redis
from redis.exceptions import ResponseError
import os

class TokenBucketLimiter:
    """
    Redis-based Token Bucket Rate Limiter using Lua scripting.
    The Lua script is loaded once and cached by SHA. On Redis restart the SHA
    is invalidated; NOSCRIPT errors are caught and the script is reloaded
    transparently before retrying.
    """
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self.script_path = os.path.join(
            os.path.dirname(__file__), "lua", "token_bucket.lua"
        )
        self._script_sha: Optional[str] = None

    async def _load_script(self):
        """Loads the Lua script into Redis and caches the SHA."""
        if self._script_sha is None:
            with open(self.script_path, "r") as f:
                script_content = f.read()
            self._script_sha = await self.redis_client.script_load(script_content)

    async def _evalsha(self, redis_key: str, now_ms: int, tokens_needed: int,
                        capacity: int, rate_per_ms: float) -> int:
        """Execute the token bucket Lua script, with NOSCRIPT recovery."""
        try:
            return await self.redis_client.evalsha(
                self._script_sha, 1,
                redis_key, now_ms, tokens_needed, capacity, rate_per_ms
            )
        except ResponseError as e:
            if "NOSCRIPT" not in str(e):
                raise
            # Redis was restarted and flushed its script cache — reload and retry once.
            self._script_sha = None
            await self._load_script()
            return await self.redis_client.evalsha(
                self._script_sha, 1,
                redis_key, now_ms, tokens_needed, capacity, rate_per_ms
            )

    async def is_allowed(
        self,
        key: str,
        capacity: int,
        refill_rate: float,
        tokens_needed: int = 1
    ) -> bool:
        """
        Checks if the request is allowed under the rate limit.
        - key: The unique identifier for the bucket (e.g., API key).
        - capacity: Maximum tokens in the bucket (burst size).
        - refill_rate: Tokens added per second (sustained QPS).
        - tokens_needed: Number of tokens to consume (default 1).
        Returns True if allowed, False if rate-limited.
        """
        await self._load_script()

        rate_per_ms = refill_rate / 1000.0
        now_ms = int(time.time() * 1000)
        redis_key = f"ratelimit:{key}"

        result = await self._evalsha(redis_key, now_ms, tokens_needed, capacity, rate_per_ms)
        return bool(result)
