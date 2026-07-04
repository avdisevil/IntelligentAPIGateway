import httpx
import time
from fastapi import Request, HTTPException
from gateway.metrics.collector import simulated_cost_total, upstream_requests_total
from gateway.config import settings
from gateway.proxy.handler import forward_with_retry
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DownstreamProxy:
    """
    Handles forwarding requests to the simulated paid API and accounting for costs.
    Uses a persistent AsyncClient for connection reuse.
    """
    def __init__(self, base_url: str = None, client: httpx.AsyncClient = None):
        self.base_url = base_url or settings.SIMULATOR_URL
        # If an external client is injected (e.g., for tests), use it;
        # otherwise create and own a persistent client on first use.
        self._external_client = client
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Returns the persistent client, creating it on first call."""
        if self._external_client is not None:
            return self._external_client
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def aclose(self):
        """Gracefully closes the persistent client. Call from lifespan shutdown."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def forward_process(self, data: str) -> dict:
        """Proxies a single processing request with retry/timeout handling."""
        client = self._get_client()
        start = time.perf_counter()
        status_code = "500"
        try:
            response = await forward_with_retry(
                client,
                "POST",
                f"{self.base_url}/v1/process",
                json={"data": data},
            )
            status_code = str(response.status_code)
            payload = response.json()

            # Record cost metric
            cost = payload.get("billing", {}).get("cost", 0)
            simulated_cost_total.inc(cost)

            return payload
        except httpx.HTTPError as e:
            logger.error(f"Downstream proxy error: {e}")
            raise HTTPException(status_code=502, detail="Downstream service error")
        finally:
            duration = time.perf_counter() - start
            try:
                from gateway.metrics.middleware import downstream_duration_var
                downstream_duration_var.set(downstream_duration_var.get() + duration)
            except Exception:
                pass
            upstream_requests_total.labels(service="simulator", status=status_code).inc()

    async def forward_batch(self, items: list) -> dict:
        """Proxies a batch processing request with retry/timeout handling."""
        client = self._get_client()
        start = time.perf_counter()
        status_code = "500"
        try:
            response = await forward_with_retry(
                client,
                "POST",
                f"{self.base_url}/v1/batch",
                json={"items": [{"data": item} for item in items]},
            )
            status_code = str(response.status_code)
            payload = response.json()

            # Record cost metric
            cost = payload.get("billing", {}).get("cost", 0)
            simulated_cost_total.inc(cost)

            return payload
        except httpx.HTTPError as e:
            logger.error(f"Downstream batch proxy error: {e}")
            raise HTTPException(status_code=502, detail="Downstream service error")
        finally:
            duration = time.perf_counter() - start
            try:
                from gateway.metrics.middleware import downstream_duration_var
                downstream_duration_var.set(downstream_duration_var.get() + duration)
            except Exception:
                pass
            upstream_requests_total.labels(service="simulator", status=status_code).inc()

