import asyncio
import hashlib
import time
from typing import Dict, Any, Coroutine, Callable
from gateway.metrics.collector import batch_calls_total, batch_saved_total, coalesced_requests_total

class RequestCoalescer:
    """
    In-memory request coalescer that aggregates identical concurrent requests.
    """
    def __init__(self, window_ms: int = 100):
        self.window_ms = window_ms
        self._flights: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    def generate_hash(self, method: str, url: str, body: bytes = b"") -> str:
        """Generates a canonical hash for the outbound request."""
        hasher = hashlib.md5()
        hasher.update(method.encode())
        hasher.update(url.encode())
        hasher.update(body)
        return hasher.hexdigest()

    async def coalesce(self, request_hash: str, coro_func: Callable[[], Coroutine[Any, Any, Any]]) -> Any:
        """
        Executes the coroutine or waits for an existing identical flight.
        """
        async with self._lock:
            if request_hash in self._flights:
                future = self._flights[request_hash]
                batch_saved_total.inc()
                coalesced_requests_total.labels(status="coalesced").inc()
                return await future

            # Create a new future and mark as in-flight
            future = asyncio.get_event_loop().create_future()
            self._flights[request_hash] = future
            batch_calls_total.inc()
            coalesced_requests_total.labels(status="first_flight").inc()


        try:
            if self.window_ms > 0:
                await asyncio.sleep(self.window_ms / 1000.0)
            
            result = await coro_func()
            future.set_result(result)
            return result
        except Exception as e:
            future.set_exception(e)
            raise e
        finally:
            async with self._lock:
                # Clean up flight once done
                if self._flights.get(request_hash) == future:
                    del self._flights[request_hash]
