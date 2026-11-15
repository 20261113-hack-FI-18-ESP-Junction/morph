"""Small bounded loopback HTTP surface; no camera or publisher control routes."""
from __future__ import annotations

import asyncio
import hmac
import json

from .config import Config, private_token
from .frames import Stats


class StatusServer:
    def __init__(self, config: Config, stats: Stats):
        self.config, self.stats = config, stats
        self.token = private_token(config.status_token_file)
        self.server: asyncio.Server | None = None
        self.clients: set[asyncio.Task] = set()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, self.config.status_host, self.config.status_port,
                                                 limit=8192, backlog=8)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task
        if len(self.clients) >= 8:
            writer.close()
            return
        self.clients.add(task)
        code, body = 400, {"error": "invalid_request"}
        try:
            raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 2)
            if len(raw) > 8192:
                raise ValueError("Headers too large")
            lines = raw.decode("ascii").split("\r\n")
            method, target, protocol = lines[0].split(" ")
            if protocol not in ("HTTP/1.0", "HTTP/1.1"):
                raise ValueError("Invalid protocol")
            headers: dict[str, str] = {}
            for line in lines[1:]:
                if not line:
                    continue
                key, value = line.split(":", 1)
                key = key.lower()
                if key in headers:
                    raise ValueError("Repeated header")
                headers[key] = value.strip()
            if method != "GET":
                code, body = 405, {"error": "method_not_allowed"}
            elif target == "/health":
                code, body = 200, {"status": "ok"}
            elif target == "/api/media/v1/status":
                if hmac.compare_digest(headers.get("authorization", ""), "Bearer " + self.token):
                    code, body = 200, self.stats.status()
                else:
                    code, body = 401, {"error": "unauthorized"}
            else:
                code, body = 404, {"error": "not_found"}
        except (ValueError, UnicodeError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, TimeoutError):
            pass
        except asyncio.CancelledError:
            writer.close()
            raise
        finally:
            self.clients.discard(task)
        encoded = json.dumps(body, separators=(",", ":"), allow_nan=False).encode()
        try:
            writer.write(f"HTTP/1.1 {code} Response\r\nContent-Type: application/json\r\nContent-Length: {len(encoded)}\r\nCache-Control: no-store\r\nConnection: close\r\nX-Content-Type-Options: nosniff\r\n\r\n".encode() + encoded)
            await asyncio.wait_for(writer.drain(), 1)
        except (OSError, TimeoutError):
            pass
        finally:
            writer.close()

    async def close(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        clients = list(self.clients)
        for task in clients:
            task.cancel()
        await asyncio.gather(*clients, return_exceptions=True)
