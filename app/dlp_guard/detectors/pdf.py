"""PDF inspection: text layer first, OCR of rendered pages as a fallback."""
from __future__ import annotations

import io
import logging
from typing import Callable

from .. import inspector
from .image_ocr import image_texts

log = logging.getLogger(__name__)

MAX_OCR_PAGES = 20


def contains_marker(data: bytes) -> bool:
    import pymupdf as fitz

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:  # noqa: BLE001
        log.warning("unreadable PDF")
        return False

    with doc:
        # Pass 1: cheap text layer of every page.
        needs_ocr = []
        for page in doc:
            text = page.get_text()
            if inspector.contains_marker(text):
                return True
            if len(text.strip()) < 20 or page.get_images():
                needs_ocr.append(page.number)

        # Pass 2: OCR pages that are scans or hold images.
        for number in needs_ocr[:MAX_OCR_PAGES]:
            pix = doc[number].get_pixmap(dpi=200)
            png = pix.tobytes("png")
            for text in image_texts(png):
                if inspector.contains_marker(text):
                    return True
    return False
