"""macOS menu bar launcher for the J.A.R.V.I.S web UI."""

from __future__ import annotations

import os
import threading
import webbrowser

import httpx


def _url() -> str:
    host = os.getenv("JARVIS_UI_HOST", "127.0.0.1")
    port = int(os.getenv("JARVIS_UI_PORT", "8080"))
    return f"http://{host}:{port}"


def _token() -> str:
    return os.getenv("JARVIS_UI_TOKEN", "")


def _post(path: str, payload: dict) -> None:
    url = _url() + path
    token = _token()
    headers = {"X-Jarvis-Token": token} if token else {}
    with httpx.Client(timeout=3.0) as client:
        client.post(url, json=payload, headers=headers)


def main() -> None:
    try:
        import rumps
    except Exception:
        raise SystemExit("rumps is not installed. Install optional UI macOS dependencies.")

    app = rumps.App("J.A.R.V.I.S", quit_button=None)

    @rumps.clicked("Open Dashboard")
    def open_dashboard(_):
        webbrowser.open(_url())

    @rumps.clicked("Start Standalone")
    def start_standalone(_):
        threading.Thread(
            target=lambda: _post("/api/runtime/start", {"mode": "standalone", "confirm": True}),
            daemon=True,
        ).start()

    @rumps.clicked("Start LiveKit")
    def start_livekit(_):
        threading.Thread(
            target=lambda: _post("/api/runtime/start", {"mode": "livekit", "confirm": True}),
            daemon=True,
        ).start()

    @rumps.clicked("Stop Voice")
    def stop_voice(_):
        threading.Thread(
            target=lambda: _post("/api/runtime/stop", {"confirm": True}),
            daemon=True,
        ).start()

    @rumps.clicked("Quit")
    def quit_app(_):
        rumps.quit_application()

    app.run()


if __name__ == "__main__":
    main()
