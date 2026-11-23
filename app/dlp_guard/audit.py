"""Append-only JSON-lines audit log. Never stores prompt or file content."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path


def default_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "dlp-guard" / "audit.jsonl"


class AuditLog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_path()
        self._lock = threading.Lock()

    def record(self, **fields) -> None:
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **fields}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
