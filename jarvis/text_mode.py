"""Text command mode for J.A.R.V.I.S."""

from __future__ import annotations

import argparse
import asyncio
import inspect
import shlex
from typing import Any, Callable

from jarvis.tools import get_all_tools


def _coerce_value(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered.isdigit():
        return int(lowered)
    try:
        return float(value)
    except ValueError:
        return value


def _parse_kwargs(tokens: list[str]) -> tuple[dict[str, Any], str]:
    kwargs: dict[str, Any] = {}
    for token in tokens:
        if "=" not in token:
            return {}, f"Invalid arg '{token}'. Use key=value."
        key, value = token.split("=", 1)
        kwargs[key] = _coerce_value(value)
    return kwargs, ""


async def _run_tool(tool: Callable[..., Any], kwargs: dict[str, Any]) -> str:
    result = tool(**kwargs)
    if inspect.isawaitable(result):
        return await result
    return str(result)


def _build_tool_map() -> dict[str, Callable[..., Any]]:
    tools = get_all_tools()
    return {tool.__name__: tool for tool in tools}


def _print_help(tool_map: dict[str, Callable[..., Any]]) -> None:
    print("Use /tool_name key=value ...")
    print("Examples:")
    print("  /daily_brief city=London")
    print('  /remember content="Buy milk" tags="groceries" importance=2')
    print('  /add_task content="Pay rent" due_date=2025-01-05 priority=high')
    print("Type /tools to list tools. Type exit to quit.")


async def _repl(tool_map: dict[str, Callable[..., Any]]) -> None:
    _print_help(tool_map)
    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return

        if not raw:
            continue
        if raw.lower() in {"exit", "quit"}:
            print("Bye.")
            return
        if raw.lower() in {"/tools", "tools"}:
            for name in sorted(tool_map.keys()):
                print(name)
            continue
        if raw.lower() in {"/help", "help"}:
            _print_help(tool_map)
            continue

        if not raw.startswith("/"):
            print("Commands must start with '/'. Type /help for usage.")
            continue

        tokens = shlex.split(raw[1:])
        if not tokens:
            continue

        tool_name = tokens[0]
        tool = tool_map.get(tool_name)
        if not tool:
            print(f"Unknown tool: {tool_name}")
            continue

        kwargs, error = _parse_kwargs(tokens[1:])
        if error:
            print(error)
            continue

        try:
            output = await _run_tool(tool, kwargs)
        except TypeError as exc:
            print(f"Invalid args: {exc}")
            continue
        except Exception as exc:
            print(f"Error: {exc}")
            continue

        print(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S text command mode")
    parser.add_argument(
        "--command",
        help="Run a single command and exit (e.g., /daily_brief city=London)",
    )
    args = parser.parse_args()

    tool_map = _build_tool_map()

    if args.command:
        command = args.command.strip()
        if not command.startswith("/"):
            raise SystemExit("Command must start with '/'.")
        tokens = shlex.split(command[1:])
        tool = tool_map.get(tokens[0])
        if not tool:
            raise SystemExit(f"Unknown tool: {tokens[0]}")
        kwargs, error = _parse_kwargs(tokens[1:])
        if error:
            raise SystemExit(error)
        output = asyncio.run(_run_tool(tool, kwargs))
        print(output)
        return

    asyncio.run(_repl(tool_map))


if __name__ == "__main__":
    main()
