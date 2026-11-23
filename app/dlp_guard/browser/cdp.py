"""Minimal Chrome DevTools Protocol client (JSON over a WebSocket)."""
from __future__ import annotations

import asyncio
import json
import urllib.request
from typing import Any, Awaitable, Callable

import websockets

EventHandler = Callable[[str, dict, str | None], Awaitable[None] | None]


class CdpError(RuntimeError):
    pass


def browser_ws_url(port: int, timeout: float = 2.0) -> str:
    """Ask the browser's HTTP endpoint for its DevTools WebSocket URL."""
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=timeout) as r:
        return json.load(r)["webSocketDebuggerUrl"]


class Connection:
    def __init__(self, ws: Any, on_event: EventHandler) -> None:
        self._ws = ws
        self._on_event = on_event
        self._next_id = 0
        self._waiting: dict[int, asyncio.Future] = {}
        self._reader = asyncio.ensure_future(self._read_loop())

    @classmethod
    async def connect(cls, url: str, on_event: EventHandler) -> "Connection":
        ws = await websockets.connect(url, max_size=None, ping_interval=None)
        return cls(ws, on_event)

    async def send(self, method: str, params: dict | None = None, session: str | None = None) -> dict:
        self._next_id += 1
        msg: dict = {"id": self._next_id, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        fut = asyncio.get_running_loop().create_future()
        self._waiting[self._next_id] = fut
        await self._ws.send(json.dumps(msg))
        return await fut

    async def _read_loop(self) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if "id" in msg:
                    fut = self._waiting.pop(msg["id"], None)
                    if fut and not fut.done():
                        if "error" in msg:
                            fut.set_exception(CdpError(f'{msg["error"].get("message")}'))
                        else:
                            fut.set_result(msg.get("result", {}))
                elif "method" in msg:
                    res = self._on_event(msg["method"], msg.get("params", {}), msg.get("sessionId"))
                    if asyncio.iscoroutine(res):
                        asyncio.ensure_future(res)
        except websockets.ConnectionClosed:
            pass
        finally:
            for fut in self._waiting.values():
                if not fut.done():
                    fut.set_exception(CdpError("connection closed"))
            self._waiting.clear()

    async def wait_closed(self) -> None:
        await self._reader

    async def close(self) -> None:
        await self._ws.close()
