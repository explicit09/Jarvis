"""Outlook (Microsoft Graph) integration helpers."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
try:
    import msal
except Exception:  # pragma: no cover
    msal = None

from jarvis.config import config
from jarvis.storage import get_data_dir

logger = logging.getLogger(__name__)

DEFAULT_SCOPES = ["Calendars.ReadWrite", "offline_access"]
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


def _get_cache_path() -> Path:
    return get_data_dir() / "msal_cache.bin"


def _load_cache() -> msal.SerializableTokenCache:
    if msal is None:
        raise RuntimeError("msal is not installed. Add 'msal' to dependencies.")
    cache = msal.SerializableTokenCache()
    cache_path = _get_cache_path()
    if cache_path.exists():
        cache.deserialize(cache_path.read_text(encoding="utf-8"))
    return cache


def _save_cache(cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        _get_cache_path().write_text(cache.serialize(), encoding="utf-8")


def _get_client_app() -> msal.PublicClientApplication:
    if msal is None:
        raise RuntimeError("msal is not installed. Add 'msal' to dependencies.")
    tenant = config.outlook.tenant_id or "common"
    authority = f"https://login.microsoftonline.com/{tenant}"
    cache = _load_cache()
    return msal.PublicClientApplication(
        client_id=config.outlook.client_id,
        authority=authority,
        token_cache=cache,
    )


def acquire_access_token(scopes: Optional[list[str]] = None) -> tuple[Optional[str], str]:
    """Acquire an access token using device code flow."""
    if not config.outlook.client_id:
        return None, "Outlook is not configured. Set MS_CLIENT_ID."
    if msal is None:
        return None, "msal is not installed. Add 'msal' to dependencies."

    scopes = scopes or DEFAULT_SCOPES
    app = _get_client_app()
    accounts = app.get_accounts()
    result = None

    if accounts:
        result = app.acquire_token_silent(scopes=scopes, account=accounts[0])

    if not result:
        flow = app.initiate_device_flow(scopes=scopes)
        if "user_code" not in flow:
            return None, "Failed to start Outlook device login flow."

        logger.info("Outlook device code flow: %s", flow.get("message"))
        result = app.acquire_token_by_device_flow(flow)

    _save_cache(app.token_cache)

    if "access_token" not in result:
        error = result.get("error_description") or result.get("error") or "Auth failed."
        return None, error

    return result["access_token"], ""


def _format_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def default_window() -> tuple[str, str]:
    """Return default start/end window (now to 7 days)."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=7)
    return _format_datetime(now), _format_datetime(end)


async def graph_get(url: str, token: str, params: Optional[dict] = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()


async def graph_post(url: str, token: str, payload: dict) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


async def graph_delete(url: str, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.delete(url, headers=headers)
        response.raise_for_status()
