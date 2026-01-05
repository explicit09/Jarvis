"""Memory tools for J.A.R.V.I.S."""

from __future__ import annotations

from livekit.agents import llm

from jarvis.storage import get_connection


@llm.function_tool
async def remember(content: str, tags: str = "", importance: int = 1) -> str:
    """Store a memory for later recall."""
    importance = max(1, min(5, importance))

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO memory (content, tags, importance) VALUES (?, ?, ?)",
            (content.strip(), tags.strip(), importance),
        )
        conn.commit()

    return "Saved that to memory."


@llm.function_tool
async def recall_memory(query: str = "", tags: str = "", limit: int = 5) -> str:
    """Recall memories that match a query or tags."""
    limit = max(1, min(20, limit))
    query = query.strip()
    tags = tags.strip()

    sql = "SELECT id, content, tags, importance, created_at FROM memory WHERE 1=1"
    params: list[object] = []

    if query:
        sql += " AND content LIKE ?"
        params.append(f"%{query}%")
    if tags:
        sql += " AND tags LIKE ?"
        params.append(f"%{tags}%")

    sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    if not rows:
        return "No matching memories found."

    lines = []
    for row in rows:
        tag_text = f" (tags: {row['tags']})" if row["tags"] else ""
        lines.append(f"{row['id']}: {row['content']}{tag_text}")

    return "Memories:\n" + "\n".join(lines)


@llm.function_tool
async def forget_memory(memory_id: int) -> str:
    """Delete a memory by ID."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM memory WHERE id = ?", (memory_id,))
        conn.commit()

    if cur.rowcount:
        return f"Deleted memory {memory_id}."
    return f"Memory {memory_id} not found."


@llm.function_tool
async def forget_memory_by_tag(tag: str) -> str:
    """Delete memories matching a tag."""
    tag = tag.strip()
    if not tag:
        return "Tag is required."

    with get_connection() as conn:
        cur = conn.execute("DELETE FROM memory WHERE tags LIKE ?", (f"%{tag}%",))
        conn.commit()

    if cur.rowcount:
        return f"Deleted {cur.rowcount} memories tagged with '{tag}'."
    return f"No memories found with tag '{tag}'."


@llm.function_tool
async def forget_memory_before(days: int = 30) -> str:
    """Delete memories older than N days."""
    days = max(1, min(3650, days))
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM memory WHERE created_at < datetime('now', ?)",
            (f"-{days} days",),
        )
        conn.commit()

    if cur.rowcount:
        return f"Deleted {cur.rowcount} memories older than {days} days."
    return f"No memories older than {days} days."


@llm.function_tool
async def memory_stats(limit: int = 5) -> str:
    """Get memory stats and top tags."""
    limit = max(1, min(20, limit))
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) AS count FROM memory").fetchone()["count"]
        rows = conn.execute(
            """
            SELECT tags, COUNT(*) AS count
            FROM memory
            WHERE tags IS NOT NULL AND tags != ''
            GROUP BY tags
            ORDER BY count DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    if total == 0:
        return "No memories stored yet."

    tag_lines = []
    for row in rows:
        tag_lines.append(f"{row['tags']}: {row['count']}")

    summary = [f"Total memories: {total}"]
    if tag_lines:
        summary.append("Top tags: " + ", ".join(tag_lines))
    return "\n".join(summary)


def get_memory_tools() -> list:
    """Get memory tools."""
    return [
        remember,
        recall_memory,
        forget_memory,
        forget_memory_by_tag,
        forget_memory_before,
        memory_stats,
    ]
