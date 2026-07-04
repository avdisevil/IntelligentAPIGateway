import time
from redis.asyncio import Redis

class StatsCollector:
    """
    Lightweight statistics collection using Redis counters with TTLs.
    Tracks requests in sliding windows of 1s, 10s, and 60s per API key.
    """
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self.prefix = "stats"

    async def record_request(self, api_key: str):
        """
        Increments counters for various time windows and tracks the active key.
        """
        now = time.time()
        
        # Windows configuration: (name, duration_seconds, ttl_seconds)
        windows = [
            ("1s", 1, 10),
            ("10s", 10, 60),
            ("60s", 60, 300)
        ]

        async with self.redis_client.pipeline(transaction=False) as pipe:
            # Track this key as active for the next minute
            active_keys_key = f"{self.prefix}:active_keys"
            pipe.sadd(active_keys_key, api_key)
            pipe.expire(active_keys_key, 60)

            for name, duration, ttl in windows:
                bucket_id = int(now // duration)
                key = f"{self.prefix}:{api_key}:{name}:{bucket_id}"
                pipe.incr(key)
                pipe.expire(key, ttl)
            
            await pipe.execute()

    async def get_active_keys(self) -> list[str]:
        """Returns the list of API keys that have been active recently."""
        return await self.redis_client.smembers(f"{self.prefix}:active_keys")

    async def get_stats(self, api_key: str, window_name: str, duration: int) -> int:
        """Retrieves the count for the current bucket of the specified window."""
        bucket_id = int(time.time() // duration)
        key = f"{self.prefix}:{api_key}:{window_name}:{bucket_id}"
        val = await self.redis_client.get(key)
        return int(val) if val else 0
