"""Session store for conversation history.

Supports both in-memory and Redis backends.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from jarvis.config import config

logger = logging.getLogger(__name__)

# Try to import redis
try:
    from redis.asyncio import Redis
    REDIS_AVAILABLE = True
except ImportError:
    Redis = None  # type: ignore
    REDIS_AVAILABLE = False


class SessionStore:
    """Manages conversation history per session."""

    def __init__(self, max_history: int = 20, ttl_seconds: int = 3600):
        self.max_history = max_history
        self.ttl_seconds = ttl_seconds
        self._redis: Optional[Redis] = None
        self._lock = asyncio.Lock()
        self._mem_sessions: dict[str, list[dict[str, Any]]] = {}

    async def _get_redis(self) -> Optional[Redis]:
        """Get Redis connection if configured."""
        if not REDIS_AVAILABLE:
            return None

        redis_url = getattr(config, 'redis_url', None) or None
        if not redis_url:
            return None

        async with self._lock:
            if self._redis is None:
                try:
                    self._redis = Redis.from_url(redis_url, decode_responses=True)
                    await self._redis.ping()
                    logger.info("Connected to Redis for session storage")
                except Exception as e:
                    logger.warning(f"Redis connection failed, using memory: {e}")
                    self._redis = None
            return self._redis

    def _key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"jarvis:session:{session_id}"

    async def get_history(self, session_id: str) -> list[dict[str, Any]]:
        """Get conversation history for a session."""
        redis = await self._get_redis()

        if redis is None:
            return self._mem_sessions.get(session_id, [])

        try:
            raw = await redis.get(self._key(session_id))
            if not raw:
                return []
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
            return self._mem_sessions.get(session_id, [])

    async def set_history(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        """Set conversation history for a session."""
        # Trim to max history
        trimmed = messages[-self.max_history:]

        redis = await self._get_redis()

        if redis is None:
            self._mem_sessions[session_id] = trimmed
            return

        try:
            await redis.set(self._key(session_id), json.dumps(trimmed))
            await redis.expire(self._key(session_id), self.ttl_seconds)
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")
            self._mem_sessions[session_id] = trimmed

    async def append_exchange(
        self,
        session_id: str,
        user_text: str,
        assistant_text: str
    ) -> None:
        """Append a user/assistant exchange to history."""
        history = await self.get_history(session_id)
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": assistant_text})
        await self.set_history(session_id, history)

    async def clear(self, session_id: str) -> None:
        """Clear history for a session."""
        redis = await self._get_redis()

        if redis is None:
            self._mem_sessions.pop(session_id, None)
            return

        try:
            await redis.delete(self._key(session_id))
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")
        self._mem_sessions.pop(session_id, None)

    async def list_sessions(self) -> list[str]:
        """List all session IDs."""
        redis = await self._get_redis()

        if redis is None:
            return list(self._mem_sessions.keys())

        try:
            keys = await redis.keys("jarvis:session:*")
            return [k.replace("jarvis:session:", "") for k in keys]
        except Exception as e:
            logger.warning(f"Redis keys failed: {e}")
            return list(self._mem_sessions.keys())


# Global session store instance
session_store = SessionStore()
