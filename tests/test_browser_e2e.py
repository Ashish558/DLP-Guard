"""End-to-end: real headless Edge/Chrome + the real controller, JS gates and Guard.

A local fake chat page stands in for ChatGPT; a fake dialog stands in for the
native one (its answers are scripted). Input is injected with real DevTools input
events, so the page sees trusted key presses and real file selections.
"""
import asyncio
import json
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from dlp_guard.audit import AuditLog
from dlp_guard.browser import BrowserController, find_browser, is_debuggable, launch
from dlp_guard.browser.cdp import Connection, browser_ws_url
from dlp_guard.guard import Guard
from dlp_guard.sites import Site

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

PAGE = """<!doctype html><html><body>
<textarea id="box"></textarea>
<button aria-label="Send message" id="send" type="button">send</button>
<input type="file" id="file" multiple>
<div data-message-author-role="assistant"><p>an answer</p></div>
<script>
  window.__sent = []; window.__files = [];
  document.getElementById('send').addEventListener('click', () => {
    window.__sent.push(document.getElementById('box').value);
  });
  document.getElementById('box').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); document.getElementById('send').click(); }
  });
  document.getElementById('file').addEventListener('change', (e) => {
    window.__files.push(Array.from(e.target.files).map(f => f.name));
  });
</script></body></html>"""


class _Page(BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class FakeDialog:
    def __init__(self):
        self.answers = []
        self.calls = []

    def confirm(self, c):
        self.calls.append((c.kind, c.name))
        return self.answers.pop(0) if self.answers else False


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def wait_for(pred, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        if await pred():
            return True
        await asyncio.sleep(0.1)
    return False


@pytest.mark.skipif(find_browser() is None, reason="Edge/Chrome not installed")
def test_gates_against_real_browser(tmp_path):
    srv = HTTPServer(("127.0.0.1", 0), _Page)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    page_url = f"http://127.0.0.1:{srv.server_address[1]}/"
    site = Site(name="TestChat", hosts=("127.0.0.1",), start_url=page_url,
                send_button=('button[aria-label="Send message"]',),
                assistant_message=('[data-message-author-role="assistant"]',))

    dialog = FakeDialog()
    guard = Guard(dialog, AuditLog(tmp_path / "audit.jsonl"))
    port = free_port()
    profile = Path(tempfile.mkdtemp(prefix="dlp-e2e-"))
    proc = launch(page_url, port=port, profile=profile, headless=True)
    controller = BrowserController(guard, (site,), port=port)
    try:
        for _ in range(100):
            if is_debuggable(port):
                break
            time.sleep(0.1)
        assert is_debuggable(port), "browser did not start"
        controller.start()
        assert controller.connected.wait(15)
        asyncio.run(_scenario(port, dialog))
    finally:
        controller.stop()
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        srv.shutdown()
        shutil.rmtree(profile, ignore_errors=True)


async def _scenario(port, dialog):
    conn = await Connection.connect(browser_ws_url(port), lambda *a: None)
    targets = (await conn.send("Target.getTargets"))["targetInfos"]
    target = next(t for t in targets if t["type"] == "page")
    sid = (await conn.send("Target.attachToTarget", {"targetId": target["targetId"], "flatten": True}))["sessionId"]

    async def ev(expr):
        r = await conn.send("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                                 "awaitPromise": True}, sid)
        return r.get("result", {}).get("value")

    async def type_and_enter(text):
        await ev("document.getElementById('box').value=''; document.getElementById('box').focus()")
        await conn.send("Input.insertText", {"text": text}, sid)
        for t in ("keyDown", "keyUp"):
            await conn.send("Input.dispatchKeyEvent", {
                "type": t, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13,
                "text": "\r" if t == "keyDown" else ""}, sid)

    async def sent():
        return await ev("window.__sent.length")

    assert await wait_for(lambda: ev("!!window.__dlpGuardInstalled")), "script was not injected"

    # 1. clean prompt: goes through, no dialog
    await type_and_enter("hello there")
    assert await wait_for(lambda: _eq(sent(), 1))
    assert dialog.calls == []

    # 2. marker prompt + Cancel: nothing sent, text stays
    dialog.answers = [False]
    await type_and_enter("this is WALLED_SENSITIVE text")
    assert await wait_for(lambda: _truthy(lambda: len(dialog.calls) == 1))
    await asyncio.sleep(0.5)
    assert await sent() == 1
    assert await ev("document.getElementById('box').value") == "this is WALLED_SENSITIVE text"
    assert dialog.calls[0][0] == "prompt"

    # 3. same, Continue: sent unchanged
    dialog.answers = [True]
    await ev("document.getElementById('box').focus()")
    for t in ("keyDown", "keyUp"):
        await conn.send("Input.dispatchKeyEvent", {"type": t, "key": "Enter", "code": "Enter",
                                                   "windowsVirtualKeyCode": 13,
                                                   "text": "\r" if t == "keyDown" else ""}, sid)
    assert await wait_for(lambda: _eq(sent(), 2))
    assert await ev("window.__sent[1]") == "this is WALLED_SENSITIVE text"

    # 4. files: select txt (sensitive, cancel), png (sensitive, continue), clean txt, scanned pdf
    doc = await conn.send("DOM.getDocument", {}, sid)
    node = (await conn.send("DOM.querySelector", {"nodeId": doc["root"]["nodeId"],
                                                  "selector": "#file"}, sid))["nodeId"]

    async def pick(*names):
        await conn.send("DOM.setFileInputFiles",
                        {"nodeId": node, "files": [str(FIXTURES / n) for n in names]}, sid)

    dialog.calls.clear()
    dialog.answers = [False]
    await pick("sensitive.txt")
    assert await wait_for(lambda: _truthy(lambda: len(dialog.calls) == 1))
    await asyncio.sleep(0.5)
    assert await ev("window.__files.length") == 0
    assert dialog.calls == [("file", "sensitive.txt")]

    dialog.calls.clear()
    dialog.answers = [True]
    await pick("sensitive.png")
    assert await wait_for(lambda: _eq(ev("window.__files.length"), 1), 30)
    assert await ev("window.__files[0]") == ["sensitive.png"]

    dialog.calls.clear()
    await pick("clean.txt")
    assert await wait_for(lambda: _eq(ev("window.__files.length"), 2))
    assert dialog.calls == []

    # mixed batch: only the clean and the approved files reach the page
    dialog.calls.clear()
    dialog.answers = [False]
    await pick("clean.pdf", "sensitive_scanned.pdf", "clean.png")
    assert await wait_for(lambda: _eq(ev("window.__files.length"), 3), 40)
    assert sorted(await ev("window.__files[2]")) == ["clean.pdf", "clean.png"]
    assert dialog.calls == [("file", "sensitive_scanned.pdf")]

    # 5. response recolor
    color = await ev("getComputedStyle(document.querySelector('[data-message-author-role] p')).color")
    assert color == "rgb(232, 89, 12)"
    await conn.close()


async def _eq(coro, value):
    return (await coro) == value


async def _truthy(fn):
    return bool(fn())
