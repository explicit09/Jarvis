"""File operation tools for J.A.R.V.I.S."""

from __future__ import annotations

from pathlib import Path

from livekit.agents import llm

from jarvis.tools.safety import check_path_safety


@llm.function_tool
async def list_files(
    path: str = ".",
    pattern: str = "",
    limit: int = 50,
    confirm: bool = False,
) -> str:
    """List files in a directory."""
    allowed, message, resolved = check_path_safety(path, confirm)
    if not allowed:
        return message

    if not resolved.exists():
        return f"Path not found: {resolved}"
    if not resolved.is_dir():
        return f"Not a directory: {resolved}"

    limit = max(1, min(200, limit))
    entries = []
    if pattern:
        entries = sorted(resolved.glob(pattern))
    else:
        entries = sorted(resolved.iterdir())

    lines = []
    for entry in entries[:limit]:
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"{entry.name}{suffix}")

    if not lines:
        return "No files found."

    return "Files:\n" + "\n".join(lines)


@llm.function_tool
async def read_file(path: str, max_chars: int = 4000, confirm: bool = False) -> str:
    """Read a file's contents."""
    allowed, message, resolved = check_path_safety(path, confirm)
    if not allowed:
        return message

    if not resolved.exists():
        return f"File not found: {resolved}"
    if resolved.is_dir():
        return f"Path is a directory: {resolved}"

    data = resolved.read_text(encoding="utf-8", errors="replace")
    if len(data) > max_chars:
        data = data[:max_chars] + "\n... [truncated]"
    return data


@llm.function_tool
async def write_file(
    path: str,
    content: str,
    confirm: bool = False,
    overwrite: bool = True,
) -> str:
    """Write content to a file."""
    allowed, message, resolved = check_path_safety(path, confirm)
    if not allowed:
        return message

    if resolved.exists() and not overwrite:
        return f"File already exists: {resolved}"

    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {resolved}"


@llm.function_tool
async def search_files(
    query: str,
    path: str = ".",
    limit: int = 20,
    confirm: bool = False,
) -> str:
    """Search for a string in files under a path."""
    allowed, message, resolved = check_path_safety(path, confirm)
    if not allowed:
        return message

    if not resolved.exists() or not resolved.is_dir():
        return f"Invalid directory: {resolved}"

    limit = max(1, min(100, limit))
    matches = []
    for file_path in resolved.rglob("*"):
        if file_path.is_dir():
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if query in content:
            matches.append(str(file_path))
            if len(matches) >= limit:
                break

    if not matches:
        return "No matches found."
    return "Matches:\n" + "\n".join(matches)


def get_file_tools() -> list:
    """Get file operation tools."""
    return [list_files, read_file, write_file, search_files]
