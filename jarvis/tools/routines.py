"""Routine automation tools for J.A.R.V.I.S."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from livekit.agents import llm

from jarvis.config import config
from jarvis.storage import get_connection
from jarvis.tools.smart_home import set_device_state, toggle_device
from jarvis.tools.system import open_application, run_shell_command, set_volume


def _validate_actions(actions: list[dict[str, Any]]) -> tuple[bool, str]:
    if not isinstance(actions, list) or not actions:
        return False, "Actions must be a non-empty list."

    for action in actions:
        if not isinstance(action, dict):
            return False, "Each action must be an object."
        if "type" not in action:
            return False, "Each action must include a 'type' field."
    return True, ""


async def _execute_action(action: dict[str, Any], confirm: bool) -> str:
    action_type = action.get("type", "").strip().lower()

    if action_type in {"device_on", "device_off"}:
        entity_id = action.get("entity_id", "")
        state = "on" if action_type == "device_on" else "off"
        return await set_device_state(entity_id=entity_id, state=state)
    if action_type == "toggle_device":
        return await toggle_device(entity_id=action.get("entity_id", ""))
    if action_type == "set_volume":
        return await set_volume(level=int(action.get("level", 50)))
    if action_type == "open_app":
        return await open_application(app_name=action.get("app_name", ""))
    if action_type == "shell_command":
        return await run_shell_command(
            command=action.get("command", ""),
            confirm=confirm,
        )
    if action_type == "wait":
        seconds = float(action.get("seconds", 1))
        await asyncio.sleep(max(0.0, min(300.0, seconds)))
        return f"Waited {seconds} seconds."

    return f"Unknown action type: {action_type}"


@llm.function_tool
async def add_routine(name: str, actions_json: str, description: str = "") -> str:
    """Create or update a routine with a JSON list of actions."""
    name = name.strip()
    if not name:
        return "Routine name is required."

    try:
        actions = json.loads(actions_json)
    except json.JSONDecodeError as exc:
        return f"Invalid JSON: {exc}"

    is_valid, error = _validate_actions(actions)
    if not is_valid:
        return error

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM routines WHERE name = ? ORDER BY created_at DESC LIMIT 1",
            (name,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE routines
                SET description = ?, actions_json = ?, created_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (description.strip() or None, json.dumps(actions), existing["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO routines (name, description, actions_json)
                VALUES (?, ?, ?)
                """,
                (name, description.strip() or None, json.dumps(actions)),
            )
        conn.commit()

    return f"Routine saved: {name}"


@llm.function_tool
async def list_routines(limit: int = 20) -> str:
    """List available routines."""
    limit = max(1, min(100, limit))
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, description, created_at
            FROM routines
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    if not rows:
        return "No routines found."

    lines = []
    for row in rows:
        desc = f" - {row['description']}" if row["description"] else ""
        lines.append(f"{row['id']}: {row['name']}{desc}")

    return "Routines:\n" + "\n".join(lines)


@llm.function_tool
async def run_routine(name: str, confirm: bool = False) -> str:
    """Run a routine by name."""
    name = name.strip()
    if not name:
        return "Routine name is required."

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT actions_json
            FROM routines
            WHERE name = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (name,),
        ).fetchone()

    if not row:
        return f"Routine '{name}' not found."

    if config.safety.require_confirmation and not confirm:
        return "Confirmation required to run routines. Re-run with confirm=true."

    try:
        actions = json.loads(row["actions_json"])
    except json.JSONDecodeError:
        return "Routine actions are corrupted."

    is_valid, error = _validate_actions(actions)
    if not is_valid:
        return error

    results = []
    for action in actions:
        results.append(await _execute_action(action, confirm))

    return "Routine complete:\n" + "\n".join(results)


@llm.function_tool
async def delete_routine(name: str) -> str:
    """Delete a routine by name."""
    name = name.strip()
    if not name:
        return "Routine name is required."

    with get_connection() as conn:
        cur = conn.execute("DELETE FROM routines WHERE name = ?", (name,))
        conn.commit()

    if cur.rowcount:
        return f"Deleted {cur.rowcount} routine(s) named '{name}'."
    return f"Routine '{name}' not found."


def get_routine_tools() -> list:
    """Get routine tools."""
    return [add_routine, list_routines, run_routine, delete_routine]
