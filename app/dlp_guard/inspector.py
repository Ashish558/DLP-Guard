"""Marker matching. Pure functions, no I/O."""
from __future__ import annotations

import re

MARKER = "WALLED_SENSITIVE"

_NON_ALNUM = re.compile(r"[^0-9A-Z]+")
_NEEDLE = _NON_ALNUM.sub("", MARKER.upper())


def normalize(text: str) -> str:
    """Upper-case and drop everything but letters and digits.

    OCR commonly turns '_' into ' ', '-' or nothing, and PDF extraction can
    split the marker over a line break, so matching is done on this form.
    """
    return _NON_ALNUM.sub("", text.upper())


def contains_marker(text: str) -> bool:
    return bool(text) and _NEEDLE in normalize(text)
