#!/usr/bin/env python3
"""
iOS client for J.A.R.V.I.S - Run via Pythonista or as a Shortcut script.

Usage:
    # Find hub
    python ios_client.py find_hub

    # Send text command
    python ios_client.py send_text "What's the weather?"

    # Send audio file
    python ios_client.py send_audio recording.wav

For iOS Shortcuts integration:
    1. Install Pythonista app
    2. Copy this script to Pythonista
    3. Create a Shortcut that runs this script
"""

from __future__ import annotations

import json
import os
import socket
import sys
from typing import Optional

# Try to import requests
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    try:
        # Fallback for Pythonista
        from urllib import request, error
        import ssl
        REQUESTS_AVAILABLE = False
    except ImportError:
        print("Neither requests nor urllib available")
        sys.exit(1)


class JarvisClient:
    """Client for connecting to J.A.R.V.I.S hub."""

    # Known endpoints to try
    ENDPOINTS = [
        "http://jarvis.local:18000",      # Home network (mDNS)
        "http://192.168.1.100:18000",     # Common home IP
        "http://192.168.0.100:18000",     # Alternative home IP
        "http://10.0.1.5:18000",          # School/work network
        "http://localhost:18000",          # Local testing
        # Add your Cloudflare tunnel URL here:
        # "https://jarvis.yourdomain.com",
    ]

    BROADCAST_PORT = 18001

    def __init__(self):
        self.active_endpoint: Optional[str] = None
        self.session_id = self._get_session_id()

    def _get_session_id(self) -> str:
        """Get unique session ID for this device."""
        try:
            import platform
            import hashlib
            info = f"ios-{platform.node()}"
            return hashlib.md5(info.encode()).hexdigest()[:8]
        except Exception:
            return "ios-client"

    def _http_get(self, url: str, timeout: float = 2.0) -> Optional[dict]:
        """HTTP GET request."""
        if REQUESTS_AVAILABLE:
            try:
                resp = requests.get(url, timeout=timeout)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
        else:
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = request.Request(url)
                with request.urlopen(req, timeout=timeout, context=ctx) as resp:
                    if resp.status == 200:
                        return json.loads(resp.read().decode())
            except Exception:
                pass
        return None

    def _http_post(self, url: str, data: dict, timeout: float = 30.0) -> Optional[dict]:
        """HTTP POST request with JSON."""
        if REQUESTS_AVAILABLE:
            try:
                resp = requests.post(url, json=data, timeout=timeout)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
        else:
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = request.Request(
                    url,
                    data=json.dumps(data).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}
                )
                with request.urlopen(req, timeout=timeout, context=ctx) as resp:
                    if resp.status == 200:
                        return json.loads(resp.read().decode())
            except Exception:
                pass
        return None

    def _http_post_file(self, url: str, filepath: str, timeout: float = 30.0) -> Optional[dict]:
        """HTTP POST with file upload."""
        if REQUESTS_AVAILABLE:
            try:
                with open(filepath, 'rb') as f:
                    files = {'audio': ('audio.wav', f, 'audio/wav')}
                    resp = requests.post(url, files=files, timeout=timeout)
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                print(f"Error: {e}")
        else:
            print("File upload requires 'requests' package")
        return None

    def discover_hub(self) -> Optional[str]:
        """Discover hub via UDP broadcast."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', self.BROADCAST_PORT))
            sock.settimeout(3.0)

            print("Listening for hub broadcast...")

            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                if msg.get("service") == "jarvis-hub":
                    hub_url = f"http://{msg['ip']}:{msg['port']}"
                    print(f"Found hub via broadcast: {hub_url}")
                    return hub_url
            except socket.timeout:
                pass
            finally:
                sock.close()

        except Exception as e:
            print(f"Broadcast discovery failed: {e}")

        return None

    def find_hub(self) -> Optional[str]:
        """Find the best available J.A.R.V.I.S hub."""
        # Try broadcast first
        hub = self.discover_hub()
        if hub:
            self.active_endpoint = hub
            return hub

        # Try known endpoints
        print("Trying known endpoints...")
        for endpoint in self.ENDPOINTS:
            result = self._http_get(f"{endpoint}/healthz", timeout=1.0)
            if result and result.get("ok"):
                print(f"Found hub at {endpoint}")
                self.active_endpoint = endpoint
                return endpoint

        print("No hub found")
        return None

    def send_text(self, text: str) -> str:
        """Send text command to hub."""
        if not self.active_endpoint:
            self.find_hub()

        if not self.active_endpoint:
            return "No J.A.R.V.I.S hub available"

        result = self._http_post(
            f"{self.active_endpoint}/chat",
            {"text": text, "session_id": self.session_id}
        )

        if result:
            return result.get("response", "No response")
        return "Failed to get response"

    def send_audio(self, audio_file: str) -> dict:
        """Send audio to hub for processing."""
        if not self.active_endpoint:
            self.find_hub()

        if not self.active_endpoint:
            return {"error": "No J.A.R.V.I.S hub available"}

        result = self._http_post_file(
            f"{self.active_endpoint}/voice/ptt?session_id={self.session_id}",
            audio_file
        )

        return result or {"error": "Failed to process audio"}

    def get_hub_info(self) -> dict:
        """Get hub information."""
        if not self.active_endpoint:
            self.find_hub()

        if not self.active_endpoint:
            return {"error": "No hub found"}

        return self._http_get(f"{self.active_endpoint}/hub/info") or {"error": "Failed to get info"}

    def register(self) -> dict:
        """Register this client with the hub."""
        if not self.active_endpoint:
            self.find_hub()

        if not self.active_endpoint:
            return {"error": "No hub found"}

        result = self._http_post(
            f"{self.active_endpoint}/hub/register",
            {
                "device_id": self.session_id,
                "device_type": "ios",
                "capabilities": ["voice", "text"],
            }
        )

        return result or {"error": "Failed to register"}


def main():
    """CLI interface."""
    client = JarvisClient()

    if len(sys.argv) < 2:
        # Interactive mode
        print("J.A.R.V.I.S iOS Client")
        print("-" * 30)

        hub = client.find_hub()
        if hub:
            print(f"Connected to: {hub}")
            client.register()
        else:
            print("No hub found. Running in offline mode.")
            return

        print("\nType 'quit' to exit\n")

        while True:
            try:
                text = input("> ").strip()
                if text.lower() in ['quit', 'exit', 'q']:
                    break
                if not text:
                    continue

                response = client.send_text(text)
                print(f"\n{response}\n")

            except KeyboardInterrupt:
                break
            except EOFError:
                break

        print("\nGoodbye!")
        return

    # Command mode
    command = sys.argv[1].lower()

    if command == "find_hub":
        hub = client.find_hub()
        print(hub if hub else "No hub found")

    elif command == "hub_info":
        info = client.get_hub_info()
        print(json.dumps(info, indent=2))

    elif command == "register":
        result = client.register()
        print(json.dumps(result, indent=2))

    elif command == "send_text":
        if len(sys.argv) < 3:
            print("Usage: ios_client.py send_text <message>")
            sys.exit(1)
        text = " ".join(sys.argv[2:])
        response = client.send_text(text)
        print(response)

    elif command == "send_audio":
        if len(sys.argv) < 3:
            print("Usage: ios_client.py send_audio <audio_file>")
            sys.exit(1)
        audio_file = sys.argv[2]
        if not os.path.exists(audio_file):
            print(f"File not found: {audio_file}")
            sys.exit(1)
        result = client.send_audio(audio_file)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {command}")
        print("\nCommands:")
        print("  find_hub    - Find J.A.R.V.I.S hub")
        print("  hub_info    - Get hub information")
        print("  register    - Register this client")
        print("  send_text   - Send text command")
        print("  send_audio  - Send audio file")
        sys.exit(1)


if __name__ == "__main__":
    main()
