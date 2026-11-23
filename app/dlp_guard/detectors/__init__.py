"""Content detectors. `scan_file` picks one by sniffing the bytes."""
from __future__ import annotations

from .. import inspector
from . import image_ocr, pdf

_IMAGE_MAGICS = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",          # JPEG
    b"GIF8",
    b"BM",                    # BMP
    b"RIFF",                  # WEBP (checked further below)
    b"II*\x00", b"MM\x00*",   # TIFF
)


def kind_of(data: bytes) -> str:
    """'pdf', 'image' or 'text' (anything else is scanned as text)."""
    if data[:5] == b"%PDF-":
        return "pdf"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image"
    if any(data.startswith(m) for m in _IMAGE_MAGICS if m != b"RIFF"):
        return "image"
    return "text"


def _decode(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="ignore")
    return data.decode("utf-8", errors="ignore")


def scan_file(data: bytes) -> bool:
    """True if the file content contains the sensitive marker."""
    kind = kind_of(data)
    if kind == "pdf":
        return pdf.contains_marker(data)
    if kind == "image":
        return any(inspector.contains_marker(t) for t in image_ocr.image_texts(data))
    return inspector.contains_marker(_decode(data))
