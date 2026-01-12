"""Tests for memory tools."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_remember_basic():
    """Test basic memory storage."""
    from jarvis.tools.memory import remember

    result = await remember("User likes Python")
    assert "saved" in result.lower()


@pytest.mark.asyncio
async def test_remember_with_tags():
    """Test memory storage with tags."""
    from jarvis.tools.memory import remember

    result = await remember("User prefers VSCode", tags="preferences,tools", importance=3)
    assert "saved" in result.lower()


@pytest.mark.asyncio
async def test_remember_importance_clamped():
    """Test that importance is clamped to valid range."""
    from jarvis.tools.memory import remember, recall_memory

    # Test clamping to max 5
    await remember("High importance", importance=10)
    # Test clamping to min 1
    await remember("Low importance", importance=-5)

    result = await recall_memory()
    assert "High importance" in result
    assert "Low importance" in result


@pytest.mark.asyncio
async def test_recall_memory_empty():
    """Test recalling from empty memory."""
    from jarvis.tools.memory import recall_memory

    result = await recall_memory()
    assert "no matching" in result.lower()


@pytest.mark.asyncio
async def test_recall_memory_with_query():
    """Test recalling memory with search query."""
    from jarvis.tools.memory import remember, recall_memory

    await remember("User likes Python programming")
    await remember("User dislikes Java")

    result = await recall_memory(query="Python")
    assert "Python" in result
    assert "Java" not in result


@pytest.mark.asyncio
async def test_recall_memory_with_tags():
    """Test recalling memory by tags."""
    from jarvis.tools.memory import remember, recall_memory

    await remember("Coffee preference: black", tags="food")
    await remember("Favorite IDE: VSCode", tags="tools")

    result = await recall_memory(tags="food")
    assert "Coffee" in result
    assert "IDE" not in result


@pytest.mark.asyncio
async def test_recall_memory_limit():
    """Test recall memory respects limit."""
    from jarvis.tools.memory import remember, recall_memory

    for i in range(10):
        await remember(f"Memory item {i}")

    result = await recall_memory(limit=3)
    # Should only have 3 items (plus header)
    lines = [l for l in result.split("\n") if l.strip()]
    assert len(lines) <= 4  # Header + 3 items


@pytest.mark.asyncio
async def test_forget_memory():
    """Test deleting a memory by ID."""
    from jarvis.tools.memory import remember, recall_memory, forget_memory
    from jarvis.storage import get_connection

    await remember("Test memory to delete")

    # Get the ID
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM memory LIMIT 1").fetchone()
        memory_id = row["id"]

    result = await forget_memory(memory_id)
    assert "deleted" in result.lower()

    # Verify it's gone
    recall_result = await recall_memory()
    assert "no matching" in recall_result.lower()


@pytest.mark.asyncio
async def test_forget_memory_not_found():
    """Test deleting a non-existent memory."""
    from jarvis.tools.memory import forget_memory

    result = await forget_memory(99999)
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_forget_memory_by_tag():
    """Test deleting memories by tag."""
    from jarvis.tools.memory import remember, recall_memory, forget_memory_by_tag

    await remember("Work memory 1", tags="work")
    await remember("Work memory 2", tags="work")
    await remember("Personal memory", tags="personal")

    result = await forget_memory_by_tag("work")
    assert "deleted" in result.lower()
    assert "2" in result  # Should delete 2 memories

    # Verify only personal remains
    recall_result = await recall_memory()
    assert "Personal" in recall_result
    assert "Work" not in recall_result


@pytest.mark.asyncio
async def test_forget_memory_by_tag_empty():
    """Test that empty tag returns error."""
    from jarvis.tools.memory import forget_memory_by_tag

    result = await forget_memory_by_tag("")
    assert "required" in result.lower()


@pytest.mark.asyncio
async def test_forget_memory_before():
    """Test deleting old memories."""
    from jarvis.tools.memory import remember, forget_memory_before

    await remember("Recent memory")

    # Try to delete memories older than 30 days (none should be deleted)
    result = await forget_memory_before(30)
    assert "no memories" in result.lower() or "0" in result


@pytest.mark.asyncio
async def test_memory_stats_empty():
    """Test memory stats on empty database."""
    from jarvis.tools.memory import memory_stats

    result = await memory_stats()
    assert "no memories" in result.lower()


@pytest.mark.asyncio
async def test_memory_stats():
    """Test memory statistics."""
    from jarvis.tools.memory import remember, memory_stats

    await remember("Item 1", tags="work")
    await remember("Item 2", tags="work")
    await remember("Item 3", tags="personal")

    result = await memory_stats()
    assert "total memories: 3" in result.lower()
    assert "work" in result.lower()


@pytest.mark.asyncio
async def test_get_memory_tools():
    """Test that get_memory_tools returns all tools."""
    from jarvis.tools.memory import get_memory_tools

    tools = get_memory_tools()
    tool_names = [t.__name__ for t in tools]

    assert "remember" in tool_names
    assert "recall_memory" in tool_names
    assert "forget_memory" in tool_names
    assert "forget_memory_by_tag" in tool_names
    assert "forget_memory_before" in tool_names
    assert "memory_stats" in tool_names
