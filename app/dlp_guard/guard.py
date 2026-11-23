"""Decision logic: inspect content, ask the user if needed, return allow/block.

No HTTP and no UI toolkit in here, so it is easy to test with a fake dialog.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from . import detectors, inspector
from .audit import AuditLog
from .dialog import Confirmation, Dialog


@dataclass(frozen=True)
class Decision:
    action: str          # "allow" or "block"
    sensitive: bool
    reason: str          # "clean" | "user_continue" | "user_cancel"


class Guard:
    def __init__(self, dialog: Dialog, audit: AuditLog) -> None:
        self._dialog = dialog
        self._audit = audit
        self._dialog_lock = threading.Lock()   # one dialog at a time

    def check_prompt(self, site: str, text: str) -> Decision:
        sensitive = inspector.contains_marker(text)
        return self._decide(site, "prompt", _preview(text), sensitive,
                            audit_name=f"(prompt, {len(text)} chars)")

    def check_file(self, site: str, name: str, data: bytes) -> Decision:
        sensitive = detectors.scan_file(data)
        return self._decide(site, "file", name, sensitive)

    def _decide(self, site: str, kind: str, name: str, sensitive: bool,
                audit_name: str | None = None) -> Decision:
        if not sensitive:
            decision = Decision("allow", False, "clean")
        else:
            with self._dialog_lock:
                ok = self._dialog.confirm(Confirmation(kind, name, site))
            decision = Decision("allow" if ok else "block", True,
                                "user_continue" if ok else "user_cancel")
        self._audit.record(site=site, kind=kind, name=audit_name or name,
                           sensitive=sensitive, decision=decision.action)
        return decision


def _preview(text: str, limit: int = 120) -> str:
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= limit else one_line[:limit] + "…"
