"""
gateway/deps.py

FastAPI dependency functions for injecting shared resources into route handlers.
These are the canonical injection points; middleware should prefer reading from
request.app.state directly.
"""
from fastapi import Request
from redis.asyncio import Redis


async def get_redis(request: Request) -> Redis:
    """
    Dependency: returns the shared async Redis client from app.state.
    The client is created once during lifespan and torn down on shutdown.

    Usage:
        @app.get("/example")
        async def handler(redis: Redis = Depends(get_redis)):
            value = await redis.get("some-key")
    """
    return request.app.state.redis


async def get_db():
    """
    Placeholder for a relational database session dependency.
    Implement when a SQL/NoSQL store is added to the gateway.
    """
    # Example pattern for SQLAlchemy async sessions:
    # async with AsyncSessionLocal() as session:
    #     yield session
    pass
