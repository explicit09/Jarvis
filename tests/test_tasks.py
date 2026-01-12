"""Tests for task management tools."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_add_task():
    """Test adding a task."""
    from jarvis.tools.tasks import add_task

    result = await add_task("Review pull request")
    assert "added" in result.lower()
    assert "Review pull request" in result


@pytest.mark.asyncio
async def test_add_task_with_due_date():
    """Test adding a task with due date."""
    from jarvis.tools.tasks import add_task, list_tasks

    await add_task("Submit report", due_date="2025-01-15")

    result = await list_tasks()
    assert "Submit report" in result
    assert "2025-01-15" in result


@pytest.mark.asyncio
async def test_add_task_with_priority():
    """Test adding a task with priority."""
    from jarvis.tools.tasks import add_task, list_tasks

    await add_task("Urgent task", priority="high")

    result = await list_tasks()
    assert "Urgent task" in result
    assert "high" in result


@pytest.mark.asyncio
async def test_list_tasks_empty():
    """Test listing tasks when none exist."""
    from jarvis.tools.tasks import list_tasks

    result = await list_tasks()
    assert "no tasks" in result.lower()


@pytest.mark.asyncio
async def test_list_tasks_open():
    """Test listing open tasks."""
    from jarvis.tools.tasks import add_task, list_tasks

    await add_task("Task 1")
    await add_task("Task 2")

    result = await list_tasks(status="open")
    assert "Task 1" in result
    assert "Task 2" in result


@pytest.mark.asyncio
async def test_list_tasks_completed():
    """Test listing completed tasks."""
    from jarvis.tools.tasks import add_task, complete_task, list_tasks
    from jarvis.storage import get_connection

    await add_task("Task to complete")

    with get_connection() as conn:
        row = conn.execute("SELECT id FROM tasks LIMIT 1").fetchone()
        task_id = row["id"]

    await complete_task(task_id)

    open_result = await list_tasks(status="open")
    assert "no tasks" in open_result.lower()

    completed_result = await list_tasks(status="completed")
    assert "Task to complete" in completed_result


@pytest.mark.asyncio
async def test_list_tasks_all():
    """Test listing all tasks."""
    from jarvis.tools.tasks import add_task, complete_task, list_tasks
    from jarvis.storage import get_connection

    await add_task("Open task")
    await add_task("Completed task")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM tasks WHERE content = 'Completed task'"
        ).fetchone()
        task_id = row["id"]

    await complete_task(task_id)

    result = await list_tasks(status="all")
    assert "Open task" in result
    assert "Completed task" in result


@pytest.mark.asyncio
async def test_list_tasks_invalid_status():
    """Test that invalid status defaults to open."""
    from jarvis.tools.tasks import add_task, list_tasks

    await add_task("Test task")

    result = await list_tasks(status="invalid")
    assert "Test task" in result


@pytest.mark.asyncio
async def test_list_tasks_limit():
    """Test that list_tasks respects limit."""
    from jarvis.tools.tasks import add_task, list_tasks

    for i in range(10):
        await add_task(f"Task {i}")

    result = await list_tasks(limit=3)
    # Count lines that start with a number (task entries like "1: Task 0 [open, normal]")
    lines = [l for l in result.split("\n") if l.strip() and l.strip()[0].isdigit()]
    assert len(lines) == 3


@pytest.mark.asyncio
async def test_complete_task():
    """Test marking a task as completed."""
    from jarvis.tools.tasks import add_task, complete_task
    from jarvis.storage import get_connection

    await add_task("Task to complete")

    with get_connection() as conn:
        row = conn.execute("SELECT id FROM tasks LIMIT 1").fetchone()
        task_id = row["id"]

    result = await complete_task(task_id)
    assert "completed" in result.lower()

    with get_connection() as conn:
        row = conn.execute(
            "SELECT status, completed_at FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()
        assert row["status"] == "completed"
        assert row["completed_at"] is not None


@pytest.mark.asyncio
async def test_complete_task_not_found():
    """Test completing a non-existent task."""
    from jarvis.tools.tasks import complete_task

    result = await complete_task(99999)
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_delete_task():
    """Test deleting a task."""
    from jarvis.tools.tasks import add_task, delete_task, list_tasks
    from jarvis.storage import get_connection

    await add_task("Task to delete")

    with get_connection() as conn:
        row = conn.execute("SELECT id FROM tasks LIMIT 1").fetchone()
        task_id = row["id"]

    result = await delete_task(task_id)
    assert "deleted" in result.lower()

    list_result = await list_tasks()
    assert "no tasks" in list_result.lower()


@pytest.mark.asyncio
async def test_delete_task_not_found():
    """Test deleting a non-existent task."""
    from jarvis.tools.tasks import delete_task

    result = await delete_task(99999)
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_get_task_tools():
    """Test that get_task_tools returns all tools."""
    from jarvis.tools.tasks import get_task_tools

    tools = get_task_tools()
    tool_names = [t.__name__ for t in tools]

    assert "add_task" in tool_names
    assert "list_tasks" in tool_names
    assert "complete_task" in tool_names
    assert "delete_task" in tool_names
