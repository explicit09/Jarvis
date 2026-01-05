"""Secure command execution helpers for J.A.R.V.I.S.

Provides:
- run_quick_command: fast allowlisted host execution (delegates to run_shell_command)
- run_sandboxed_command: Docker-based sandbox for running arbitrary commands
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Tuple

from livekit.agents import llm

from jarvis.config import config
from jarvis.audit import append_event
from jarvis.tools.safety import check_command_safety, check_path_safety
from jarvis.tools.system import run_shell_command

logger = logging.getLogger(__name__)


async def _run_exec(cmd: list[str], timeout_s: float) -> Tuple[str, int]:
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_s)
        out = stdout.decode() if stdout else ""
        err = stderr.decode() if stderr else ""
        combined = (out + ("\n" + err if err else "")).strip()
        return combined, process.returncode or 0
    except asyncio.TimeoutError:
        return f"Timed out after {timeout_s} seconds.", -1
    except FileNotFoundError:
        return "Executable not found.", -1
    except Exception as exc:
        return f"Error: {exc}", -1


def _truncate(text: str, max_chars: int = 6000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated]"


def _docker_available() -> bool:
    return any(
        (Path(p) / "docker").exists() for p in os.getenv("PATH", "").split(os.pathsep) if p
    )


@llm.function_tool
async def run_quick_command(command: str) -> str:
    """Run a safe command directly on the host (strict allowlist, no confirmation)."""
    allowed, message = check_command_safety(command, confirm=False)
    if not allowed:
        return message
    return await run_shell_command(command=command, confirm=False)


@llm.function_tool
async def run_sandboxed_command(
    command: str,
    workdir: str = ".",
    image: str = "python:3.11-slim",
    timeout_s: float = 30.0,
    memory_mb: int = 256,
    cpus: float = 1.0,
    network: bool = False,
    writable: bool = False,
    confirm: bool = False,
) -> str:
    """Run a command inside a Docker container sandbox.

    Defaults:
    - Read-only mount of workdir
    - Network disabled
    - Limited CPU/memory
    """
    allowed_cmd, msg = check_command_safety(command, confirm=confirm)
    if not allowed_cmd:
        return msg

    allowed_path, path_msg, resolved = check_path_safety(workdir, confirm=confirm)
    if not allowed_path:
        return path_msg
    if not resolved.exists() or not resolved.is_dir():
        return f"Invalid workdir: {resolved}"

    if (network or writable) and config.safety.require_confirmation and not confirm:
        return "Confirmation required for network or writable sandbox. Re-run with confirm=true."

    if not _docker_available():
        return "Docker not found. Install Docker Desktop or set PATH to docker."

    timeout_s = max(1.0, min(300.0, timeout_s))
    memory_mb = max(64, min(4096, memory_mb))
    cpus = max(0.25, min(8.0, cpus))

    mount_mode = "rw" if writable else "ro"
    network_mode = "bridge" if network else "none"

    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "--init",
        "--network",
        network_mode,
        "--memory",
        f"{memory_mb}m",
        "--cpus",
        str(cpus),
        "--pids-limit",
        "256",
        "--security-opt",
        "no-new-privileges",
        "--cap-drop",
        "ALL",
        "-v",
        f"{str(resolved)}:/workspace:{mount_mode}",
        "-w",
        "/workspace",
        image,
        "sh",
        "-lc",
        command,
    ]

    append_event(
        {
            "type": "sandbox_command",
            "workdir": str(resolved),
            "image": image,
            "network": network,
            "writable": writable,
        }
    )

    output, code = await _run_exec(docker_cmd, timeout_s=timeout_s)
    output = _truncate(output or "(no output)")
    if code == 0:
        return output
    return f"Command failed (exit {code}):\n{output}"


def get_sandbox_tools() -> list:
    """Get sandbox tools."""
    return [run_quick_command, run_sandboxed_command]
