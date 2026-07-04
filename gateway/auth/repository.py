import json
from typing import Optional
from redis.asyncio import Redis
from gateway.auth.models import APIKeyMetadata

class APIKeyRepository:
    """
    Repository for managing API key metadata in Redis.
    """
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self.prefix = "apikey:"

    async def get_key_metadata(self, api_key: str) -> Optional[APIKeyMetadata]:
        """
        Retrieves metadata for a given API key from Redis.
        """
        data = await self.redis_client.get(f"{self.prefix}{api_key}")
        if not data:
            return None
        
        try:
            return APIKeyMetadata.model_validate_json(data)
        except Exception:
            # Handle potential corruption or schema mismatch
            return None

    async def store_key_metadata(self, api_key: str, metadata: APIKeyMetadata):
        """
        Stores metadata for an API key in Redis.
        """
        await self.redis_client.set(
            f"{self.prefix}{api_key}",
            metadata.model_dump_json()
        )
