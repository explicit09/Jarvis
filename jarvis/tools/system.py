"""System control tools for J.A.R.V.I.S.

Provides tools for:
- Opening applications
- Running system commands
- Controlling system settings
"""

from __future__ import annotations

import asyncio
import logging
import platform
from datetime import datetime
from typing import List, Tuple

from livekit.agents import llm

logger = logging.getLogger(__name__)


async def _run_command(cmd: List[str], timeout: float = 30.0) -> Tuple[str, int]:
    """Run a shell command and return output and return code."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
        output = stdout.decode() if stdout else stderr.decode()
        return output.strip(), process.returncode or 0
    except asyncio.TimeoutError:
        return "Command timed out", -1
    except Exception as e:
        return f"Error: {str(e)}", -1


@llm.function_tool
async def get_current_time(timezone: str = "local") -> str:
    """Get the current time.

    Args:
        timezone: Timezone name (e.g., 'UTC', 'America/New_York') or 'local'
    """
    try:
        if timezone == "local":
            now = datetime.now()
            return f"The current time is {now.strftime('%I:%M %p on %A, %B %d, %Y')}"
        else:
            import pytz

            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            return f"The time in {timezone} is {now.strftime('%I:%M %p on %A, %B %d, %Y')}"
    except Exception as e:
        return f"Could not get time: {str(e)}"


@llm.function_tool
async def open_application(app_name: str) -> str:
    """Open an application on the computer.

    Args:
        app_name: Name of the application to open (e.g., 'Safari', 'Terminal', 'Spotify')
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        cmd = ["open", "-a", app_name]
    elif system == "Windows":
        cmd = ["start", "", app_name]
    elif system == "Linux":
        cmd = [app_name.lower()]
    else:
        return f"Unsupported operating system: {system}"

    output, code = await _run_command(cmd)

    if code == 0:
        return f"Opened {app_name}"
    else:
        return f"Could not open {app_name}: {output}"


@llm.function_tool
async def run_shell_command(command: str, confirm: bool = False) -> str:
    """Run a shell command and return the output.

    Use with caution - only run safe commands.

    Args:
        command: The shell command to execute
        confirm: Set true to confirm commands outside the allowlist
    """
    from jarvis.tools.safety import check_command_safety
    from jarvis.audit import append_event

    allowed, message = check_command_safety(command, confirm)
    if not allowed:
        return message

    append_event({"type": "host_command", "command": command, "confirmed": confirm})

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=30.0
        )

        output = stdout.decode() if stdout else ""
        error = stderr.decode() if stderr else ""

        if process.returncode == 0:
            return output.strip() or "Command executed successfully"
        else:
            return f"Command failed: {error.strip() or output.strip()}"
    except asyncio.TimeoutError:
        return "Command timed out after 30 seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@llm.function_tool
async def get_system_info() -> str:
    """Get basic system information."""
    system = platform.system()
    release = platform.release()
    machine = platform.machine()
    python_version = platform.python_version()

    # Get uptime on macOS/Linux
    uptime = "unknown"
    if system in ("Darwin", "Linux"):
        output, code = await _run_command(["uptime"])
        if code == 0:
            uptime = output

    return (
        f"System: {system} {release}\n"
        f"Architecture: {machine}\n"
        f"Python: {python_version}\n"
        f"Uptime: {uptime}"
    )


@llm.function_tool
async def set_volume(level: int) -> str:
    """Set the system volume level.

    Args:
        level: Volume level from 0 to 100
    """
    level = max(0, min(100, level))
    system = platform.system()

    if system == "Darwin":
        cmd = ["osascript", "-e", f"set volume output volume {level}"]
    elif system == "Linux":
        cmd = ["amixer", "set", "Master", f"{level}%"]
    else:
        return f"Volume control not supported on {system}"

    output, code = await _run_command(cmd)

    if code == 0:
        return f"Volume set to {level}%"
    else:
        return f"Could not set volume: {output}"


@llm.function_tool
async def toggle_dark_mode() -> str:
    """Toggle dark mode on macOS."""
    system = platform.system()

    if system != "Darwin":
        return "Dark mode toggle is only supported on macOS"

    script = '''
    tell application "System Events"
        tell appearance preferences
            set dark mode to not dark mode
        end tell
    end tell
    '''
    cmd = ["osascript", "-e", script]
    output, code = await _run_command(cmd)

    if code == 0:
        return "Dark mode toggled"
    else:
        return f"Could not toggle dark mode: {output}"


def get_system_tools() -> list:
    """Get all system tools."""
    return [
        get_current_time,
        open_application,
        run_shell_command,
        get_system_info,
        set_volume,
        toggle_dark_mode,
    ]
