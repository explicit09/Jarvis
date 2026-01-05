"""Hub mode for distributed J.A.R.V.I.S.

Enables:
- Auto-discovery via UDP broadcast
- Client registration
- Multi-device support (iPhone, iPad, Raspberry Pi, etc.)
"""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

HUB_PORT = 18000
BROADCAST_PORT = 18001
BROADCAST_INTERVAL = 5.0  # seconds


@dataclass
class ClientInfo:
    """Information about a connected client."""
    device_id: str
    device_type: str
    ip_address: str
    last_seen: float = field(default_factory=time.time)
    capabilities: list[str] = field(default_factory=list)


class HubManager:
    """Manages hub discovery and client connections."""

    def __init__(self):
        self.is_hub = self._detect_hub_capability()
        self.local_ip = self._get_local_ip()
        self.clients: Dict[str, ClientInfo] = {}
        self._broadcast_task: Optional[asyncio.Task] = None

    def _detect_hub_capability(self) -> bool:
        """Determine if this machine should act as a hub."""
        if platform.system() != "Darwin":
            return True  # Default to hub on non-Mac

        try:
            # Check CPU cores
            cores = int(subprocess.check_output(
                ["sysctl", "-n", "hw.ncpu"],
                stderr=subprocess.DEVNULL
            ).strip())

            # Check if on AC power
            power = subprocess.check_output(
                ["pmset", "-g", "batt"],
                stderr=subprocess.DEVNULL
            ).decode()
            on_ac = "AC Power" in power or "charged" in power.lower()

            # Hub if: 4+ cores and on AC power (or desktop Mac)
            is_desktop = "Mac mini" in platform.node() or "Mac Pro" in platform.node()
            return cores >= 4 and (on_ac or is_desktop)

        except Exception:
            return True  # Default to hub

    def _get_local_ip(self) -> str:
        """Get local network IP address."""
        try:
            # Create a dummy socket to get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    async def broadcast_presence(self):
        """Broadcast hub availability on local network."""
        while True:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.setblocking(False)

                message = json.dumps({
                    "service": "jarvis-hub",
                    "ip": self.local_ip,
                    "port": HUB_PORT,
                    "capabilities": ["asr", "tts", "llm", "tools", "music", "home"],
                    "clients": len(self.clients),
                }).encode()

                sock.sendto(message, ('<broadcast>', BROADCAST_PORT))
                sock.close()

                logger.debug(f"Hub broadcast sent: {self.local_ip}:{HUB_PORT}")

            except Exception as e:
                logger.debug(f"Broadcast error (expected on some networks): {e}")

            await asyncio.sleep(BROADCAST_INTERVAL)

    def start_broadcast(self):
        """Start the broadcast task."""
        if self._broadcast_task is None or self._broadcast_task.done():
            self._broadcast_task = asyncio.create_task(self.broadcast_presence())
            logger.info(f"Hub broadcast started at {self.local_ip}:{HUB_PORT}")

    def stop_broadcast(self):
        """Stop the broadcast task."""
        if self._broadcast_task and not self._broadcast_task.done():
            self._broadcast_task.cancel()

    def register_client(self, client_id: str, client_info: Dict[str, Any]) -> None:
        """Register a client device."""
        self.clients[client_id] = ClientInfo(
            device_id=client_id,
            device_type=client_info.get("device_type", "unknown"),
            ip_address=client_info.get("ip_address", "unknown"),
            capabilities=client_info.get("capabilities", []),
        )
        logger.info(f"Client registered: {client_id} ({client_info.get('device_type', 'unknown')})")

    def unregister_client(self, client_id: str) -> None:
        """Unregister a client device."""
        if client_id in self.clients:
            del self.clients[client_id]
            logger.info(f"Client unregistered: {client_id}")

    def update_client(self, client_id: str) -> None:
        """Update last seen time for a client."""
        if client_id in self.clients:
            self.clients[client_id].last_seen = time.time()

    def get_hub_info(self) -> Dict[str, Any]:
        """Get hub information for clients."""
        return {
            "hub_ip": self.local_ip,
            "hub_port": HUB_PORT,
            "is_hub": self.is_hub,
            "capabilities": {
                "asr": True,
                "tts": True,
                "llm": True,
                "tools": True,
                "music": True,
                "home": True,
                "timers": True,
            },
            "clients_connected": len(self.clients),
            "clients": [
                {
                    "device_id": c.device_id,
                    "device_type": c.device_type,
                    "last_seen": c.last_seen,
                }
                for c in self.clients.values()
            ]
        }

    def cleanup_stale_clients(self, max_age: float = 300.0):
        """Remove clients not seen in max_age seconds."""
        now = time.time()
        stale = [
            cid for cid, c in self.clients.items()
            if now - c.last_seen > max_age
        ]
        for cid in stale:
            self.unregister_client(cid)


class ClientManager:
    """Manages client connections to a hub."""

    def __init__(self):
        self.hub_url: Optional[str] = None
        self.device_id = self._get_device_id()

    def _get_device_id(self) -> str:
        """Get unique device identifier."""
        import hashlib
        info = f"{platform.node()}-{platform.system()}-{platform.machine()}"
        return hashlib.md5(info.encode()).hexdigest()[:8]

    async def discover_hub(self, timeout: float = 3.0) -> Optional[str]:
        """Discover hub on local network via UDP broadcast."""
        import select

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            sock.bind(('', BROADCAST_PORT))
            sock.setblocking(False)

            logger.info("Searching for J.A.R.V.I.S hub...")

            start = time.time()
            while time.time() - start < timeout:
                ready = select.select([sock], [], [], 0.1)
                if ready[0]:
                    try:
                        data, addr = sock.recvfrom(1024)
                        msg = json.loads(data.decode())
                        if msg.get("service") == "jarvis-hub":
                            hub_url = f"http://{msg['ip']}:{msg['port']}"
                            logger.info(f"Found hub at {hub_url}")
                            self.hub_url = hub_url
                            return hub_url
                    except Exception:
                        pass

        finally:
            sock.close()

        # Try known endpoints as fallback
        import httpx
        endpoints = [
            "http://jarvis.local:18000",
            "http://localhost:18000",
        ]

        async with httpx.AsyncClient(timeout=1.0) as client:
            for endpoint in endpoints:
                try:
                    resp = await client.get(f"{endpoint}/healthz")
                    if resp.status_code == 200:
                        logger.info(f"Found hub at {endpoint}")
                        self.hub_url = endpoint
                        return endpoint
                except Exception:
                    pass

        logger.info("No hub found, running in standalone mode")
        return None

    async def forward_to_hub(self, endpoint: str, data: Any) -> Optional[Dict]:
        """Forward request to hub for processing."""
        if not self.hub_url:
            return None

        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.hub_url}{endpoint}",
                    json=data,
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.warning(f"Hub forwarding failed: {e}")
            # Try to rediscover hub
            self.hub_url = await self.discover_hub()

        return None


# Global instances
hub_manager = HubManager()
client_manager = ClientManager()


def setup_hub_mode(app: "FastAPI"):
    """Configure FastAPI app for hub mode."""
    from fastapi import Request

    @app.get("/hub/info")
    async def hub_info():
        """Get hub information."""
        return hub_manager.get_hub_info()

    @app.post("/hub/register")
    async def register_client(request: Request):
        """Register a client device."""
        data = await request.json()
        client_id = data.get("device_id", "unknown")

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        data["ip_address"] = client_ip

        hub_manager.register_client(client_id, data)
        return {"ok": True, "hub_info": hub_manager.get_hub_info()}

    @app.post("/hub/heartbeat")
    async def client_heartbeat(request: Request):
        """Update client last seen time."""
        data = await request.json()
        client_id = data.get("device_id")
        if client_id:
            hub_manager.update_client(client_id)
        return {"ok": True}

    @app.delete("/hub/unregister/{client_id}")
    async def unregister_client(client_id: str):
        """Unregister a client device."""
        hub_manager.unregister_client(client_id)
        return {"ok": True}

    @app.get("/hub/discover")
    async def discover():
        """Endpoint for client discovery."""
        return {
            "hub": True,
            "ip": hub_manager.local_ip,
            "port": HUB_PORT,
        }

    # Start hub broadcast if we're a hub
    @app.on_event("startup")
    async def start_hub():
        if hub_manager.is_hub:
            hub_manager.start_broadcast()
            logger.info(f"Hub mode active at {hub_manager.local_ip}:{HUB_PORT}")

    @app.on_event("shutdown")
    async def stop_hub():
        hub_manager.stop_broadcast()
