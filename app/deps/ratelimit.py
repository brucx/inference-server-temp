import asyncio
from datetime import datetime, timedelta

import structlog
from fastapi import HTTPException, status

logger = structlog.get_logger()


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list] = {}
        self._lock = asyncio.Lock()

    async def check_rate_limit(self, key: str) -> None:
        async with self._lock:
            now = datetime.now()
            minute_ago = now - timedelta(minutes=1)

            if key not in self.requests:
                self.requests[key] = []

            self.requests[key] = [
                timestamp for timestamp in self.requests[key] if timestamp > minute_ago
            ]

            if len(self.requests[key]) >= self.requests_per_minute:
                logger.warning(f"Rate limit exceeded for key: {key[:8]}...")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute.",
                )

            self.requests[key].append(now)

    async def reset(self, key: str) -> None:
        async with self._lock:
            if key in self.requests:
                del self.requests[key]
                logger.info(f"Rate limit reset for key: {key[:8]}...")
