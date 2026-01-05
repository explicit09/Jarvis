"""Lightweight audit logging for J.A.R.V.I.S."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis.config import config


def _data_dir() -> Path:
    path = config.storage.data_dir.expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def audit_path() -> Path:
    """Path to the audit log file."""
    return _data_dir() / "audit.log"


def append_event(event: dict[str, Any]) -> None:
    """Append an audit event as JSONL (best-effort)."""
    payload = dict(event)
    payload["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    try:
        audit_path().open("a", encoding="utf-8").write(json.dumps(payload) + "\n")
    except Exception:
        pass


def tail(max_lines: int = 200) -> str:
    """Return the last N lines of the audit log (best-effort)."""
    max_lines = max(10, min(2000, max_lines))
    path = audit_path()
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-max_lines:])
    except Exception:
        return ""
