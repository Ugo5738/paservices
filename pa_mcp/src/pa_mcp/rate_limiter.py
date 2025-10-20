import asyncio
import time
from collections import deque
from typing import Deque, Dict

from fastapi import Request, HTTPException
from starlette.responses import PlainTextResponse

# Simple in-memory sliding-window rate limiter keyed by client identifier.
# Not suitable for multi-process deployments; replace with Redis for production.

_buckets: Dict[str, Deque[float]] = {}
_locks: Dict[str, asyncio.Lock] = {}

RATE_LIMIT = 60  # requests
RATE_PERIOD = 60  # seconds


def _get_key(request: Request) -> str:
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1]
    # fallback to client host
    client = request.client.host if request.client else "unknown"
    return client


async def rate_limit_middleware(request: Request, call_next):
    key = _get_key(request)
    # create per-key structures lazily
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    async with _locks[key]:
        now = time.time()
        bucket = _buckets.get(key)
        if bucket is None:
            bucket = deque()
            _buckets[key] = bucket

        # remove old timestamps
        while bucket and bucket[0] <= now - RATE_PERIOD:
            bucket.popleft()

        if len(bucket) >= RATE_LIMIT:
            retry_after = int(RATE_PERIOD - (now - bucket[0]))
            return PlainTextResponse(
                content="Too Many Requests",
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)

    response = await call_next(request)
    return response
