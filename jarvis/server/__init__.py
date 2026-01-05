"""HTTP API Server for J.A.R.V.I.S.

Provides REST endpoints for remote access:
- /voice/ptt - Push-to-talk voice processing
- /chat - Text chat with LLM
- /speak - Text-to-speech
- /healthz - Health check
"""

# Lazy imports to avoid requiring FastAPI when just importing submodules
def __getattr__(name):
    if name == "app":
        from .app import app
        return app
    elif name == "run_server":
        from .app import run_server
        return run_server
    elif name == "main":
        from .app import main
        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["app", "run_server", "main"]
