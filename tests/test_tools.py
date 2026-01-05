"""Tests for tools module."""

from __future__ import annotations

import pytest


def test_get_all_tools():
    """Test that all tools are registered."""
    from jarvis.tools import get_all_tools

    tools = get_all_tools()

    # Should have system, web, and extended tools
    assert len(tools) >= 55

    # Check for expected tools
    tool_names = [t.__name__ for t in tools]
    assert "get_current_time" in tool_names
    assert "web_search" in tool_names
    assert "get_weather" in tool_names
    assert "open_application" in tool_names
    assert "remember" in tool_names
    assert "add_note" in tool_names
    assert "add_task" in tool_names
    assert "add_calendar_event" in tool_names
    assert "get_device_state" in tool_names
    assert "read_file" in tool_names
    assert "place_call" in tool_names
    assert "outlook_list_events" in tool_names
    assert "daily_brief" in tool_names
    assert "add_routine" in tool_names
    assert "add_contact" in tool_names
    assert "list_alarms" in tool_names
    assert "play_music" in tool_names
    assert "create_apple_calendar_event" in tool_names
    assert "create_apple_reminder" in tool_names
    assert "send_notification" in tool_names
    assert "analyze_code" in tool_names
    assert "get_project_structure" in tool_names
    assert "count_lines" in tool_names
    assert "find_todos" in tool_names
    assert "diff_files" in tool_names
    assert "github_list_repos" in tool_names
    assert "github_read_file" in tool_names
    assert "run_sandboxed_command" in tool_names


@pytest.mark.asyncio
async def test_get_current_time():
    """Test get_current_time tool."""
    from jarvis.tools.system import get_current_time

    result = await get_current_time()
    assert "current time" in result.lower()


@pytest.mark.asyncio
async def test_get_current_time_timezone():
    """Test get_current_time with timezone."""
    from jarvis.tools.system import get_current_time

    # This will fail without pytz installed, which is fine
    result = await get_current_time(timezone="UTC")
    assert "time" in result.lower()


@pytest.mark.asyncio
async def test_get_system_info():
    """Test get_system_info tool."""
    from jarvis.tools.system import get_system_info

    result = await get_system_info()
    assert "System:" in result
    assert "Python:" in result


@pytest.mark.asyncio
async def test_web_search():
    """Test web_search tool."""
    from jarvis.tools.web import web_search

    result = await web_search("python programming")
    # Should return some result (may be "no results" if API is down)
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_definition():
    """Test get_definition tool."""
    from jarvis.tools.web import get_definition

    result = await get_definition("hello")
    assert isinstance(result, str)
    # Should contain either a definition or "no definition found"
    assert len(result) > 0
