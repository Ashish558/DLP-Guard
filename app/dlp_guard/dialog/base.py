"""Dialog interface. Implementations show a native, blocking confirmation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Confirmation:
    kind: str    # "prompt" or "file"
    name: str    # file name, or a preview of the prompt
    site: str    # "ChatGPT" / "Perplexity"

    @property
    def what(self) -> str:
        return "a text prompt" if self.kind == "prompt" else "a file"

    @property
    def label(self) -> str:
        return "Prompt" if self.kind == "prompt" else "File"


class Dialog(Protocol):
    def confirm(self, c: Confirmation) -> bool:
        """Block until the user answers. True = Continue, False = Cancel."""
        ...
