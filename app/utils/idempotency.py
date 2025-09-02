import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger()


class IdempotencyCache:
    def __init__(self, ttl_seconds: int = 3600):
        self.cache: dict[str, tuple[str, datetime]] = {}
        self.ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()

    def _compute_hash(self, data: dict[str, Any]) -> str:
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    async def get_task_id(self, client_request_id: str) -> str | None:
        async with self._lock:
            self._cleanup_expired()

            if client_request_id in self.cache:
                task_id, timestamp = self.cache[client_request_id]
                if datetime.now() - timestamp < timedelta(seconds=self.ttl_seconds):
                    logger.info(f"Found cached task_id for client_request_id: {client_request_id}")
                    return task_id
                else:
                    del self.cache[client_request_id]

            return None

    async def set_task_id(self, client_request_id: str, task_id: str) -> None:
        async with self._lock:
            self.cache[client_request_id] = (task_id, datetime.now())
            logger.info(f"Cached task_id for client_request_id: {client_request_id}")

    async def get_by_content(self, request_data: dict[str, Any]) -> str | None:
        request_hash = self._compute_hash(request_data)
        return await self.get_task_id(request_hash)

    async def set_by_content(self, request_data: dict[str, Any], task_id: str) -> None:
        request_hash = self._compute_hash(request_data)
        await self.set_task_id(request_hash, task_id)

    def _cleanup_expired(self) -> None:
        now = datetime.now()
        expired_keys = [
            key
            for key, (_, timestamp) in self.cache.items()
            if now - timestamp > timedelta(seconds=self.ttl_seconds)
        ]

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

    async def clear(self) -> None:
        async with self._lock:
            self.cache.clear()
            logger.info("Cleared idempotency cache")
