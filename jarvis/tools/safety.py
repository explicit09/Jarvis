"""Safety utilities for tool execution."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Tuple

from jarvis.config import config

DEFAULT_ALLOWED_COMMANDS = [
    "ls",
    "pwd",
    "whoami",
    "date",
    "uptime",
    "df -h",
    "du -h",
]

DANGEROUS_PATTERNS = [
    "rm -rf",
    "sudo",
    "mkfs",
    "> /dev",
    "dd if=",
    ":(){:|:&};:",
    "chmod -R 777",
]


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def get_allowed_commands() -> list[str]:
    """Return the configured allowed command prefixes."""
    if config.safety.allowed_commands:
        return config.safety.allowed_commands
    return DEFAULT_ALLOWED_COMMANDS


def get_allowed_paths() -> list[Path]:
    """Return allowed file path prefixes."""
    allowed = []
    if config.safety.allowed_paths:
        allowed.extend(Path(p).expanduser().resolve() for p in config.safety.allowed_paths)
    else:
        allowed.append(Path.cwd().resolve())
        allowed.append(config.storage.data_dir.expanduser().resolve())
    return allowed


def check_command_safety(command: str, confirm: bool) -> Tuple[bool, str]:
    """Check command safety and confirmation requirements."""
    normalized = command.strip()
    if not normalized:
        return False, "Command is empty."

    lowered = normalized.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in lowered:
            return False, f"Command blocked for safety: contains '{pattern}'"

    allowed_prefixes = get_allowed_commands()
    if any(lowered.startswith(prefix.lower()) for prefix in allowed_prefixes):
        return True, "Command allowed"

    if not config.safety.require_confirmation:
        return True, "Command allowed without confirmation"

    if confirm:
        return True, "Command confirmed"

    return (
        False,
        "Confirmation required. Re-run with confirm=true if you want to proceed.",
    )


def check_path_safety(path: str, confirm: bool) -> Tuple[bool, str, Path]:
    """Check file path safety and confirmation requirements."""
    resolved = Path(path).expanduser().resolve()
    allowed_paths = get_allowed_paths()

    if any(_is_relative_to(resolved, allowed) for allowed in allowed_paths):
        return True, "Path allowed", resolved

    if not config.safety.require_confirmation:
        return True, "Path allowed without confirmation", resolved

    if confirm:
        return True, "Path confirmed", resolved

    return (
        False,
        "Confirmation required for this path. Re-run with confirm=true.",
        resolved,
    )


def normalize_command(command: str) -> list[str]:
    """Normalize command into argv list."""
    return shlex.split(command)
