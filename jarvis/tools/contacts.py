"""Contact management tools for J.A.R.V.I.S."""

from __future__ import annotations

from livekit.agents import llm

from jarvis.storage import get_connection


@llm.function_tool
async def add_contact(name: str, phone: str = "", email: str = "") -> str:
    """Add a contact."""
    name = name.strip()
    if not name:
        return "Name is required."

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO contacts (name, phone, email) VALUES (?, ?, ?)",
            (name, phone.strip() or None, email.strip() or None),
        )
        conn.commit()

    return f"Added contact: {name}"


@llm.function_tool
async def list_contacts(limit: int = 20) -> str:
    """List contacts."""
    limit = max(1, min(100, limit))
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, phone, email FROM contacts ORDER BY name ASC LIMIT ?",
            (limit,),
        ).fetchall()

    if not rows:
        return "No contacts found."

    lines = []
    for row in rows:
        details = []
        if row["phone"]:
            details.append(row["phone"])
        if row["email"]:
            details.append(row["email"])
        detail_text = " | ".join(details) if details else "No details"
        lines.append(f"{row['id']}: {row['name']} - {detail_text}")

    return "Contacts:\n" + "\n".join(lines)


@llm.function_tool
async def find_contact(query: str) -> str:
    """Find contacts by name."""
    query = query.strip()
    if not query:
        return "Query is required."

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, phone, email FROM contacts WHERE name LIKE ?",
            (f"%{query}%",),
        ).fetchall()

    if not rows:
        return "No matching contacts found."

    lines = []
    for row in rows:
        details = []
        if row["phone"]:
            details.append(row["phone"])
        if row["email"]:
            details.append(row["email"])
        detail_text = " | ".join(details) if details else "No details"
        lines.append(f"{row['id']}: {row['name']} - {detail_text}")

    return "Matches:\n" + "\n".join(lines)


def get_contact_tools() -> list:
    """Get contact tools."""
    return [add_contact, list_contacts, find_contact]
