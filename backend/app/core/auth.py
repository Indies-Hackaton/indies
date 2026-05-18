"""JWT verification for Clerk sessions.

Fetches JWKS via httpx (which uses certifi/system certs correctly) instead of
PyJWT's built-in urllib client, which fails on macOS Python 3.14 due to missing
CA bundle.

Usage in route handlers:

    from app.core.auth import get_optional_user_id, require_user_id

    # Optional — returns user_id or None (anonymous allowed)
    @router.get("/public")
    async def public_route(user_id: str | None = Depends(get_optional_user_id)):
        ...

    # Required — raises 401 if no valid token
    @router.get("/private")
    async def private_route(user_id: str = Depends(require_user_id)):
        ...
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Simple in-memory JWKS cache: (keys_dict, fetched_at_timestamp)
_jwks_cache: tuple[dict[str, Any], float] | None = None
_JWKS_CACHE_TTL = 3600  # 1 hour


async def _fetch_jwks() -> dict[str, Any]:
    """Fetch JWKS using httpx — handles SSL correctly on all platforms."""
    global _jwks_cache

    now = time.monotonic()
    if _jwks_cache and (now - _jwks_cache[1]) < _JWKS_CACHE_TTL:
        return _jwks_cache[0]

    url = get_settings().CLERK_JWKS_URL
    if not url:
        return {}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    # Build a kid → public_key mapping for fast lookup.
    keys: dict[str, Any] = {}
    for jwk in data.get("keys", []):
        kid = jwk.get("kid")
        if kid:
            keys[kid] = RSAAlgorithm.from_jwk(jwk)

    _jwks_cache = (keys, now)
    logger.debug("JWKS fetched: %d key(s)", len(keys))
    return keys


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):]
    return None


async def get_optional_user_id(request: Request) -> str | None:
    """FastAPI dependency — returns Clerk user_id or None for anonymous."""
    token = _extract_bearer(request)
    if not token:
        return None

    url = get_settings().CLERK_JWKS_URL
    if not url:
        logger.debug("CLERK_JWKS_URL not set; skipping token verification.")
        return None

    try:
        # Decode header to find kid without verifying signature yet.
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            logger.warning("JWT has no kid — treating as anonymous.")
            return None

        keys = await _fetch_jwks()
        public_key = keys.get(kid)

        if public_key is None:
            # Kid not found — refresh cache once and retry.
            global _jwks_cache
            _jwks_cache = None
            keys = await _fetch_jwks()
            public_key = keys.get(kid)

        if public_key is None:
            logger.warning("JWT kid '%s' not in JWKS — treating as anonymous.", kid)
            return None

        payload: dict[str, Any] = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        user_id: str | None = payload.get("sub")
        return user_id or None

    except jwt.ExpiredSignatureError:
        logger.debug("Expired JWT — treating as anonymous.")
        return None
    except jwt.PyJWTError as exc:
        logger.warning("JWT error (treating as anonymous): %s", exc)
        return None
    except httpx.HTTPError as exc:
        logger.warning("JWKS fetch error (treating as anonymous): %s", exc)
        return None
    except Exception as exc:
        logger.warning("Unexpected auth error (treating as anonymous): %s", exc)
        return None


async def require_user_id(
    user_id: str | None = Depends(get_optional_user_id),
) -> str:
    """FastAPI dependency — raises 401 if anonymous."""
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user_id
