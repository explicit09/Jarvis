"""Local calendar tools for J.A.R.V.I.S."""

from __future__ import annotations

from livekit.agents import llm

from jarvis.storage import get_connection


@llm.function_tool
async def add_calendar_event(
    title: str,
    start_time: str,
    end_time: str = "",
    location: str = "",
    notes: str = "",
) -> str:
    """Add a calendar event (expects ISO-like datetime strings)."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO calendar_events (title, start_time, end_time, location, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                title.strip(),
                start_time.strip(),
                end_time.strip() or None,
                location.strip() or None,
                notes.strip() or None,
            ),
        )
        conn.commit()

    return f"Event added: {title} at {start_time}"


@llm.function_tool
async def list_calendar_events(
    start_date: str = "",
    end_date: str = "",
    limit: int = 10,
) -> str:
    """List upcoming calendar events."""
    limit = max(1, min(50, limit))
    start_date = start_date.strip()
    end_date = end_date.strip()

    sql = "SELECT id, title, start_time, end_time, location FROM calendar_events"
    params: list[object] = []
    conditions = []

    if start_date:
        conditions.append("start_time >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("start_time <= ?")
        params.append(end_date)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY start_time ASC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    if not rows:
        return "No events found."

    lines = []
    for row in rows:
        end_time = f" - {row['end_time']}" if row["end_time"] else ""
        location = f" @ {row['location']}" if row["location"] else ""
        lines.append(
            f"{row['id']}: {row['title']} ({row['start_time']}{end_time}){location}"
        )

    return "Events:\n" + "\n".join(lines)


@llm.function_tool
async def delete_calendar_event(event_id: int) -> str:
    """Delete a calendar event by ID."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
        conn.commit()

    if cur.rowcount:
        return f"Deleted event {event_id}."
    return f"Event {event_id} not found."


def get_calendar_tools() -> list:
    """Get calendar tools."""
    return [add_calendar_event, list_calendar_events, delete_calendar_event]
