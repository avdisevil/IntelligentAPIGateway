from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from fastapi import Request, Response
from gateway.coalescer.manager import RequestCoalescer

class CoalescingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that coalesces identical concurrent GET requests.
    """
    def __init__(self, app, window_ms: int = 100):
        super().__init__(app)
        self.coalescer = RequestCoalescer(window_ms=window_ms)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method != "GET" or request.url.path.rstrip("/") in ["", "/metrics", "/health"]:
            return await call_next(request)

        body = await request.body()
        
        request_hash = self.coalescer.generate_hash(
            method=request.method,
            url=str(request.url),
            body=body
        )

        async def execute_request():
            response = await call_next(request)
            
            # We MUST consume the body to fan it out to multiple awaiters
            if hasattr(response, "body_iterator"):
                body_content = b""
                async for chunk in response.body_iterator:
                    body_content += chunk
            else:
                body_content = response.body
            
            # Extract headers safely. response.headers is normally a Starlette Headers object.
            headers_dict = {k: v for k, v in response.headers.items()}
            
            return {
                "body": body_content,
                "status_code": response.status_code,
                "headers": headers_dict,
                "media_type": getattr(response, "media_type", None)
            }

        result = await self.coalescer.coalesce(request_hash, execute_request)

        return Response(
            content=result["body"],
            status_code=result["status_code"],
            headers={**result["headers"], "X-Coalesced": "true"},
            media_type=result["media_type"]
        )
