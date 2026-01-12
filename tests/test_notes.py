"""Tests for notes tools."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_add_note():
    """Test adding a note."""
    from jarvis.tools.notes import add_note

    result = await add_note("Test Title", "Test content here")
    assert "saved" in result.lower()
    assert "Test Title" in result


@pytest.mark.asyncio
async def test_add_note_strips_whitespace():
    """Test that note content is stripped."""
    from jarvis.tools.notes import add_note, list_notes

    await add_note("  Spaced Title  ", "  Content with spaces  ")

    result = await list_notes()
    assert "Spaced Title" in result
    assert "Content with spaces" in result


@pytest.mark.asyncio
async def test_list_notes_empty():
    """Test listing notes when none exist."""
    from jarvis.tools.notes import list_notes

    result = await list_notes()
    assert "no notes" in result.lower()


@pytest.mark.asyncio
async def test_list_notes():
    """Test listing notes."""
    from jarvis.tools.notes import add_note, list_notes

    await add_note("Note 1", "Content 1")
    await add_note("Note 2", "Content 2")
    await add_note("Note 3", "Content 3")

    result = await list_notes()
    assert "Note 1" in result
    assert "Note 2" in result
    assert "Note 3" in result


@pytest.mark.asyncio
async def test_list_notes_limit():
    """Test that list_notes respects limit."""
    from jarvis.tools.notes import add_note, list_notes

    for i in range(10):
        await add_note(f"Note {i}", f"Content {i}")

    result = await list_notes(limit=3)
    # Count lines that start with a number (note entries like "1: Note 0 - Content 0")
    lines = [l for l in result.split("\n") if l.strip() and l.strip()[0].isdigit()]
    assert len(lines) == 3


@pytest.mark.asyncio
async def test_list_notes_limit_clamped():
    """Test that limit is clamped to valid range."""
    from jarvis.tools.notes import add_note, list_notes

    await add_note("Test", "Content")

    # Limit too low
    result1 = await list_notes(limit=0)
    assert "Test" in result1

    # Limit too high (should work, just capped)
    result2 = await list_notes(limit=100)
    assert "Test" in result2


@pytest.mark.asyncio
async def test_list_notes_truncates_long_content():
    """Test that long content is truncated in listing."""
    from jarvis.tools.notes import add_note, list_notes

    long_content = "A" * 200
    await add_note("Long Note", long_content)

    result = await list_notes()
    assert "..." in result
    assert "A" * 200 not in result


@pytest.mark.asyncio
async def test_delete_note():
    """Test deleting a note."""
    from jarvis.tools.notes import add_note, delete_note, list_notes
    from jarvis.storage import get_connection

    await add_note("To Delete", "Delete me")

    with get_connection() as conn:
        row = conn.execute("SELECT id FROM notes LIMIT 1").fetchone()
        note_id = row["id"]

    result = await delete_note(note_id)
    assert "deleted" in result.lower()

    list_result = await list_notes()
    assert "no notes" in list_result.lower()


@pytest.mark.asyncio
async def test_delete_note_not_found():
    """Test deleting a non-existent note."""
    from jarvis.tools.notes import delete_note

    result = await delete_note(99999)
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_get_note_tools():
    """Test that get_note_tools returns all tools."""
    from jarvis.tools.notes import get_note_tools

    tools = get_note_tools()
    tool_names = [t.__name__ for t in tools]

    assert "add_note" in tool_names
    assert "list_notes" in tool_names
    assert "delete_note" in tool_names
