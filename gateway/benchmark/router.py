import asyncio
from fastapi import APIRouter, Response

router = APIRouter()


@router.get("/slow")
async def slow_endpoint():
    """
    Sleeps for exactly 1000ms. Safe for concurrency testing.
    """
    await asyncio.sleep(1.0)
    return {"status": "success", "message": "slow response after 1000ms"}


@router.get("/cache")
async def cache_endpoint(response: Response):
    """
    Returns a fast response cacheable via Cache-Control header.
    No artificial backend assumptions, just standard Cache-Control.
    """
    response.headers["Cache-Control"] = "max-age=10"
    return {"status": "success", "message": "this response is cacheable"}


@router.get("/coalesce")
async def coalesce_endpoint():
    """
    Simulates a slow upstream request (e.g. database query, ML inference) taking 500ms.
    Used to demonstrate the savings when multiple concurrent requests are coalesced.
    """
    await asyncio.sleep(0.5)
    return {"status": "success", "message": "response after 500ms database simulation"}
