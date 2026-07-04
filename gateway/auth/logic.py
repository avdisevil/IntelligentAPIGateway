from typing import Optional
from fastapi import Request, HTTPException, status
from gateway.auth.repository import APIKeyRepository
from gateway.auth.models import APIKeyMetadata

async def extract_api_key(request: Request) -> Optional[str]:
    """
    Extracts the API key from the Authorization header or x-api-key header.
    Supports 'Authorization: ApiKey <key>' and 'x-api-key: <key>'.
    """
    # Try Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("apikey "):
        return auth_header[7:].strip()

    # Try x-api-key header
    return request.headers.get("x-api-key")

async def authenticate_key(
    api_key: str, 
    repository: APIKeyRepository
) -> APIKeyMetadata:
    """
    Validates the API key against the repository and returns metadata.
    Raises HTTPException 401 if invalid.
    """
    metadata = await repository.get_key_metadata(api_key)
    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return metadata
