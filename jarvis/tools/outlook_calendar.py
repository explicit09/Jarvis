"""Outlook calendar tools powered by Microsoft Graph."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from livekit.agents import llm

from jarvis.config import config
from jarvis.integrations.outlook import (
    GRAPH_BASE_URL,
    acquire_access_token,
    default_window,
    graph_delete,
    graph_get,
    graph_post,
)


def _calendar_events_url() -> str:
    if config.outlook.calendar_id:
        return f"{GRAPH_BASE_URL}/me/calendars/{config.outlook.calendar_id}/events"
    return f"{GRAPH_BASE_URL}/me/events"


def _calendar_view_url() -> str:
    if config.outlook.calendar_id:
        return f"{GRAPH_BASE_URL}/me/calendars/{config.outlook.calendar_id}/calendarView"
    return f"{GRAPH_BASE_URL}/me/calendarView"


def _parse_or_default_start_end(start_time: str, end_time: str) -> tuple[str, str]:
    start_time = start_time.strip()
    end_time = end_time.strip()

    if start_time and end_time:
        return start_time, end_time

    return default_window()


def _timezone_name() -> str:
    return config.calendar.timezone if config.calendar.timezone != "local" else "UTC"


@llm.function_tool
async def outlook_list_events(
    start_time: str = "",
    end_time: str = "",
    limit: int = 10,
) -> str:
    """List upcoming Outlook calendar events."""
    token, error = acquire_access_token()
    if not token:
        return error

    start_time, end_time = _parse_or_default_start_end(start_time, end_time)
    limit = max(1, min(50, limit))

    params = {
        "startDateTime": start_time,
        "endDateTime": end_time,
        "$top": str(limit),
        "$orderby": "start/dateTime",
    }

    data = await graph_get(_calendar_view_url(), token, params=params)
    events = data.get("value", [])
    if not events:
        return "No Outlook events found."

    lines = []
    for event in events:
        subject = event.get("subject", "No title")
        start = event.get("start", {}).get("dateTime", "?")
        end = event.get("end", {}).get("dateTime", "")
        location = event.get("location", {}).get("displayName", "")
        line = f"{event.get('id')}: {subject} ({start} - {end})"
        if location:
            line += f" @ {location}"
        lines.append(line)

    return "Outlook events:\n" + "\n".join(lines)


@llm.function_tool
async def outlook_create_event(
    title: str,
    start_time: str,
    end_time: str = "",
    location: str = "",
    body: str = "",
) -> str:
    """Create an Outlook calendar event."""
    token, error = acquire_access_token()
    if not token:
        return error

    if not end_time.strip():
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except ValueError:
            start_dt = datetime.now(timezone.utc)
        end_dt = start_dt + timedelta(minutes=30)
        end_time = end_dt.isoformat(timespec="seconds").replace("+00:00", "Z")

    payload = {
        "subject": title.strip(),
        "start": {"dateTime": start_time.strip(), "timeZone": _timezone_name()},
        "end": {"dateTime": end_time.strip(), "timeZone": _timezone_name()},
    }

    if location.strip():
        payload["location"] = {"displayName": location.strip()}
    if body.strip():
        payload["body"] = {"contentType": "Text", "content": body.strip()}

    event = await graph_post(_calendar_events_url(), token, payload)
    return f"Created Outlook event: {event.get('subject', title)}"


@llm.function_tool
async def outlook_delete_event(event_id: str) -> str:
    """Delete an Outlook calendar event by ID."""
    token, error = acquire_access_token()
    if not token:
        return error

    await graph_delete(f"{GRAPH_BASE_URL}/me/events/{event_id}", token)
    return f"Deleted Outlook event {event_id}."


def get_outlook_tools() -> list:
    """Get Outlook calendar tools."""
    return [outlook_list_events, outlook_create_event, outlook_delete_event]
