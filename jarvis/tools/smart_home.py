"""Smart home tools powered by Home Assistant."""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from livekit.agents import llm

from jarvis.config import config

logger = logging.getLogger(__name__)

_http_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)
    return _http_client


def _get_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {config.home_assistant.token}"}


def _ensure_configured() -> Optional[str]:
    if not config.home_assistant.url or not config.home_assistant.token:
        return (
            "Home Assistant is not configured. Set HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN."
        )
    return None


@llm.function_tool
async def get_device_state(entity_id: str) -> str:
    """Get the current state of a Home Assistant entity."""
    error = _ensure_configured()
    if error:
        return error

    client = _get_client()
    try:
        response = await client.get(
            f"{config.home_assistant.url}/api/states/{entity_id}",
            headers=_get_headers(),
        )
        response.raise_for_status()
        data = response.json()
        return f"{entity_id} is {data.get('state')}."
    except Exception as exc:
        logger.error("Home Assistant state fetch failed: %s", exc)
        return f"Failed to get state for {entity_id}: {exc}"


@llm.function_tool
async def set_device_state(entity_id: str, state: str) -> str:
    """Set a Home Assistant entity to on/off."""
    error = _ensure_configured()
    if error:
        return error

    normalized = state.strip().lower()
    if normalized not in {"on", "off"}:
        return "State must be 'on' or 'off'."

    domain = entity_id.split(".", 1)[0]
    service = "turn_on" if normalized == "on" else "turn_off"

    client = _get_client()
    try:
        response = await client.post(
            f"{config.home_assistant.url}/api/services/{domain}/{service}",
            headers=_get_headers(),
            json={"entity_id": entity_id},
        )
        response.raise_for_status()
        return f"Set {entity_id} to {normalized}."
    except Exception as exc:
        logger.error("Home Assistant state change failed: %s", exc)
        return f"Failed to set {entity_id}: {exc}"


@llm.function_tool
async def toggle_device(entity_id: str) -> str:
    """Toggle a Home Assistant entity."""
    error = _ensure_configured()
    if error:
        return error

    client = _get_client()
    try:
        response = await client.post(
            f"{config.home_assistant.url}/api/services/homeassistant/toggle",
            headers=_get_headers(),
            json={"entity_id": entity_id},
        )
        response.raise_for_status()
        return f"Toggled {entity_id}."
    except Exception as exc:
        logger.error("Home Assistant toggle failed: %s", exc)
        return f"Failed to toggle {entity_id}: {exc}"


@llm.function_tool
async def list_devices(domain: str = "", limit: int = 20) -> str:
    """List Home Assistant entities, optionally filtered by domain."""
    error = _ensure_configured()
    if error:
        return error

    limit = max(1, min(50, limit))
    domain = domain.strip().lower()

    client = _get_client()
    try:
        response = await client.get(
            f"{config.home_assistant.url}/api/states",
            headers=_get_headers(),
        )
        response.raise_for_status()
        data = response.json()

        if domain:
            data = [
                item
                for item in data
                if item.get("entity_id", "").startswith(domain + ".")
            ]

        data = data[:limit]
        if not data:
            return "No devices found."

        lines = [f"{item.get('entity_id')}: {item.get('state')}" for item in data]
        return "Devices:\n" + "\n".join(lines)
    except Exception as exc:
        logger.error("Home Assistant list failed: %s", exc)
        return f"Failed to list devices: {exc}"


def get_smart_home_tools() -> list:
    """Get smart home tools."""
    return [get_device_state, set_device_state, toggle_device, list_devices]
