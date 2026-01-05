"""Code and project analysis tools for J.A.R.V.I.S."""

from __future__ import annotations

import ast
import difflib
import os
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from livekit.agents import llm

from jarvis.config import config
from jarvis.llm.text_client import generate_reply
from jarvis.tools.safety import check_path_safety


def _run_git(args: list[str], cwd: Path) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        output = completed.stdout.strip() if completed.stdout else completed.stderr.strip()
        return completed.returncode, output
    except Exception as exc:
        return 1, str(exc)


def _list_repo_files(root: Path) -> list[Path]:
    """List files respecting .gitignore when possible."""
    code, _ = _run_git(["rev-parse", "--is-inside-work-tree"], root)
    if code != 0:
        files: list[Path] = []
        for path in root.rglob("*"):
            if ".git" in path.parts:
                continue
            if path.is_file():
                files.append(path)
        return files

    tracked_code, tracked_out = _run_git(["ls-files"], root)
    other_code, other_out = _run_git(["ls-files", "--others", "--exclude-standard"], root)
    if tracked_code != 0:
        return []

    rel_files = []
    for line in (tracked_out.splitlines() + other_out.splitlines()):
        line = line.strip()
        if not line:
            continue
        rel_files.append(Path(line))

    return [root / rel for rel in rel_files]


@dataclass
class PythonSymbolIndex:
    functions: list[str]
    classes: list[str]
    imports: list[str]


def _analyze_python_code(source: str) -> PythonSymbolIndex:
    tree = ast.parse(source)
    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}:{alias.name}" if module else alias.name)

    return PythonSymbolIndex(
        functions=sorted(set(functions)),
        classes=sorted(set(classes)),
        imports=sorted(set(imports)),
    )


def _analyze_non_python_code(source: str) -> dict[str, list[str]]:
    # Best-effort regex-based extraction.
    function_patterns = [
        r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\([^)]*\)\s*=>",
    ]
    class_patterns = [
        r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)",
    ]
    import_patterns = [
        r"^\s*import\s+([A-Za-z0-9_./-]+)",
        r"^\s*from\s+([A-Za-z0-9_./-]+)\s+import\s+",
    ]

    functions: set[str] = set()
    classes: set[str] = set()
    imports: set[str] = set()

    for line in source.splitlines():
        for pattern in function_patterns:
            match = re.match(pattern, line)
            if match:
                functions.add(match.group(1))
        for pattern in class_patterns:
            match = re.match(pattern, line)
            if match:
                classes.add(match.group(1))
        for pattern in import_patterns:
            match = re.match(pattern, line)
            if match:
                imports.add(match.group(1))

    return {
        "functions": sorted(functions),
        "classes": sorted(classes),
        "imports": sorted(imports),
    }


@llm.function_tool
async def analyze_code(path: str, confirm: bool = False) -> str:
    """Analyze a source file and summarize its structure (functions/classes/imports)."""
    allowed, message, resolved = check_path_safety(path, confirm)
    if not allowed:
        return message

    if not resolved.exists() or resolved.is_dir():
        return f"File not found: {resolved}"

    source = resolved.read_text(encoding="utf-8", errors="replace")
    suffix = resolved.suffix.lower()

    if suffix == ".py":
        try:
            index = _analyze_python_code(source)
        except SyntaxError as exc:
            return f"Python parse error: {exc}"
        return (
            f"File: {resolved.name}\n"
            f"Classes: {', '.join(index.classes) or 'none'}\n"
            f"Functions: {', '.join(index.functions) or 'none'}\n"
            f"Imports: {', '.join(index.imports[:50]) or 'none'}"
        )

    data = _analyze_non_python_code(source)
    return (
        f"File: {resolved.name}\n"
        f"Classes: {', '.join(data['classes']) or 'none'}\n"
        f"Functions: {', '.join(data['functions']) or 'none'}\n"
        f"Imports: {', '.join(data['imports']) or 'none'}"
    )


@llm.function_tool
async def get_project_structure(path: str = ".", limit: int = 500, confirm: bool = False) -> str:
    """Generate a tree view of a project directory (respects .gitignore when possible)."""
    allowed, message, root = check_path_safety(path, confirm)
    if not allowed:
        return message

    if not root.exists() or not root.is_dir():
        return f"Invalid directory: {root}"

    limit = max(50, min(5000, limit))
    files = _list_repo_files(root)
    files = [f for f in files if f.is_file()]
    files = files[:limit]

    if not files:
        return "No files found."

    tree: dict[str, Any] = {}
    for file_path in files:
        rel = file_path.relative_to(root)
        parts = rel.parts
        cursor = tree
        for part in parts[:-1]:
            cursor = cursor.setdefault(part + "/", {})
        cursor.setdefault(parts[-1], None)

    lines: list[str] = []

    def walk(node: dict[str, Any], prefix: str = "") -> None:
        entries = list(node.items())
        entries.sort(key=lambda item: item[0])
        for i, (name, child) in enumerate(entries):
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(prefix + connector + name)
            if isinstance(child, dict):
                extension = "    " if i == len(entries) - 1 else "│   "
                walk(child, prefix + extension)

    walk(tree)
    header = f"Project structure ({root}):"
    if len(files) >= limit:
        header += f" (showing first {limit} files)"
    return header + "\n" + "\n".join(lines)


@llm.function_tool
async def count_lines(path: str = ".", confirm: bool = False) -> str:
    """Count lines of code by file extension."""
    allowed, message, root = check_path_safety(path, confirm)
    if not allowed:
        return message

    if not root.exists() or not root.is_dir():
        return f"Invalid directory: {root}"

    files = _list_repo_files(root)
    totals: dict[str, int] = defaultdict(int)
    total_lines = 0

    for file_path in files:
        if not file_path.is_file():
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        line_count = content.count("\n") + (1 if content else 0)
        ext = file_path.suffix.lower() or "<noext>"
        totals[ext] += line_count
        total_lines += line_count

    top = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:20]
    lines = [f"Total lines: {total_lines}"]
    for ext, count in top:
        lines.append(f"{ext}: {count}")
    return "\n".join(lines)


@llm.function_tool
async def find_todos(path: str = ".", limit: int = 50, confirm: bool = False) -> str:
    """Find TODO/FIXME/HACK comments in a codebase."""
    allowed, message, root = check_path_safety(path, confirm)
    if not allowed:
        return message

    if not root.exists() or not root.is_dir():
        return f"Invalid directory: {root}"

    limit = max(1, min(200, limit))
    pattern = re.compile(r"\b(TODO|FIXME|HACK)\b", re.IGNORECASE)
    matches: list[str] = []

    for file_path in _list_repo_files(root):
        if not file_path.is_file():
            continue
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                rel = file_path.relative_to(root)
                matches.append(f"{rel}:{idx}: {line.strip()}")
                if len(matches) >= limit:
                    break
        if len(matches) >= limit:
            break

    if not matches:
        return "No TODO/FIXME/HACK comments found."
    return "Findings:\n" + "\n".join(matches)


@llm.function_tool
async def diff_files(path_a: str, path_b: str, confirm: bool = False) -> str:
    """Return a unified diff between two files."""
    allowed_a, message_a, a = check_path_safety(path_a, confirm)
    if not allowed_a:
        return message_a
    allowed_b, message_b, b = check_path_safety(path_b, confirm)
    if not allowed_b:
        return message_b

    if not a.exists() or a.is_dir():
        return f"File not found: {a}"
    if not b.exists() or b.is_dir():
        return f"File not found: {b}"

    a_lines = a.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    b_lines = b.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    diff = difflib.unified_diff(a_lines, b_lines, fromfile=str(a), tofile=str(b))
    text = "".join(diff)
    if not text.strip():
        return "Files are identical."
    if len(text) > 8000:
        text = text[:8000] + "\n... [truncated]"
    return text


@llm.function_tool
async def explain_code(code: str, focus: str = "", confirm: bool = False) -> str:
    """Explain a code snippet using the configured cloud LLM (safe, text-only)."""
    if config.safety.require_confirmation and not confirm:
        return "Confirmation required to use explain_code (cloud request). Re-run with confirm=true."

    prompt = (
        "Explain this code clearly and concisely for the project context. "
        "Call out risks, edge cases, and how to modify it safely.\n"
    )
    if focus.strip():
        prompt += f"\nFocus: {focus.strip()}\n"
    prompt += f"\nCode:\n{code.strip()}\n"

    return await generate_reply(prompt)


def get_code_analysis_tools() -> list:
    """Get code analysis tools."""
    return [
        analyze_code,
        get_project_structure,
        count_lines,
        find_todos,
        diff_files,
        explain_code,
    ]

