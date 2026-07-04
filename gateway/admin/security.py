"""
gateway/admin/security.py

FastAPI dependency for restricting admin routes to trusted source IPs.
"""
from fastapi import Request, HTTPException, status
from typing import List


class IPAllowlist:
    def __init__(self, allowed_ips: List[str] = None):
        self.allowed_ips = allowed_ips or ["127.0.0.1"]

    async def __call__(self, request: Request) -> None:
        client_host = request.client.host if request.client else None

        # Trust X-Forwarded-For only when running behind a trusted reverse proxy.
        # See the security note in the class docstring.
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_host = forwarded_for.split(",")[0].strip()

        # Debug
        # print(f"DEBUG: IPAllowlist checking {client_host} against {self.allowed_ips}")

        if client_host not in self.allowed_ips:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied from IP: {client_host}",
            )
