from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from fastapi import Request, Response, HTTPException, status
from gateway.auth.logic import extract_api_key, authenticate_key
from gateway.auth.repository import APIKeyRepository
import redis.asyncio as redis
from gateway.config import settings

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle API Key authentication for all incoming requests.
    """
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Get repository from app state
        repo = getattr(request.app.state, "repo", None)
        
        # Exempt common paths, metrics, and standalone simulator routes
        path = request.url.path.rstrip("/")
        if path in ("", "/health", "/docs", "/openapi.json", "/metrics") or \
           request.url.path.startswith(("/simulator", "/admin", "/docs", "/openapi.json")):
            return await call_next(request)

        if not repo:
            # If repo is missing (startup issue), fail closed for security
            return Response(
                content='{"detail": "Authentication service unavailable"}',
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                media_type="application/json"
            )

        api_key = await extract_api_key(request)
        if not api_key:
            return Response(
                content='{"detail": "Missing API Key"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        try:
            metadata = await authenticate_key(api_key, repo)
            # Inject authenticated key context into request state
            request.state.api_key = api_key
            request.state.api_key_metadata = metadata
        except HTTPException as exc:
            return Response(
                content=f'{{"detail": "{exc.detail}"}}',
                status_code=exc.status_code,
                media_type="application/json",
                headers=exc.headers,
            )
        except Exception:
            # Redis or other infrastructure errors - fail closed with 503
            return Response(
                content='{"detail": "Authentication service unavailable"}',
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                media_type="application/json"
            )

        response = await call_next(request)
        return response
