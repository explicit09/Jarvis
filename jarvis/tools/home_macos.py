"""
Home automation tools using macOS Shortcuts and HomeKit.
Controls smart home devices through Apple's ecosystem without Home Assistant.
Based on proven implementation with scene support.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import re
from typing import Optional

from livekit.agents import llm

logger = logging.getLogger(__name__)


async def _run_command(cmd: list[str], timeout: float = 10.0) -> tuple[bool, str]:
    """Run a shell command and return success status and output."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        output = stdout.decode().strip() if stdout else stderr.decode().strip()
        return process.returncode == 0, output
    except asyncio.TimeoutError:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


async def _run_shortcut(shortcut_name: str, input_text: str = "") -> tuple[bool, str]:
    """Run a macOS Shortcut."""
    if platform.system() != "Darwin":
        return False, "Shortcuts are only available on macOS"

    try:
        if input_text:
            # Pipe input to shortcut
            process = await asyncio.create_subprocess_shell(
                f'echo "{input_text}" | shortcuts run "{shortcut_name}"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                "shortcuts", "run", shortcut_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)
        output = stdout.decode().strip() if stdout else stderr.decode().strip()
        return process.returncode == 0, output
    except asyncio.TimeoutError:
        return False, "Shortcut timed out"
    except Exception as e:
        return False, str(e)


async def _run_applescript(script: str, timeout: float = 5.0) -> tuple[bool, str]:
    """Execute AppleScript and return success status and output."""
    if platform.system() != "Darwin":
        return False, "AppleScript only available on macOS"

    try:
        process = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        output = stdout.decode().strip() if stdout else stderr.decode().strip()
        return process.returncode == 0, output
    except asyncio.TimeoutError:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


# Scene mappings
SCENE_MAPPINGS = {
    "morning": "Good Morning",
    "night": "Good Night",
    "goodnight": "Good Night",
    "movie": "Movie Time",
    "work": "Work Mode",
    "away": "Away",
    "home": "I'm Home",
    "arrive": "I'm Home",
}

# Shortcut mappings for common commands
SHORTCUT_MAPPINGS = {
    "lights on": "Lights on",
    "lights off": "Lights off",
    "turn on lights": "Lights on",
    "turn off lights": "Lights off",
}


@llm.function_tool
async def home_scene(scene: str) -> str:
    """
    Activate a home scene using HomeKit via macOS Shortcuts.

    Args:
        scene: Scene name (morning, night, movie, work, away, home)
    """
    if platform.system() != "Darwin":
        return "Home scenes are only available on macOS"

    scene_lower = scene.lower().strip()
    actual_scene = SCENE_MAPPINGS.get(scene_lower, scene)

    # Try Shortcuts first (most reliable)
    success, output = await _run_shortcut(f"Set Scene {actual_scene}")
    if success:
        return f"Activated scene: {actual_scene}"

    # Try generic scene shortcut
    success, output = await _run_shortcut("Home Scene", actual_scene)
    if success:
        return f"Activated scene: {actual_scene}"

    # Fallback to AppleScript (may not work with all HomeKit setups)
    script = f'''
    tell application "Home"
        activate
    end tell
    '''
    await _run_applescript(script)

    return f"Attempted to activate scene: {actual_scene}. You may need to create a Shortcut named 'Set Scene {actual_scene}' or 'Home Scene' in the Shortcuts app."


@llm.function_tool
async def home_lights(action: str, location: str = "all") -> str:
    """
    Control lights in the home.

    Args:
        action: on, off, or dim (with percentage like 'dim 50%')
        location: Room name or 'all'
    """
    if platform.system() != "Darwin":
        return "Light controls are only available on macOS"

    action_lower = action.lower().strip()
    location_lower = location.lower().strip()

    # Check for simple mappings first
    command = f"{action_lower} {location_lower}".strip()
    for key, shortcut in SHORTCUT_MAPPINGS.items():
        if key in command or command in key:
            success, output = await _run_shortcut(shortcut)
            if success:
                return f"Lights turned {action_lower}"

    # Handle specific actions
    if action_lower in ["on", "turn on"]:
        # Try simple shortcut first
        success, output = await _run_shortcut("Lights on")
        if success:
            return "Lights turned on"

        # Try location-specific
        if location_lower != "all":
            success, output = await _run_shortcut(f"Turn On {location.title()} Lights")
            if success:
                return f"{location.title()} lights turned on"

        return "Attempted to turn lights on. You may need to create a 'Lights on' Shortcut."

    elif action_lower in ["off", "turn off"]:
        success, output = await _run_shortcut("Lights off")
        if success:
            return "Lights turned off"

        if location_lower != "all":
            success, output = await _run_shortcut(f"Turn Off {location.title()} Lights")
            if success:
                return f"{location.title()} lights turned off"

        return "Attempted to turn lights off. You may need to create a 'Lights off' Shortcut."

    elif "dim" in action_lower:
        # Extract percentage
        match = re.search(r'(\d+)%?', action)
        if match:
            level = int(match.group(1))
            success, output = await _run_shortcut(f"Set {location.title()} Lights", f"{level}%")
            if success:
                return f"Set {location} lights to {level}%"
            return f"Attempted to dim lights to {level}%. You may need to create a 'Set {location.title()} Lights' Shortcut."
        return "Please specify a dim percentage, like 'dim 50%'"

    return f"Unknown light action: {action}"


@llm.function_tool
async def home_temperature(temperature: int, mode: str = "") -> str:
    """
    Set thermostat temperature.

    Args:
        temperature: Target temperature in degrees (60-85)
        mode: heating, cooling, or auto (optional)
    """
    if platform.system() != "Darwin":
        return "Thermostat control is only available on macOS"

    # Clamp temperature to reasonable range
    temperature = max(60, min(85, temperature))

    input_data = f"{temperature}"
    if mode:
        input_data += f" {mode}"

    success, output = await _run_shortcut("Set Temperature", input_data)

    if success:
        result = f"Temperature set to {temperature}°"
        if mode:
            result += f" ({mode} mode)"
        return result

    return f"Attempted to set temperature to {temperature}°. You may need to create a 'Set Temperature' Shortcut that accepts a temperature value."


@llm.function_tool
async def home_lock(action: str = "lock", door: str = "all") -> str:
    """
    Control door locks.

    Args:
        action: lock or unlock
        door: front, back, or all
    """
    if platform.system() != "Darwin":
        return "Lock control is only available on macOS"

    action_lower = action.lower().strip()
    door_lower = door.lower().strip()

    if action_lower == "lock":
        if door_lower == "all":
            success, output = await _run_shortcut("Lock All Doors")
            if success:
                return "All doors locked"
            # Try individual doors
            await _run_shortcut("Lock Front Door")
            await _run_shortcut("Lock Back Door")
            return "Attempted to lock all doors"
        else:
            success, output = await _run_shortcut(f"Lock {door.title()} Door")
            if success:
                return f"{door.title()} door locked"
            return f"Attempted to lock {door} door. You may need to create a 'Lock {door.title()} Door' Shortcut."

    elif action_lower == "unlock":
        if door_lower == "all":
            success, output = await _run_shortcut("Unlock All Doors")
            if success:
                return "All doors unlocked"
            return "Attempted to unlock all doors"
        else:
            success, output = await _run_shortcut(f"Unlock {door.title()} Door")
            if success:
                return f"{door.title()} door unlocked"
            return f"Attempted to unlock {door} door. You may need to create an 'Unlock {door.title()} Door' Shortcut."

    return f"Unknown door action: {action}. Use 'lock' or 'unlock'."


@llm.function_tool
async def home_status() -> str:
    """Get status of home devices via HomeKit."""
    if platform.system() != "Darwin":
        return "Home status is only available on macOS"

    # Try to get status via Shortcut
    success, output = await _run_shortcut("Home Status")

    if success and output:
        return output

    # Fallback to general info
    return """Home Status (via HomeKit Shortcuts):
To get detailed home status, create a 'Home Status' Shortcut that:
1. Gets the state of your lights, locks, and thermostat
2. Returns a summary of their states

Available device types:
- Lights (living room, bedroom, kitchen, office)
- Locks (front door, back door)
- Thermostat
- Scenes (morning, night, movie, work, away, home)"""


# Convenience functions
@llm.function_tool
async def good_morning() -> str:
    """Activate the morning routine scene."""
    return await home_scene("morning")


@llm.function_tool
async def good_night() -> str:
    """Activate the night routine scene."""
    return await home_scene("night")


@llm.function_tool
async def movie_time() -> str:
    """Activate the movie scene (dim lights, etc.)."""
    return await home_scene("movie")


@llm.function_tool
async def lights_on(room: str = "all") -> str:
    """Turn lights on in specified room or all rooms."""
    return await home_lights("on", room)


@llm.function_tool
async def lights_off(room: str = "all") -> str:
    """Turn lights off in specified room or all rooms."""
    return await home_lights("off", room)


def get_home_macos_tools() -> list:
    """Get macOS HomeKit/Shortcuts-based home automation tools."""
    return [
        home_scene,
        home_lights,
        home_temperature,
        home_lock,
        home_status,
        good_morning,
        good_night,
        movie_time,
        lights_on,
        lights_off,
    ]
