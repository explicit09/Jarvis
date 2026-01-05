"""Alarm, timer, and reminder tools for J.A.R.V.I.S."""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Dict, Optional

from livekit.agents import llm

from jarvis.storage import get_connection

logger = logging.getLogger(__name__)

# Active quick timers (in-memory, for short duration timers)
_ACTIVE_TIMERS: Dict[str, asyncio.Task] = {}
_TIMER_LABELS: Dict[str, str] = {}
_timer_callback: Optional[Callable[[str], Awaitable[None]]] = None

# Number words for natural language parsing
_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "a": 1, "an": 1, "half": 30,  # "half a minute" = 30 seconds
}

_scheduler_task: Optional[asyncio.Task] = None
_alarm_callback: Optional[Callable[[str], Awaitable[None]]] = None


def _parse_duration(value: str) -> Optional[int]:
    """
    Parse a duration string into seconds.

    Supports formats like:
    - "10" or "10s" or "10 seconds" -> 10 seconds
    - "5m" or "5 minutes" -> 300 seconds
    - "1h" or "1 hour" -> 3600 seconds
    - "five minutes" -> 300 seconds
    - "2m30s" or "2 minutes 30 seconds" -> 150 seconds
    - "half a minute" -> 30 seconds

    Returns None if parsing fails.
    """
    if not value:
        return None

    text = value.strip().lower()

    # Handle "half a minute" / "half an hour"
    if "half" in text:
        if "hour" in text:
            return 1800  # 30 minutes
        elif "minute" in text:
            return 30

    # Pattern: "10", "10s", "10 sec", "10 seconds", "5m", "5 min", "1h", "1 hour"
    m = re.match(
        r"^(\d+)\s*(h|hr|hrs|hour|hours|m|min|mins|minute|minutes|s|sec|secs|second|seconds)?$",
        text
    )
    if m:
        num = int(m.group(1))
        unit = (m.group(2) or "s").lower()
        if unit.startswith("h"):
            return num * 3600
        elif unit.startswith("m"):
            return num * 60
        return num

    # Word numbers: "five", "ten minutes", "twenty seconds"
    m2 = re.match(r"^(\w+)\s*(hour|hours|minute|minutes|min|mins|sec|secs|second|seconds)?$", text)
    if m2:
        word = m2.group(1)
        unit = (m2.group(2) or "seconds").lower()
        if word in _NUMBER_WORDS:
            num = _NUMBER_WORDS[word]
            if unit.startswith("h"):
                return num * 3600
            elif unit.startswith("m"):
                return num * 60
            return num

    # Composite: "2m30s", "1h30m", "1 hour 30 minutes", "2 minutes and 30 seconds"
    # First try compact format
    comp = re.findall(r"(\d+)\s*(h|m|s)", text)
    if comp:
        total = 0
        for n, u in comp:
            if u == "h":
                total += int(n) * 3600
            elif u == "m":
                total += int(n) * 60
            else:
                total += int(n)
        return total if total > 0 else None

    # Try verbose format: "1 hour 30 minutes"
    total = 0
    hour_match = re.search(r"(\d+)\s*(?:hour|hours|hr|hrs)", text)
    min_match = re.search(r"(\d+)\s*(?:minute|minutes|min|mins)", text)
    sec_match = re.search(r"(\d+)\s*(?:second|seconds|sec|secs)", text)

    if hour_match:
        total += int(hour_match.group(1)) * 3600
    if min_match:
        total += int(min_match.group(1)) * 60
    if sec_match:
        total += int(sec_match.group(1))

    return total if total > 0 else None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_fire_time(value: str) -> Optional[datetime]:
    raw = value.strip()
    if not raw:
        return None

    lowered = raw.lower()
    match = re.match(
        r"in\s+(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs|day|days)",
        lowered,
    )
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit.startswith("min"):
            delta = timedelta(minutes=amount)
        elif unit.startswith("hour") or unit.startswith("hr"):
            delta = timedelta(hours=amount)
        else:
            delta = timedelta(days=amount)
        return _utc_now() + delta

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@llm.function_tool
async def add_alarm(title: str, fire_at: str, message: str = "") -> str:
    """Schedule an alarm using ISO time or 'in X minutes/hours/days'."""
    title = title.strip()
    if not title:
        return "Alarm title is required."

    fire_time = _parse_fire_time(fire_at)
    if fire_time is None:
        return "Could not parse time. Use ISO 8601 or 'in 10 minutes'."

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO alarms (title, fire_at, message, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (title, _format_iso(fire_time), message.strip() or None),
        )
        conn.commit()

    return f"Alarm set for {_format_iso(fire_time)}: {title}"


@llm.function_tool
async def list_alarms(status: str = "pending", limit: int = 10) -> str:
    """List alarms by status (pending, triggered, cancelled, all)."""
    status = status.strip().lower() or "pending"
    if status not in {"pending", "triggered", "cancelled", "all"}:
        status = "pending"

    limit = max(1, min(100, limit))
    sql = "SELECT id, title, fire_at, status FROM alarms"
    params: list[object] = []
    if status != "all":
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY fire_at ASC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    if not rows:
        return "No alarms found."

    lines = [
        f"{row['id']}: {row['title']} at {row['fire_at']} [{row['status']}]"
        for row in rows
    ]
    return "Alarms:\n" + "\n".join(lines)


@llm.function_tool
async def cancel_alarm(alarm_id: int) -> str:
    """Cancel an alarm."""
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE alarms SET status = 'cancelled' WHERE id = ? AND status = 'pending'",
            (alarm_id,),
        )
        conn.commit()

    if cur.rowcount:
        return f"Cancelled alarm {alarm_id}."
    return f"Alarm {alarm_id} not found or already handled."


# ============================================================================
# Quick Timers (in-memory, for short durations)
# ============================================================================


def _format_duration(seconds: int) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        result = f"{mins} minute{'s' if mins != 1 else ''}"
        if secs > 0:
            result += f" {secs} second{'s' if secs != 1 else ''}"
        return result
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        result = f"{hours} hour{'s' if hours != 1 else ''}"
        if mins > 0:
            result += f" {mins} minute{'s' if mins != 1 else ''}"
        return result


@llm.function_tool
async def set_timer(duration: str, label: str = "") -> str:
    """
    Set a quick timer. Supports natural language durations.

    Args:
        duration: Duration like '5 minutes', '30 seconds', '2m30s', 'five minutes', 'half an hour'
        label: Optional label for the timer (e.g., 'pasta', 'eggs')

    Examples:
        set_timer("5 minutes", "eggs")
        set_timer("2m30s", "tea")
        set_timer("ten seconds")
        set_timer("half an hour", "meeting")
    """
    seconds = _parse_duration(duration)
    if seconds is None or seconds <= 0:
        return "Could not parse duration. Try '5 minutes', '30 seconds', '2m30s', or 'five minutes'."

    timer_id = str(uuid.uuid4())[:8]
    label_text = f" ({label})" if label else ""

    if label:
        _TIMER_LABELS[timer_id] = label

    async def _timer_task(tid: str, secs: int, lbl: str):
        try:
            await asyncio.sleep(secs)
            message = f"Timer{f' for {lbl}' if lbl else ''} finished!"

            # Use callback if available (for voice notification)
            if _timer_callback:
                try:
                    await _timer_callback(message)
                except Exception as e:
                    logger.error("Timer callback failed: %s", e)
            else:
                logger.info(message)
        finally:
            _ACTIVE_TIMERS.pop(tid, None)
            _TIMER_LABELS.pop(tid, None)

    task = asyncio.create_task(_timer_task(timer_id, seconds, label))
    _ACTIVE_TIMERS[timer_id] = task

    return f"Timer set for {_format_duration(seconds)}{label_text}. Timer ID: {timer_id}"


@llm.function_tool
async def cancel_timer(timer_id: str = "", label: str = "") -> str:
    """
    Cancel a running timer by ID or label.

    Args:
        timer_id: Timer ID returned by set_timer
        label: Timer label (if no ID provided)
    """
    if not _ACTIVE_TIMERS:
        return "There are no active timers."

    # Resolve by label if no ID provided
    if label and not timer_id:
        for tid, lab in list(_TIMER_LABELS.items()):
            if lab and lab.lower() == label.lower():
                timer_id = tid
                break

    if not timer_id or timer_id not in _ACTIVE_TIMERS:
        return "Timer not found. Use list_timers to see active timers."

    task = _ACTIVE_TIMERS.pop(timer_id)
    task.cancel()
    _TIMER_LABELS.pop(timer_id, None)
    return f"Timer {timer_id} cancelled."


@llm.function_tool
async def list_timers() -> str:
    """List all active quick timers."""
    if not _ACTIVE_TIMERS:
        return "No active timers."

    lines = []
    for tid in _ACTIVE_TIMERS.keys():
        label = _TIMER_LABELS.get(tid)
        if label:
            lines.append(f"- {tid}: {label}")
        else:
            lines.append(f"- {tid}")

    return "Active timers:\n" + "\n".join(lines)


def set_timer_callback(callback: Callable[[str], Awaitable[None]]) -> None:
    """Set the callback for timer notifications."""
    global _timer_callback
    _timer_callback = callback


async def _alarm_scheduler() -> None:
    while True:
        due = []
        now = _format_iso(_utc_now())
        with get_connection() as conn:
            due = conn.execute(
                """
                SELECT id, title, message
                FROM alarms
                WHERE status = 'pending' AND fire_at <= ?
                ORDER BY fire_at ASC
                """,
                (now,),
            ).fetchall()

            if due:
                conn.executemany(
                    """
                    UPDATE alarms
                    SET status = 'triggered', triggered_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    [(row["id"],) for row in due],
                )
                conn.commit()

        if due and _alarm_callback:
            for row in due:
                message = row["message"] or row["title"]
                try:
                    await _alarm_callback(f"Alarm: {message}")
                except Exception as exc:
                    logger.error("Alarm callback failed: %s", exc)

        await asyncio.sleep(5)


def start_alarm_scheduler(callback: Callable[[str], Awaitable[None]]) -> asyncio.Task:
    """Start the background alarm scheduler."""
    global _scheduler_task, _alarm_callback
    _alarm_callback = callback

    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_alarm_scheduler())

    return _scheduler_task


def stop_alarm_scheduler() -> None:
    """Stop the background alarm scheduler."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
    _scheduler_task = None


def get_alarm_tools() -> list:
    """Get alarm and timer tools."""
    return [
        # Scheduled alarms (database-backed)
        add_alarm,
        list_alarms,
        cancel_alarm,
        # Quick timers (in-memory)
        set_timer,
        cancel_timer,
        list_timers,
    ]
