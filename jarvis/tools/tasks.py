"""Task management tools for J.A.R.V.I.S."""

from __future__ import annotations

from datetime import datetime

from livekit.agents import llm

from jarvis.storage import get_connection


@llm.function_tool
async def add_task(content: str, due_date: str = "", priority: str = "normal") -> str:
    """Create a task."""
    priority = priority.strip().lower() or "normal"
    due_date = due_date.strip()

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO tasks (content, due_date, priority) VALUES (?, ?, ?)",
            (content.strip(), due_date or None, priority),
        )
        conn.commit()

    return f"Task added: {content}"


@llm.function_tool
async def list_tasks(status: str = "open", limit: int = 10) -> str:
    """List tasks by status (open or completed)."""
    status = status.strip().lower() or "open"
    if status not in {"open", "completed", "all"}:
        status = "open"
    limit = max(1, min(50, limit))

    sql = "SELECT id, content, due_date, priority, status FROM tasks"
    params: list[object] = []
    if status != "all":
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    if not rows:
        return "No tasks found."

    lines = []
    for row in rows:
        due = f" (due {row['due_date']})" if row["due_date"] else ""
        lines.append(
            f"{row['id']}: {row['content']} [{row['status']}, {row['priority']}] {due}"
        )

    return "Tasks:\n" + "\n".join(lines)


@llm.function_tool
async def complete_task(task_id: int) -> str:
    """Mark a task as completed."""
    completed_at = datetime.utcnow().isoformat()

    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?",
            (completed_at, task_id),
        )
        conn.commit()

    if cur.rowcount:
        return f"Task {task_id} completed."
    return f"Task {task_id} not found."


@llm.function_tool
async def delete_task(task_id: int) -> str:
    """Delete a task by ID."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()

    if cur.rowcount:
        return f"Deleted task {task_id}."
    return f"Task {task_id} not found."


def get_task_tools() -> list:
    """Get task tools."""
    return [add_task, list_tasks, complete_task, delete_task]
