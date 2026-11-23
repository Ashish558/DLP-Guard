"""Attaches to the browser over DevTools, injects the gate script into ChatGPT /
Perplexity tabs, and answers its questions using the Guard (inspection + dialog).

Flow for one prompt/file:
  page JS -> binding call (chunks) -> `_on_binding` -> Guard (OCR/dialog in a worker
  thread) -> `Runtime.evaluate` of the page's reply function -> page JS continues.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import secrets
import threading
from urllib.parse import urlparse

import websockets

from ..guard import Guard
from ..sites import DEFAULT_SITES, Site, site_for_host
from .cdp import CdpError, Connection, browser_ws_url
from .inject import build_script
from .launcher import DEFAULT_PORT

log = logging.getLogger(__name__)

BINDING = "dlpGuardCall"


class BrowserController:
    def __init__(self, guard: Guard, sites: tuple[Site, ...] = DEFAULT_SITES, *,
                 port: int = DEFAULT_PORT, fail_mode: str = "block") -> None:
        self._guard = guard
        self._sites = sites
        self._port = port
        self._token = secrets.token_hex(16)
        self._reply = "__dlpReply_" + secrets.token_hex(6)
        self._script = build_script(sites, token=self._token, binding=BINDING,
                                    reply=self._reply, fail_mode=fail_mode)
        self._conn: Connection | None = None
        self._urls: dict[str, str] = {}              # targetId -> current url
        self._sessions: dict[str, str] = {}          # sessionId -> targetId
        self._partial: dict[tuple[str, int], list] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self.connected = threading.Event()

    # ------------------------------------------------------------------ run
    def start(self) -> None:
        """Run the controller on a background thread."""
        self._thread = threading.Thread(target=self._thread_main, daemon=True, name="cdp")
        self._thread.start()

    def stop(self) -> None:
        loop = self._loop
        if not loop or loop.is_closed():
            return

        async def shutdown() -> None:
            if self._conn:
                await self._conn.close()
            for task in asyncio.all_tasks(loop):
                if task is not asyncio.current_task():
                    task.cancel()
            await asyncio.sleep(0)
            loop.stop()

        asyncio.run_coroutine_threadsafe(shutdown(), loop)
        if self._thread:
            self._thread.join(timeout=3)

    def _thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.create_task(self.run_forever())
        self._loop.run_forever()

    async def run_forever(self) -> None:
        """Connect, attach to every tab, and reconnect whenever the browser restarts."""
        while True:
            try:
                url = await asyncio.to_thread(browser_ws_url, self._port)
                self._conn = await Connection.connect(url, self._on_event)
                await self._conn.send("Target.setDiscoverTargets", {"discover": True})
                await self._conn.send("Target.setAutoAttach", {
                    "autoAttach": True, "waitForDebuggerOnStart": True, "flatten": True})
                log.info("attached to browser on port %s", self._port)
                self.connected.set()
                await self._conn.wait_closed()
                log.info("browser connection closed")
            except (OSError, CdpError, websockets.WebSocketException):
                pass                                  # browser not up yet; retry
            except Exception:  # noqa: BLE001
                log.exception("controller error")
            self.connected.clear()
            self._conn = None
            self._urls.clear()
            self._sessions.clear()
            self._partial.clear()
            await asyncio.sleep(1.5)

    # --------------------------------------------------------------- events
    async def _on_event(self, method: str, params: dict, session: str | None) -> None:
        if method == "Target.attachedToTarget":
            await self._on_attached(params)
        elif method == "Target.targetInfoChanged":
            info = params["targetInfo"]
            self._urls[info["targetId"]] = info.get("url", "")
        elif method == "Target.detachedFromTarget":
            self._sessions.pop(params.get("sessionId", ""), None)
        elif method == "Runtime.bindingCalled" and session:
            await self._on_binding(params, session)

    async def _on_attached(self, p: dict) -> None:
        assert self._conn
        sid, info = p["sessionId"], p["targetInfo"]
        waiting = p.get("waitingForDebugger", False)
        try:
            if info["type"] != "page":
                if waiting:
                    await self._conn.send("Runtime.runIfWaitingForDebugger", session=sid)
                await self._conn.send("Target.detachFromTarget", {"sessionId": sid})
                return
            self._sessions[sid] = info["targetId"]
            self._urls[info["targetId"]] = info.get("url", "")
            await self._conn.send("Runtime.enable", session=sid)
            await self._conn.send("Runtime.addBinding", {"name": BINDING}, sid)
            await self._conn.send("Page.enable", session=sid)
            await self._conn.send("Page.addScriptToEvaluateOnNewDocument",
                                  {"source": self._script, "runImmediately": True}, sid)
            if waiting:
                await self._conn.send("Runtime.runIfWaitingForDebugger", session=sid)
        except CdpError as exc:
            log.debug("attach failed for %s: %s", info.get("url"), exc)

    async def _on_binding(self, p: dict, sid: str) -> None:
        if p.get("name") != BINDING:
            return
        try:
            m = json.loads(p["payload"])
        except (ValueError, KeyError):
            return
        if m.get("t") != self._token:
            return
        host = urlparse(self._urls.get(self._sessions.get(sid, ""), "")).hostname or ""
        site = site_for_host(host, self._sites)
        if site is None:                               # message from a tab we do not guard
            return

        key = (sid + ":" + site.name, m["id"])
        parts = self._partial.setdefault(key, [None] * int(m["total"]))
        parts[int(m["seq"])] = m.get("data", "")
        if any(x is None for x in parts):
            return
        del self._partial[key]
        await self._reply_to(sid, m["id"], "ack")      # tell the page we have it
        data = "".join(parts)
        asyncio.ensure_future(self._decide_and_reply(sid, m["id"], m["kind"], site.name,
                                                      m.get("name", ""), data))

    async def _decide_and_reply(self, sid: str, req_id: int, kind: str, site: str,
                                name: str, data: str) -> None:
        loop = asyncio.get_running_loop()
        try:
            if kind == "prompt":
                decision = await loop.run_in_executor(None, self._guard.check_prompt, site, data)
            else:
                raw = base64.b64decode(data)
                decision = await loop.run_in_executor(None, self._guard.check_file, site, name, raw)
            action = decision.action
        except Exception:  # noqa: BLE001 - anything unexpected is a block
            log.exception("inspection failed")
            action = "block"
        await self._reply_to(sid, req_id, action)

    async def _reply_to(self, sid: str, req_id: int, action: str) -> None:
        if not self._conn:
            return
        expr = f"window.{self._reply}({int(req_id)},{json.dumps(action)})"
        try:
            await self._conn.send("Runtime.evaluate", {"expression": expr}, sid)
        except CdpError:
            log.debug("tab went away before the reply could be delivered")
