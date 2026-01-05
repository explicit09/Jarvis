"""Daily briefing tools for J.A.R.V.I.S."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from livekit.agents import llm

from jarvis.config import config
from jarvis.integrations.outlook import (
    GRAPH_BASE_URL,
    acquire_access_token,
    graph_get,
)
from jarvis.storage import get_connection
from jarvis.tools.web import get_weather


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _window_days() -> int:
    return max(1, min(30, config.briefing.brief_days))


def _format_iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


async def _fetch_outlook_events(limit: int = 5) -> list[str]:
    token, error = acquire_access_token()
    if not token:
        return [f"Outlook: {error}"]

    now = _utc_now()
    end = now + timedelta(days=_window_days())

    params = {
        "startDateTime": _format_iso(now),
        "endDateTime": _format_iso(end),
        "$top": str(limit),
        "$orderby": "start/dateTime",
    }

    data = await graph_get(f"{GRAPH_BASE_URL}/me/calendarView", token, params=params)
    events = data.get("value", [])
    if not events:
        return []

    lines = []
    for event in events:
        subject = event.get("subject", "No title")
        start = event.get("start", {}).get("dateTime", "?")
        end_time = event.get("end", {}).get("dateTime", "")
        lines.append(f"{subject} ({start} - {end_time})")
    return lines


def _fetch_local_events(limit: int = 5) -> list[str]:
    now = _utc_now().isoformat(timespec="seconds")
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT title, start_time, end_time, location
            FROM calendar_events
            WHERE start_time >= ?
            ORDER BY start_time ASC
            LIMIT ?
            """,
            (now, limit),
        ).fetchall()

    lines = []
    for row in rows:
        end_time = f" - {row['end_time']}" if row["end_time"] else ""
        location = f" @ {row['location']}" if row["location"] else ""
        lines.append(f"{row['title']} ({row['start_time']}{end_time}){location}")
    return lines


def _fetch_tasks(limit: int = 5) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT content, due_date, priority
            FROM tasks
            WHERE status = 'open'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    lines = []
    for row in rows:
        due = f" (due {row['due_date']})" if row["due_date"] else ""
        lines.append(f"{row['content']} [{row['priority']}] {due}")
    return lines


@llm.function_tool
async def daily_brief(
    city: str = "",
    include_weather: bool = True,
    include_tasks: bool = True,
    include_local_calendar: bool = True,
    include_outlook: bool = True,
) -> str:
    """Get a daily briefing summary."""
    lines = []

    if include_weather:
        weather_city = city.strip() or config.briefing.weather_city
        if weather_city:
            lines.append(await get_weather(weather_city))
        else:
            lines.append("Weather: set JARVIS_WEATHER_CITY or pass a city.")

    if include_tasks:
        tasks = _fetch_tasks()
        if tasks:
            lines.append("Tasks: " + "; ".join(tasks))
        else:
            lines.append("Tasks: none due.")

    if include_local_calendar:
        events = _fetch_local_events()
        if events:
            lines.append("Local calendar: " + "; ".join(events))

    if include_outlook:
        outlook_events = await _fetch_outlook_events()
        if outlook_events:
            lines.append("Outlook: " + "; ".join(outlook_events))

    if not lines:
        return "Nothing on the radar yet."
    return "\n".join(lines)


def get_briefing_tools() -> list:
    """Get briefing tools."""
    return [daily_brief]
