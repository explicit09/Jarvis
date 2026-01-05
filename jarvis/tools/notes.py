"""Notes tools for J.A.R.V.I.S."""

from __future__ import annotations

from livekit.agents import llm

from jarvis.storage import get_connection


@llm.function_tool
async def add_note(title: str, content: str) -> str:
    """Create a note."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO notes (title, content) VALUES (?, ?)",
            (title.strip(), content.strip()),
        )
        conn.commit()

    return f"Note saved: {title}"


@llm.function_tool
async def list_notes(limit: int = 10) -> str:
    """List recent notes."""
    limit = max(1, min(50, limit))
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, content, created_at FROM notes ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    if not rows:
        return "No notes yet."

    lines = []
    for row in rows:
        preview = row["content"]
        if len(preview) > 120:
            preview = preview[:117] + "..."
        lines.append(f"{row['id']}: {row['title']} - {preview}")

    return "Notes:\n" + "\n".join(lines)


@llm.function_tool
async def delete_note(note_id: int) -> str:
    """Delete a note by ID."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()

    if cur.rowcount:
        return f"Deleted note {note_id}."
    return f"Note {note_id} not found."


def get_note_tools() -> list:
    """Get note tools."""
    return [add_note, list_notes, delete_note]
