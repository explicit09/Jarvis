"""Calling and messaging tools via Twilio."""

from __future__ import annotations

import logging
import re
from typing import Optional

from livekit.agents import llm

from jarvis.config import config
from jarvis.storage import get_connection

logger = logging.getLogger(__name__)


def _looks_like_number(value: str) -> bool:
    return bool(re.search(r"\d", value))


def _resolve_contact_phone(name: str) -> tuple[Optional[str], str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT name, phone FROM contacts WHERE name LIKE ?",
            (f"%{name}%",),
        ).fetchall()

    if not rows:
        return None, f"No contact found matching '{name}'."
    if len(rows) > 1:
        matches = ", ".join(row["name"] for row in rows)
        return None, f"Multiple contacts found: {matches}. Be more specific."

    phone = rows[0]["phone"]
    if not phone:
        return None, f"Contact '{rows[0]['name']}' has no phone number."
    return phone, ""


def _ensure_twilio_configured() -> Optional[str]:
    if not config.twilio.account_sid or not config.twilio.auth_token:
        return (
            "Twilio is not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
        )
    if not config.twilio.from_number:
        return "Twilio from-number not configured. Set TWILIO_FROM_NUMBER."
    return None


@llm.function_tool
async def place_call(
    to_number: str = "",
    message: str = "Hello, this is J.A.R.V.I.S.",
    confirm: bool = False,
) -> str:
    """Place a phone call using Twilio with a spoken message."""
    error = _ensure_twilio_configured()
    if error:
        return error

    if config.safety.require_confirmation and not confirm:
        return "Confirmation required to place a call. Re-run with confirm=true."

    try:
        from twilio.rest import Client
    except Exception:
        return "Twilio library not installed. Add 'twilio' to dependencies."

    target = to_number.strip() or config.twilio.default_to_number
    if target and not _looks_like_number(target):
        resolved, error = _resolve_contact_phone(target)
        if not resolved:
            return error
        target = resolved
    if not target:
        return "No destination number provided. Set TWILIO_DEFAULT_TO_NUMBER or pass to_number."

    client = Client(config.twilio.account_sid, config.twilio.auth_token)
    try:
        call = client.calls.create(
            to=target,
            from_=config.twilio.from_number,
            twiml=f"<Response><Say>{message}</Say></Response>",
        )
        return f"Call initiated to {target}. SID: {call.sid}"
    except Exception as exc:
        logger.error("Twilio call failed: %s", exc)
        return f"Failed to place call: {exc}"


@llm.function_tool
async def send_sms(
    message: str,
    to_number: str = "",
    from_number: str = "",
    confirm: bool = False,
) -> str:
    """Send an SMS using Twilio."""
    error = _ensure_twilio_configured()
    if error:
        return error

    if config.safety.require_confirmation and not confirm:
        return "Confirmation required to send SMS. Re-run with confirm=true."

    try:
        from twilio.rest import Client
    except Exception:
        return "Twilio library not installed. Add 'twilio' to dependencies."

    target = to_number.strip() or config.twilio.default_to_number
    if target and not _looks_like_number(target):
        resolved, error = _resolve_contact_phone(target)
        if not resolved:
            return error
        target = resolved
    if not target:
        return "No destination number provided. Set TWILIO_DEFAULT_TO_NUMBER or pass to_number."

    sender = from_number.strip() or config.twilio.from_number
    client = Client(config.twilio.account_sid, config.twilio.auth_token)
    try:
        sms = client.messages.create(
            to=target,
            from_=sender,
            body=message,
        )
        return f"SMS sent to {target}. SID: {sms.sid}"
    except Exception as exc:
        logger.error("Twilio SMS failed: %s", exc)
        return f"Failed to send SMS: {exc}"


def get_telephony_tools() -> list:
    """Get calling and messaging tools."""
    return [place_call, send_sms]
