"""Notification queue for async alerts (timers, alarms, etc.)."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manages notification queues per session."""

    def __init__(self, max_queue_size: int = 100):
        self._session_queues: Dict[str, asyncio.Queue[str]] = {}
        self._lock = asyncio.Lock()
        self._max_queue_size = max_queue_size

    async def _get_queue(self, session_id: str) -> asyncio.Queue[str]:
        """Get or create queue for session."""
        async with self._lock:
            if session_id not in self._session_queues:
                self._session_queues[session_id] = asyncio.Queue(
                    maxsize=self._max_queue_size
                )
            return self._session_queues[session_id]

    async def enqueue(self, session_id: str, message: str) -> None:
        """Add a notification to the session's queue."""
        q = await self._get_queue(session_id)
        try:
            q.put_nowait(message)
            logger.debug(f"Notification queued for {session_id}: {message[:50]}...")
        except asyncio.QueueFull:
            # Drop oldest by draining one, then add
            try:
                _ = q.get_nowait()
            except Exception:
                pass
            await q.put(message)
            logger.warning(f"Notification queue full for {session_id}, dropped oldest")

    async def dequeue(self, session_id: str, timeout: float = 0.1) -> Optional[str]:
        """Get next notification (non-blocking with timeout)."""
        q = await self._get_queue(session_id)
        try:
            return await asyncio.wait_for(q.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def wait_for_message(
        self,
        session_id: str,
        timeout_sec: float = 25.0
    ) -> Optional[str]:
        """Wait for a notification (long-polling style)."""
        q = await self._get_queue(session_id)
        try:
            return await asyncio.wait_for(q.get(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            return None

    async def get_all_pending(self, session_id: str) -> list[str]:
        """Get all pending notifications without blocking."""
        q = await self._get_queue(session_id)
        messages = []
        while True:
            try:
                msg = q.get_nowait()
                messages.append(msg)
            except asyncio.QueueEmpty:
                break
        return messages

    async def has_pending(self, session_id: str) -> bool:
        """Check if session has pending notifications."""
        q = await self._get_queue(session_id)
        return not q.empty()

    async def clear(self, session_id: str) -> int:
        """Clear all pending notifications for session. Returns count cleared."""
        q = await self._get_queue(session_id)
        count = 0
        while True:
            try:
                q.get_nowait()
                count += 1
            except asyncio.QueueEmpty:
                break
        return count

    async def broadcast(self, message: str) -> int:
        """Send notification to all sessions. Returns count of sessions notified."""
        async with self._lock:
            sessions = list(self._session_queues.keys())

        count = 0
        for session_id in sessions:
            await self.enqueue(session_id, message)
            count += 1

        return count


# Global notification manager instance
notify = NotificationManager()


# Convenience functions for timer/alarm integration
async def notify_timer_finished(session_id: str, label: str = "") -> None:
    """Notify that a timer has finished."""
    message = f"Timer{f' for {label}' if label else ''} finished!"
    await notify.enqueue(session_id, message)


async def notify_alarm_triggered(session_id: str, title: str, message: str = "") -> None:
    """Notify that an alarm has triggered."""
    notification = f"Alarm: {message or title}"
    await notify.enqueue(session_id, notification)


async def notify_reminder(session_id: str, text: str) -> None:
    """Send a reminder notification."""
    await notify.enqueue(session_id, f"Reminder: {text}")
