"""Manage local J.A.R.V.I.S processes (best-effort)."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from jarvis.config import config


@dataclass
class ProcessInfo:
    pid: int
    mode: str
    started_at: str
    command: list[str]


def _data_dir() -> Path:
    path = config.storage.data_dir.expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path() -> Path:
    return _data_dir() / "runtime.json"


def _log_path(mode: str) -> Path:
    safe = "".join(ch for ch in mode if ch.isalnum() or ch in {"-", "_"})
    return _data_dir() / f"jarvis-{safe}.log"


def _load_state() -> Optional[ProcessInfo]:
    path = _state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProcessInfo(
            pid=int(data["pid"]),
            mode=str(data["mode"]),
            started_at=str(data["started_at"]),
            command=list(data["command"]),
        )
    except Exception:
        return None


def _save_state(info: ProcessInfo) -> None:
    _state_path().write_text(
        json.dumps(
            {
                "pid": info.pid,
                "mode": info.mode,
                "started_at": info.started_at,
                "command": info.command,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _clear_state() -> None:
    try:
        _state_path().unlink()
    except FileNotFoundError:
        return


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def status() -> dict:
    info = _load_state()
    if not info:
        return {"running": False}
    running = _is_running(info.pid)
    if not running:
        _clear_state()
        return {"running": False}
    return {
        "running": True,
        "pid": info.pid,
        "mode": info.mode,
        "started_at": info.started_at,
        "command": info.command,
        "log_path": str(_log_path(info.mode)),
    }


def start(mode: str) -> dict:
    current = status()
    if current.get("running"):
        return {"ok": False, "error": "Already running.", "status": current}

    mode = mode.strip().lower()
    if mode not in {"livekit", "standalone"}:
        return {"ok": False, "error": "Mode must be 'livekit' or 'standalone'."}

    module = "jarvis.main" if mode == "livekit" else "jarvis.standalone"
    cmd = [sys.executable, "-m", module]

    log_path = _log_path(mode)
    log_file = log_path.open("a", encoding="utf-8")

    process = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env=os.environ.copy(),
    )

    info = ProcessInfo(
        pid=process.pid,
        mode=mode,
        started_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        command=cmd,
    )
    _save_state(info)
    return {"ok": True, "status": status()}


def stop() -> dict:
    info = _load_state()
    if not info:
        return {"ok": True, "status": {"running": False}}

    if not _is_running(info.pid):
        _clear_state()
        return {"ok": True, "status": {"running": False}}

    try:
        os.killpg(info.pid, signal.SIGTERM)
    except Exception:
        try:
            os.kill(info.pid, signal.SIGTERM)
        except Exception:
            pass

    _clear_state()
    return {"ok": True, "status": {"running": False}}

