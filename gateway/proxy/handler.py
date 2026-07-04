"""
gateway/proxy/handler.py

Low-level HTTP forwarding utility with retry and timeout support.
Used by DownstreamProxy (routing/router.py) for all outbound calls.
"""
import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


async def forward_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    json: Optional[dict] = None,
    max_retries: int = 3,
    timeout_seconds: float = 10.0,
    backoff_base: float = 0.5,
) -> httpx.Response:
    """
    Forward an HTTP request with exponential-backoff retries.

    Retries are attempted on transient errors only (timeouts and connection
    failures). HTTP error responses (4xx/5xx) are returned immediately without
    retrying — the caller decides how to handle them.

    Args:
        client:          Persistent AsyncClient to use for the call.
        method:          HTTP method (e.g. "POST", "GET").
        url:             Full target URL.
        json:            Optional JSON body payload.
        max_retries:     Maximum number of attempts (default 3).
        timeout_seconds: Per-attempt timeout in seconds (default 10).
        backoff_base:    Base delay in seconds; multiplied by attempt index
                         for exponential backoff (default 0.5s → 0.5/1.0/1.5…).

    Returns:
        httpx.Response on success.

    Raises:
        httpx.TimeoutException | httpx.ConnectError: if all retries are exhausted.
    """
    last_exc: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            response = await asyncio.wait_for(
                client.request(method, url, json=json),
                timeout=timeout_seconds,
            )
            return response
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_exc = e
            if attempt < max_retries - 1:
                delay = backoff_base * (attempt + 1)
                logger.warning(
                    f"Downstream call to {url} failed (attempt {attempt + 1}/{max_retries}): "
                    f"{e}. Retrying in {delay:.1f}s…"
                )
                await asyncio.sleep(delay)

    logger.error(
        f"All {max_retries} attempts to {url} failed. Last error: {last_exc}"
    )
    raise last_exc  # type: ignore[misc]
