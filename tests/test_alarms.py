"""Tests for alarm and timer tools."""

from __future__ import annotations

import pytest


class TestDurationParsing:
    """Tests for duration parsing."""

    def test_parse_duration_seconds(self):
        """Test parsing seconds."""
        from jarvis.tools.alarms import _parse_duration

        assert _parse_duration("10") == 10
        assert _parse_duration("10s") == 10
        assert _parse_duration("10 seconds") == 10
        assert _parse_duration("30sec") == 30

    def test_parse_duration_minutes(self):
        """Test parsing minutes."""
        from jarvis.tools.alarms import _parse_duration

        assert _parse_duration("5m") == 300
        assert _parse_duration("5 minutes") == 300
        assert _parse_duration("5min") == 300
        assert _parse_duration("1 minute") == 60

    def test_parse_duration_hours(self):
        """Test parsing hours."""
        from jarvis.tools.alarms import _parse_duration

        assert _parse_duration("1h") == 3600
        assert _parse_duration("1 hour") == 3600
        assert _parse_duration("2 hours") == 7200

    def test_parse_duration_word_numbers(self):
        """Test parsing word numbers."""
        from jarvis.tools.alarms import _parse_duration

        assert _parse_duration("five minutes") == 300
        assert _parse_duration("ten seconds") == 10
        assert _parse_duration("one hour") == 3600

    def test_parse_duration_composite(self):
        """Test parsing composite durations."""
        from jarvis.tools.alarms import _parse_duration

        assert _parse_duration("2m30s") == 150
        assert _parse_duration("1h30m") == 5400
        assert _parse_duration("1 hour 30 minutes") == 5400
        assert _parse_duration("2 minutes 30 seconds") == 150

    def test_parse_duration_half(self):
        """Test parsing 'half' durations."""
        from jarvis.tools.alarms import _parse_duration

        assert _parse_duration("half a minute") == 30
        assert _parse_duration("half an hour") == 1800

    def test_parse_duration_invalid(self):
        """Test parsing invalid durations."""
        from jarvis.tools.alarms import _parse_duration

        assert _parse_duration("") is None
        assert _parse_duration("invalid") is None
        assert _parse_duration("abc def") is None


class TestAlarms:
    """Tests for alarm functionality."""

    @pytest.mark.asyncio
    async def test_add_alarm_relative(self):
        """Test adding alarm with relative time."""
        from jarvis.tools.alarms import add_alarm

        result = await add_alarm("Test Alarm", "in 10 minutes")
        assert "alarm set" in result.lower()
        assert "Test Alarm" in result

    @pytest.mark.asyncio
    async def test_add_alarm_iso_time(self):
        """Test adding alarm with ISO time."""
        from jarvis.tools.alarms import add_alarm

        result = await add_alarm("Meeting", "2025-12-31T10:00:00Z")
        assert "alarm set" in result.lower()

    @pytest.mark.asyncio
    async def test_add_alarm_invalid_time(self):
        """Test adding alarm with invalid time."""
        from jarvis.tools.alarms import add_alarm

        result = await add_alarm("Test", "invalid time")
        assert "could not parse" in result.lower()

    @pytest.mark.asyncio
    async def test_add_alarm_empty_title(self):
        """Test adding alarm without title."""
        from jarvis.tools.alarms import add_alarm

        result = await add_alarm("", "in 10 minutes")
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_list_alarms_empty(self):
        """Test listing alarms when none exist."""
        from jarvis.tools.alarms import list_alarms

        result = await list_alarms()
        assert "no alarms" in result.lower()

    @pytest.mark.asyncio
    async def test_list_alarms(self):
        """Test listing alarms."""
        from jarvis.tools.alarms import add_alarm, list_alarms

        await add_alarm("Alarm 1", "in 10 minutes")
        await add_alarm("Alarm 2", "in 20 minutes")

        result = await list_alarms()
        assert "Alarm 1" in result
        assert "Alarm 2" in result

    @pytest.mark.asyncio
    async def test_list_alarms_by_status(self):
        """Test listing alarms by status."""
        from jarvis.tools.alarms import add_alarm, cancel_alarm, list_alarms
        from jarvis.storage import get_connection

        await add_alarm("Pending Alarm", "in 10 minutes")
        await add_alarm("Cancelled Alarm", "in 20 minutes")

        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM alarms WHERE title = 'Cancelled Alarm'"
            ).fetchone()
            alarm_id = row["id"]

        await cancel_alarm(alarm_id)

        pending_result = await list_alarms(status="pending")
        assert "Pending Alarm" in pending_result
        assert "Cancelled Alarm" not in pending_result

        cancelled_result = await list_alarms(status="cancelled")
        assert "Cancelled Alarm" in cancelled_result
        assert "Pending Alarm" not in cancelled_result

    @pytest.mark.asyncio
    async def test_cancel_alarm(self):
        """Test cancelling an alarm."""
        from jarvis.tools.alarms import add_alarm, cancel_alarm, list_alarms
        from jarvis.storage import get_connection

        await add_alarm("To Cancel", "in 10 minutes")

        with get_connection() as conn:
            row = conn.execute("SELECT id FROM alarms LIMIT 1").fetchone()
            alarm_id = row["id"]

        result = await cancel_alarm(alarm_id)
        assert "cancelled" in result.lower()

        list_result = await list_alarms(status="pending")
        assert "no alarms" in list_result.lower()

    @pytest.mark.asyncio
    async def test_cancel_alarm_not_found(self):
        """Test cancelling a non-existent alarm."""
        from jarvis.tools.alarms import cancel_alarm

        result = await cancel_alarm(99999)
        assert "not found" in result.lower()


class TestTimers:
    """Tests for timer functionality."""

    @pytest.mark.asyncio
    async def test_set_timer(self):
        """Test setting a timer."""
        from jarvis.tools.alarms import set_timer, cancel_timer, _ACTIVE_TIMERS

        result = await set_timer("5 seconds")
        assert "timer set" in result.lower()
        assert "5 second" in result.lower()

        # Extract timer ID and cancel it to clean up
        timer_id = result.split("Timer ID: ")[1].strip()
        await cancel_timer(timer_id=timer_id)

    @pytest.mark.asyncio
    async def test_set_timer_with_label(self):
        """Test setting a timer with label."""
        from jarvis.tools.alarms import set_timer, cancel_timer

        result = await set_timer("5 seconds", label="eggs")
        assert "timer set" in result.lower()
        assert "eggs" in result

        timer_id = result.split("Timer ID: ")[1].strip()
        await cancel_timer(timer_id=timer_id)

    @pytest.mark.asyncio
    async def test_set_timer_invalid_duration(self):
        """Test setting timer with invalid duration."""
        from jarvis.tools.alarms import set_timer

        result = await set_timer("invalid")
        assert "could not parse" in result.lower()

    @pytest.mark.asyncio
    async def test_cancel_timer_by_id(self):
        """Test cancelling timer by ID."""
        from jarvis.tools.alarms import set_timer, cancel_timer

        result = await set_timer("30 seconds")
        timer_id = result.split("Timer ID: ")[1].strip()

        cancel_result = await cancel_timer(timer_id=timer_id)
        assert "cancelled" in cancel_result.lower()

    @pytest.mark.asyncio
    async def test_cancel_timer_by_label(self):
        """Test cancelling timer by label."""
        from jarvis.tools.alarms import set_timer, cancel_timer

        await set_timer("30 seconds", label="pasta")

        cancel_result = await cancel_timer(label="pasta")
        assert "cancelled" in cancel_result.lower()

    @pytest.mark.asyncio
    async def test_cancel_timer_not_found(self):
        """Test cancelling a non-existent timer."""
        from jarvis.tools.alarms import cancel_timer, _ACTIVE_TIMERS

        # Clear any existing timers
        _ACTIVE_TIMERS.clear()

        result = await cancel_timer(timer_id="nonexistent")
        assert "no active timers" in result.lower() or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_list_timers_empty(self):
        """Test listing timers when none active."""
        from jarvis.tools.alarms import list_timers, _ACTIVE_TIMERS

        _ACTIVE_TIMERS.clear()

        result = await list_timers()
        assert "no active" in result.lower()

    @pytest.mark.asyncio
    async def test_list_timers(self):
        """Test listing active timers."""
        from jarvis.tools.alarms import set_timer, list_timers, cancel_timer

        result1 = await set_timer("30 seconds", label="timer1")
        result2 = await set_timer("60 seconds", label="timer2")

        list_result = await list_timers()
        assert "timer1" in list_result
        assert "timer2" in list_result

        # Clean up
        timer_id1 = result1.split("Timer ID: ")[1].strip()
        timer_id2 = result2.split("Timer ID: ")[1].strip()
        await cancel_timer(timer_id=timer_id1)
        await cancel_timer(timer_id=timer_id2)


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_format_duration_seconds(self):
        """Test formatting seconds."""
        from jarvis.tools.alarms import _format_duration

        assert _format_duration(1) == "1 second"
        assert _format_duration(5) == "5 seconds"
        assert _format_duration(59) == "59 seconds"

    def test_format_duration_minutes(self):
        """Test formatting minutes."""
        from jarvis.tools.alarms import _format_duration

        assert _format_duration(60) == "1 minute"
        assert _format_duration(120) == "2 minutes"
        assert _format_duration(90) == "1 minute 30 seconds"

    def test_format_duration_hours(self):
        """Test formatting hours."""
        from jarvis.tools.alarms import _format_duration

        assert _format_duration(3600) == "1 hour"
        assert _format_duration(7200) == "2 hours"
        assert _format_duration(5400) == "1 hour 30 minutes"

    def test_format_iso(self):
        """Test ISO formatting."""
        from datetime import datetime, timezone
        from jarvis.tools.alarms import _format_iso

        dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = _format_iso(dt)
        assert "2025-01-15T10:30:00Z" == result


@pytest.mark.asyncio
async def test_get_alarm_tools():
    """Test that get_alarm_tools returns all tools."""
    from jarvis.tools.alarms import get_alarm_tools

    tools = get_alarm_tools()
    tool_names = [t.__name__ for t in tools]

    assert "add_alarm" in tool_names
    assert "list_alarms" in tool_names
    assert "cancel_alarm" in tool_names
    assert "set_timer" in tool_names
    assert "cancel_timer" in tool_names
    assert "list_timers" in tool_names
