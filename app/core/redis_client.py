"""Lazy Redis client used by the rate limiter."""

from __future__ import annotations

import logging
from typing import Any

try:
    import redis.asyncio as redis_asyncio
except ImportError:  # pragma: no cover - dependency is declared but be defensive
    redis_asyncio = None  # type: ignore[assignment]

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Any | None = None


async def get_redis() -> Any | None:
    """Return a connected Redis client, or `None` if Redis is unavailable.

    The rate limiter falls back to an in-process counter when this returns
    `None`, so callers don't have to special-case missing Redis.
    """
    global _client
    if redis_asyncio is None:
        return None
    if _client is not None:
        return _client
    try:
        _client = redis_asyncio.from_url(
            str(settings.REDIS_URL), encoding="utf-8", decode_responses=True
        )
        await _client.ping()
    except Exception as exc:  # noqa: BLE001 - any failure → fall back
        logger.warning("Redis unavailable, rate-limit will use in-memory: %s", exc)
        _client = None
    return _client
