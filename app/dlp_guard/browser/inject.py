"""Builds the JavaScript that the app injects into ChatGPT / Perplexity pages."""
from __future__ import annotations

import json
from pathlib import Path

from ..sites import Site

_JS_DIR = Path(__file__).parent / "js"
_PARTS = ("bridge.js", "prompt_gate.js", "file_gate.js", "response_style.js")

MAX_FILE_BYTES = 40 * 1024 * 1024
RESPONSE_COLOR = "#e8590c"


def build_script(sites: tuple[Site, ...], *, token: str, binding: str, reply: str,
                 fail_mode: str = "block", color: str = RESPONSE_COLOR) -> str:
    """One self-contained script. It does nothing on hosts that are not in `sites`."""
    cfg = {
        "token": token,
        "binding": binding,
        "reply": reply,
        "failMode": fail_mode,
        "maxFileBytes": MAX_FILE_BYTES,
        "responseColor": color,
        "sites": [s.to_js() for s in sites],
    }
    body = "\n".join((_JS_DIR / name).read_text(encoding="utf-8") for name in _PARTS)
    return (
        "(function () {\n"
        f"const CFG = {json.dumps(cfg)};\n"
        "if (window.__dlpGuardInstalled) return;\n"
        "const site = CFG.sites.find((s) => s.hosts.includes(location.hostname));\n"
        "if (!site) return;\n"
        "window.__dlpGuardInstalled = true;\n"
        f"{body}\n"
        "})();\n"
    )
