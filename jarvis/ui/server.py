"""J.A.R.V.I.S local web dashboard (also works as a PWA)."""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from jarvis.audit import append_event, tail
from jarvis.config import config
from jarvis.runtime import process_manager
from jarvis.tools import get_all_tools


def _ui_token() -> str:
    return os.getenv("JARVIS_UI_TOKEN", "").strip()


def _require_token(token: Optional[str]) -> None:
    expected = _ui_token()
    if not expected:
        raise HTTPException(status_code=500, detail="JARVIS_UI_TOKEN is not configured.")
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid UI token.")


def _ui_allow_remote() -> bool:
    return os.getenv("JARVIS_UI_ALLOW_REMOTE", "false").lower() == "true"


def _enforce_local_only(request: Request) -> None:
    if _ui_allow_remote():
        return
    client = request.client
    ip = client.host if client else ""
    if ip not in {"127.0.0.1", "::1"}:
        raise HTTPException(
            status_code=403,
            detail="Remote access disabled. Set JARVIS_UI_ALLOW_REMOTE=true to allow.",
        )


def _append_audit(event: dict[str, Any]) -> None:
    append_event(event)


def _tool_schema(tool) -> dict[str, Any]:
    sig = inspect.signature(tool)
    params = []
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        params.append(
            {
                "name": name,
                "kind": str(param.kind),
                "default": None if param.default is inspect._empty else param.default,
                "annotation": (
                    None if param.annotation is inspect._empty else str(param.annotation)
                ),
            }
        )
    return {
        "name": tool.__name__,
        "doc": (tool.__doc__ or "").strip(),
        "params": params,
    }


def _configured(value: str) -> bool:
    return bool(value and value.strip())


def create_app() -> FastAPI:
    app = FastAPI(title="J.A.R.V.I.S UI", version="0.1.0")

    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> str:
        _enforce_local_only(request)
        return _render_index()

    @app.get("/manifest.json")
    async def manifest() -> JSONResponse:
        return JSONResponse(
            {
                "name": "J.A.R.V.I.S",
                "short_name": "Jarvis",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#0b1220",
                "theme_color": "#0b1220",
                "icons": [
                    {"src": "/static/icon.svg", "sizes": "any", "type": "image/svg+xml"}
                ],
            }
        )

    @app.get("/api/status")
    async def status(request: Request) -> JSONResponse:
        _enforce_local_only(request)
        return JSONResponse(
            {
                "agent_name": config.agent_name,
                "providers": {
                    "deepgram": _configured(config.stt.deepgram_api_key),
                    "elevenlabs": _configured(config.tts.elevenlabs_api_key),
                    "anthropic": _configured(config.llm.anthropic_api_key),
                    "openai": _configured(config.llm.openai_api_key),
                    "twilio": _configured(config.twilio.account_sid)
                    and _configured(config.twilio.auth_token)
                    and _configured(config.twilio.from_number),
                    "outlook": _configured(config.outlook.client_id),
                    "github": _configured(config.github.token),
                    "home_assistant": _configured(config.home_assistant.url)
                    and _configured(config.home_assistant.token),
                    "picovoice": _configured(config.wake_word.picovoice_access_key),
                },
                "paths": {"data_dir": str(config.storage.data_dir.expanduser())},
                "runtime": process_manager.status(),
            }
        )

    @app.get("/api/tools")
    async def tools(request: Request) -> JSONResponse:
        _enforce_local_only(request)
        tools = get_all_tools()
        return JSONResponse({"count": len(tools), "tools": [_tool_schema(t) for t in tools]})

    @app.post("/api/tool/{tool_name}")
    async def run_tool(
        tool_name: str,
        request: Request,
        payload: dict[str, Any],
        x_jarvis_token: Optional[str] = Header(default=None),
    ) -> JSONResponse:
        _enforce_local_only(request)
        _require_token(x_jarvis_token)
        tools = {t.__name__: t for t in get_all_tools()}
        tool = tools.get(tool_name)
        if not tool:
            raise HTTPException(status_code=404, detail="Tool not found.")

        kwargs = payload.get("args", {})
        if not isinstance(kwargs, dict):
            raise HTTPException(status_code=400, detail="args must be an object.")

        _append_audit({"type": "tool_call", "tool": tool_name, "args": list(kwargs.keys())})

        try:
            result = tool(**kwargs)
            if inspect.isawaitable(result):
                result = await result
        except TypeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid args: {exc}") from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        text = str(result)
        if len(text) > 8000:
            text = text[:8000] + "\n... [truncated]"
        return JSONResponse({"ok": True, "result": text})

    @app.get("/api/audit")
    async def audit(request: Request, max_lines: int = 200) -> JSONResponse:
        _enforce_local_only(request)
        max_lines = max(10, min(2000, max_lines))
        content = tail(max_lines=max_lines)
        return JSONResponse({"content": content})

    @app.post("/api/runtime/start")
    async def runtime_start(
        request: Request,
        payload: dict[str, Any],
        x_jarvis_token: Optional[str] = Header(default=None),
    ) -> JSONResponse:
        _enforce_local_only(request)
        _require_token(x_jarvis_token)
        mode = str(payload.get("mode", "")).strip().lower()
        confirm = bool(payload.get("confirm", False))
        if config.safety.require_confirmation and not confirm:
            raise HTTPException(
                status_code=400,
                detail="Confirmation required. Re-run with confirm=true.",
            )
        append_event({"type": "runtime", "action": "start", "mode": mode})
        return JSONResponse(process_manager.start(mode))

    @app.post("/api/runtime/stop")
    async def runtime_stop(
        request: Request,
        payload: dict[str, Any],
        x_jarvis_token: Optional[str] = Header(default=None),
    ) -> JSONResponse:
        _enforce_local_only(request)
        _require_token(x_jarvis_token)
        confirm = bool(payload.get("confirm", False))
        if config.safety.require_confirmation and not confirm:
            raise HTTPException(
                status_code=400,
                detail="Confirmation required. Re-run with confirm=true.",
            )
        append_event({"type": "runtime", "action": "stop"})
        return JSONResponse(process_manager.stop())

    return app


def _render_index() -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>J.A.R.V.I.S</title>
    <link rel="manifest" href="/manifest.json" />
    <meta name="theme-color" content="#0b1220" />
    <style>
      :root { color-scheme: dark; }
      body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system; background: #0b1220; color: #e8eefc; }
      .wrap { max-width: 1080px; margin: 0 auto; padding: 18px; }
      .row { display: grid; grid-template-columns: 1fr; gap: 12px; }
      @media (min-width: 920px) { .row { grid-template-columns: 1fr 1fr; } }
      .card { background: #0f1a30; border: 1px solid #1f2e52; border-radius: 12px; padding: 14px; }
      h1 { margin: 0 0 10px; font-size: 20px; }
      h2 { margin: 0 0 10px; font-size: 15px; color: #b7c6ea; }
      .muted { color: #9db0dd; font-size: 12px; }
      .pill { display: inline-flex; gap: 8px; align-items: center; padding: 6px 10px; border-radius: 999px; border: 1px solid #1f2e52; margin: 4px 6px 0 0; font-size: 12px; }
      .dot { width: 8px; height: 8px; border-radius: 99px; background: #6b7280; }
      .dot.ok { background: #34d399; }
      .dot.bad { background: #fb7185; }
      input, textarea, select, button { width: 100%; background: #0b1220; color: #e8eefc; border: 1px solid #1f2e52; border-radius: 10px; padding: 10px; }
      textarea { min-height: 120px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
      button { cursor: pointer; background: #143056; }
      button:hover { background: #193b6c; }
      .grid2 { display: grid; grid-template-columns: 1fr; gap: 10px; }
      @media (min-width: 920px) { .grid2 { grid-template-columns: 1fr 1fr; } }
      pre { white-space: pre-wrap; word-break: break-word; background: #0b1220; border: 1px solid #1f2e52; border-radius: 10px; padding: 10px; margin: 0; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>J.A.R.V.I.S</h1>
      <div class="muted">Local dashboard. Tool execution requires <code>JARVIS_UI_TOKEN</code>.</div>
      <div class="row" style="margin-top: 12px;">
        <div class="card">
          <h2>Status</h2>
          <div id="statusPills"></div>
          <div class="muted" id="dataDir" style="margin-top: 10px;"></div>
          <div class="muted" id="runtime" style="margin-top: 6px;"></div>
        </div>
        <div class="card">
          <h2>Quick Actions</h2>
          <div class="grid2">
            <button onclick="quick('daily_brief', {confirm:true})">Daily Brief</button>
            <button onclick="quick('now_playing', {})">Now Playing</button>
            <button onclick="quick('play_music', {})">Play</button>
            <button onclick="quick('pause_music', {})">Pause</button>
          </div>
          <div class="grid2" style="margin-top: 10px;">
            <button onclick="runtimeStart('standalone')">Start Standalone</button>
            <button onclick="runtimeStart('livekit')">Start LiveKit</button>
            <button onclick="runtimeStop()">Stop Voice</button>
            <button onclick="refreshStatus()">Refresh Status</button>
          </div>
          <div style="margin-top: 10px;">
            <input id="notifyTitle" placeholder="Notification title" value="J.A.R.V.I.S" />
            <input id="notifyMsg" placeholder="Notification message" style="margin-top: 8px;" />
            <button style="margin-top: 8px;" onclick="notify()">Send Notification</button>
          </div>
        </div>
      </div>

      <div class="row" style="margin-top: 12px;">
        <div class="card">
          <h2>Run Tool</h2>
          <select id="toolSelect"></select>
          <textarea id="toolArgs" placeholder='{"arg":"value"}'></textarea>
          <input id="uiToken" placeholder="JARVIS_UI_TOKEN" />
          <button onclick="runSelected()">Run</button>
          <div class="muted" style="margin-top: 8px;">Tip: include <code>confirm:true</code> when required.</div>
        </div>
        <div class="card">
          <h2>Output</h2>
          <pre id="output"></pre>
          <h2 style="margin-top: 14px;">Audit</h2>
          <button onclick="refreshAudit()">Refresh Audit</button>
          <pre id="audit" style="margin-top: 8px;"></pre>
        </div>
      </div>
    </div>
    <script>
      async function api(path, opts={}) {
        const res = await fetch(path, opts);
        const data = await res.json().catch(()=>({}));
        if (!res.ok) throw new Error(data.detail || res.statusText);
        return data;
      }
      function pill(name, ok) {
        return `<span class="pill"><span class="dot ${ok?'ok':'bad'}"></span>${name}</span>`;
      }
      async function loadStatus() {
        const data = await api('/api/status');
        const providers = data.providers || {};
        let html = '';
        for (const [k,v] of Object.entries(providers)) html += pill(k, !!v);
        document.getElementById('statusPills').innerHTML = html;
        document.getElementById('dataDir').textContent = 'Data dir: ' + data.paths.data_dir;
        const rt = data.runtime || {};
        document.getElementById('runtime').textContent = rt.running ? ('Voice: ' + rt.mode + ' (pid ' + rt.pid + ')') : 'Voice: stopped';
      }
      async function loadTools() {
        const data = await api('/api/tools');
        const select = document.getElementById('toolSelect');
        select.innerHTML = '';
        for (const t of data.tools) {
          const opt = document.createElement('option');
          opt.value = t.name;
          opt.textContent = t.name;
          select.appendChild(opt);
        }
      }
      function setOutput(text) { document.getElementById('output').textContent = text || ''; }
      async function runTool(name, args) {
        const token = document.getElementById('uiToken').value;
        const data = await api('/api/tool/' + name, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Jarvis-Token': token },
          body: JSON.stringify({ args })
        });
        setOutput(data.result);
      }
      async function runSelected() {
        const name = document.getElementById('toolSelect').value;
        let args = {};
        try { args = JSON.parse(document.getElementById('toolArgs').value || '{}'); }
        catch (e) { return setOutput('Invalid JSON args: ' + e); }
        try { await runTool(name, args); }
        catch (e) { setOutput('Error: ' + e.message); }
      }
      async function quick(name, args) {
        try { await runTool(name, args); }
        catch (e) { setOutput('Error: ' + e.message); }
      }
      async function notify() {
        const title = document.getElementById('notifyTitle').value;
        const message = document.getElementById('notifyMsg').value;
        await quick('send_notification', { title, message });
      }
      async function refreshAudit() {
        const data = await api('/api/audit');
        document.getElementById('audit').textContent = data.content || '';
      }
      async function refreshStatus() {
        try { await loadStatus(); } catch(e) {}
      }
      async function runtimeStart(mode) {
        const token = document.getElementById('uiToken').value;
        try {
          const data = await api('/api/runtime/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Jarvis-Token': token },
            body: JSON.stringify({ mode, confirm: true })
          });
          setOutput(JSON.stringify(data, null, 2));
          await refreshStatus();
        } catch(e) { setOutput('Error: ' + e.message); }
      }
      async function runtimeStop() {
        const token = document.getElementById('uiToken').value;
        try {
          const data = await api('/api/runtime/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Jarvis-Token': token },
            body: JSON.stringify({ confirm: true })
          });
          setOutput(JSON.stringify(data, null, 2));
          await refreshStatus();
        } catch(e) { setOutput('Error: ' + e.message); }
      }
      (async function init() {
        await loadStatus();
        await loadTools();
        await refreshAudit();
      })();
    </script>
  </body>
</html>"""


def main() -> None:
    import uvicorn

    host = os.getenv("JARVIS_UI_HOST", "127.0.0.1")
    port = int(os.getenv("JARVIS_UI_PORT", "8080"))
    uvicorn.run("jarvis.ui.server:create_app", host=host, port=port, factory=True)
