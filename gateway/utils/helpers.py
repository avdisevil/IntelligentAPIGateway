"""
gateway/utils/helpers.py

Shared utility functions used across gateway modules.
"""
import hashlib
import json
from typing import Any, Optional
from urllib.parse import urlencode, parse_qsl, urlparse


def build_canonical_url(url: str) -> str:
    """
    Normalizes a URL for consistent cache key generation.
    Sorts query parameters alphabetically so that:
      /api?b=2&a=1  ==  /api?a=1&b=2

    Args:
        url: Raw URL string (may include scheme, host, path, query).

    Returns:
        Normalized URL string with sorted query parameters.
    """
    parsed = urlparse(url)
    sorted_params = sorted(parse_qsl(parsed.query))
    canonical_query = urlencode(sorted_params)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{canonical_query}"


def md5_hex(value: str) -> str:
    """
    Returns the MD5 hex digest of a UTF-8 encoded string.
    Used for fixed-length cache and coalescer keys.

    Args:
        value: Input string to hash.

    Returns:
        32-character lowercase hex string.
    """
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def safe_json_decode(raw: Optional[str]) -> Optional[Any]:
    """
    Decodes a JSON string, returning None on any parse error.
    Prevents crashes from malformed or corrupted Redis values.

    Args:
        raw: JSON string or None.

    Returns:
        Decoded Python object, or None if decoding fails.
    """
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
