"""macOS-specific tools for J.A.R.V.I.S."""

from __future__ import annotations

import asyncio
import logging
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

from livekit.agents import llm

from jarvis.tools.safety import check_path_safety

logger = logging.getLogger(__name__)


async def _run_command(cmd: list[str], timeout: float = 10.0) -> Tuple[str, int]:
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        output = stdout.decode() if stdout else stderr.decode()
        return output.strip(), process.returncode or 0
    except asyncio.TimeoutError:
        return "Command timed out", -1
    except Exception as exc:
        return f"Error: {exc}", -1


async def _osascript(script: str, timeout: float = 10.0) -> Tuple[str, int]:
    return await _run_command(["osascript", "-e", script], timeout=timeout)


async def _is_app_running(app_name: str) -> bool:
    script = (
        'tell application "System Events" to '
        f'(name of processes) contains "{app_name}"'
    )
    output, code = await _osascript(script)
    if code != 0:
        return False
    return output.strip().lower() == "true"


async def _ensure_app_running(app_name: str) -> bool:
    if await _is_app_running(app_name):
        return True
    output, code = await _run_command(["open", "-a", app_name])
    if code != 0:
        logger.warning("Could not open app %s: %s", app_name, output)
        return False
    # Music.app can be slow to start, wait longer
    await asyncio.sleep(1.5)
    return await _is_app_running(app_name)


def _local_tz() -> timezone:
    return datetime.now().astimezone().tzinfo or timezone.utc


def _escape_applescript(text: str) -> str:
    return text.replace('"', '\\"')


def _parse_datetime(value: str) -> Optional[datetime]:
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_local_tz())
    return parsed.astimezone(_local_tz())


def _applescript_date(var_name: str, dt: datetime) -> str:
    local = dt.astimezone(_local_tz())
    month_names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    month_name = month_names[local.month - 1]
    return "\n".join(
        [
            f"set {var_name} to (current date)",
            f"set year of {var_name} to {local.year}",
            f"set month of {var_name} to {month_name}",
            f"set day of {var_name} to {local.day}",
            f"set time of {var_name} to "
            f"{(local.hour * 3600) + (local.minute * 60) + local.second}",
        ]
    )


@llm.function_tool
async def get_battery_status() -> str:
    """Get battery status (macOS only)."""
    if platform.system() != "Darwin":
        return "Battery status is only available on macOS."

    output, code = await _run_command(["pmset", "-g", "batt"])
    if code != 0:
        return f"Could not read battery status: {output}"

    return output


@llm.function_tool
async def get_active_app() -> str:
    """Get the currently active application (macOS only)."""
    if platform.system() != "Darwin":
        return "Active app lookup is only available on macOS."

    script = (
        'tell application "System Events" to get name of first application process '
        "whose frontmost is true"
    )
    output, code = await _run_command(["osascript", "-e", script])
    if code != 0:
        return f"Could not determine active app: {output}"
    return f"Active app: {output}"


@llm.function_tool
async def reveal_in_finder(path: str, confirm: bool = False) -> str:
    """Reveal a file or directory in Finder."""
    if platform.system() != "Darwin":
        return "Finder integration is only available on macOS."

    allowed, message, resolved = check_path_safety(path, confirm)
    if not allowed:
        return message

    if not resolved.exists():
        return f"Path not found: {resolved}"

    output, code = await _run_command(["open", "-R", str(resolved)])
    if code != 0:
        return f"Could not reveal path: {output}"
    return f"Revealed in Finder: {resolved}"


@llm.function_tool
async def send_notification(title: str, message: str, sound: str = "") -> str:
    """Show a macOS notification."""
    if platform.system() != "Darwin":
        return "Notifications are only available on macOS."

    title = _escape_applescript(title.strip() or "J.A.R.V.I.S")
    message = _escape_applescript(message.strip())
    if not message:
        return "Message is required."

    sound_clause = f' sound name "{_escape_applescript(sound.strip())}"' if sound.strip() else ""
    script = f'display notification "{message}" with title "{title}"{sound_clause}'
    output, code = await _osascript(script)
    if code != 0:
        return f"Notification failed: {output}"
    return "Notification sent."


def _resolve_music_app(app: str) -> list[str]:
    """Resolve app name to actual macOS app names to try."""
    app = app.strip().lower()
    # Handle various ways users might refer to the apps
    if app in {"spotify"}:
        return ["Spotify"]
    if app in {"music", "apple music", "applemusic", "apple_music"}:
        return ["Music"]  # Apple Music is just "Music" on macOS
    # Auto mode: try Music first (more likely installed), then Spotify
    return ["Music", "Spotify"]


async def _music_command(command: str, app: str) -> str:
    if platform.system() != "Darwin":
        return "Music controls are only available on macOS."

    targets = _resolve_music_app(app)

    # Find which app to use
    target_app = None
    for target in targets:
        if await _is_app_running(target):
            target_app = target
            break

    # If no app running, try to open the first one
    if not target_app:
        target_app = targets[0]
        output, code = await _run_command(["open", "-a", target_app])
        if code != 0:
            return f"Could not open {target_app}: {output}"
        await asyncio.sleep(2.0)  # Wait for app to start

    # Handle Spotify separately - it has its own URL scheme
    if target_app == "Spotify":
        if command == "play":
            await _run_command(["open", "spotify:play"])
            return "Play command sent to Spotify"
        elif command == "pause":
            script = 'tell application "Spotify" to pause'
            output, code = await _osascript(script, timeout=5.0)
            return "Pause command sent to Spotify" if code == 0 else f"Could not pause: {output}"
        elif command == "next track":
            script = 'tell application "Spotify" to next track'
            output, code = await _osascript(script, timeout=5.0)
            return "Next track (Spotify)" if code == 0 else f"Could not skip: {output}"
        elif command == "previous track":
            script = 'tell application "Spotify" to previous track'
            output, code = await _osascript(script, timeout=5.0)
            return "Previous track (Spotify)" if code == 0 else f"Could not go back: {output}"

    # For Music.app - use UI scripting as it's most reliable
    if command in {"play", "pause", "playpause"}:
        # Activate Music first
        await _run_command(["open", "-a", "Music"])
        await asyncio.sleep(0.5)

        # Use keyboard shortcut via System Events - most reliable method
        script = '''
tell application "Music" to activate
delay 0.3
tell application "System Events"
    tell process "Music"
        keystroke space
    end tell
end tell'''
        output, code = await _osascript(script, timeout=5.0)
        if code == 0:
            return f"{command.title()} command sent to Music"
        return f"Could not {command}: {output}. Ensure Music has Accessibility permissions."

    elif command == "next track":
        # Cmd+Right = next track in Music
        script = '''
tell application "Music" to activate
delay 0.3
tell application "System Events"
    tell process "Music"
        key code 124 using command down
    end tell
end tell'''
        output, code = await _osascript(script, timeout=5.0)
        return "Next track (Music)" if code == 0 else f"Could not skip: {output}"

    elif command == "previous track":
        # Cmd+Left = previous track in Music
        script = '''
tell application "Music" to activate
delay 0.3
tell application "System Events"
    tell process "Music"
        key code 123 using command down
    end tell
end tell'''
        output, code = await _osascript(script, timeout=5.0)
        return "Previous track (Music)" if code == 0 else f"Could not go back: {output}"

    return f"Unknown command: {command}"


@llm.function_tool
async def play_music(app: str = "auto") -> str:
    """Play music. Use app='music' for Apple Music, app='spotify' for Spotify, or app='auto' to try both."""
    return await _music_command("play", app)


@llm.function_tool
async def pause_music(app: str = "auto") -> str:
    """Pause music. Use app='music' for Apple Music, app='spotify' for Spotify, or app='auto' to try both."""
    return await _music_command("pause", app)


@llm.function_tool
async def next_track(app: str = "auto") -> str:
    """Skip to the next track. Use app='music' for Apple Music, app='spotify' for Spotify."""
    return await _music_command("next track", app)


@llm.function_tool
async def previous_track(app: str = "auto") -> str:
    """Go to the previous track. Use app='music' for Apple Music, app='spotify' for Spotify."""
    return await _music_command("previous track", app)


@llm.function_tool
async def now_playing(app: str = "auto") -> str:
    """Get current track info from Spotify or Apple Music."""
    if platform.system() != "Darwin":
        return "Now playing is only available on macOS."

    for target in _resolve_music_app(app):
        if await _ensure_app_running(target):
            script = (
                f'tell application "{target}" to '
                'if player state is playing then '
                'return (name of current track) & " — " & (artist of current track) '
                'else return "stopped"'
            )
            output, code = await _osascript(script)
            if code == 0 and output:
                return f"{target}: {output}"

    return "No supported music app is running."


@llm.function_tool
async def list_apple_calendars() -> str:
    """List available calendars from macOS Calendar."""
    if platform.system() != "Darwin":
        return "Calendar tools are only available on macOS."

    script = (
        'tell application "Calendar" to '
        'get name of calendars'
    )
    output, code = await _osascript(script, timeout=15.0)
    if code != 0:
        return f"Failed to list calendars: {output}"
    calendars = [item.strip() for item in output.split(",") if item.strip()]
    if not calendars:
        return "No calendars found."
    return "Calendars:\n" + "\n".join(calendars)


@llm.function_tool
async def create_apple_calendar_event(
    title: str,
    start_time: str,
    end_time: str = "",
    calendar_name: str = "",
) -> str:
    """Create a calendar event in the macOS Calendar app."""
    if platform.system() != "Darwin":
        return "Calendar tools are only available on macOS."

    title = _escape_applescript(title.strip())
    if not title:
        return "Event title is required."

    start_dt = _parse_datetime(start_time)
    if start_dt is None:
        return "Start time must be ISO 8601 (e.g., 2025-01-05T09:00)."

    end_dt = _parse_datetime(end_time) if end_time.strip() else start_dt + timedelta(minutes=30)

    start_script = _applescript_date("startDate", start_dt)
    end_script = _applescript_date("endDate", end_dt)

    calendar_clause = (
        f'calendar "{_escape_applescript(calendar_name.strip())}"'
        if calendar_name.strip()
        else "calendar 1"
    )

    script = "\n".join(
        [
            start_script,
            end_script,
            'tell application "Calendar"',
            f"set targetCalendar to {calendar_clause}",
            'tell targetCalendar to make new event with properties '
            f'{{summary:"{title}", start date:startDate, end date:endDate}}',
            "end tell",
        ]
    )
    output, code = await _osascript(script, timeout=15.0)
    if code != 0:
        return f"Failed to create event: {output}"
    return f"Created Calendar event: {title}"


@llm.function_tool
async def create_apple_reminder(
    title: str,
    due_at: str = "",
    list_name: str = "",
    notes: str = "",
) -> str:
    """Create a reminder in the macOS Reminders app."""
    if platform.system() != "Darwin":
        return "Reminders are only available on macOS."

    title = _escape_applescript(title.strip())
    if not title:
        return "Reminder title is required."

    due_dt = _parse_datetime(due_at) if due_at.strip() else None
    due_script = _applescript_date("dueDate", due_dt) if due_dt else ""

    list_clause = (
        f'list "{_escape_applescript(list_name.strip())}"'
        if list_name.strip()
        else "list 1"
    )
    notes_clause = f', body:"{_escape_applescript(notes.strip())}"' if notes.strip() else ""
    due_clause = ", remind me date:dueDate" if due_dt else ""

    script_lines = []
    if due_script:
        script_lines.append(due_script)
    script_lines.extend(
        [
            'tell application "Reminders"',
            f"set targetList to {list_clause}",
            f'tell targetList to make new reminder with properties '
            f'{{name:"{title}"{notes_clause}{due_clause}}}',
            "end tell",
        ]
    )
    output, code = await _osascript("\n".join(script_lines), timeout=15.0)
    if code != 0:
        return f"Failed to create reminder: {output}"
    return f"Created reminder: {title}"


def get_macos_tools() -> list:
    """Get macOS tools."""
    return [
        get_battery_status,
        get_active_app,
        reveal_in_finder,
        send_notification,
        play_music,
        pause_music,
        next_track,
        previous_track,
        now_playing,
        list_apple_calendars,
        create_apple_calendar_event,
        create_apple_reminder,
    ]
