"""OCR for images. Uses the Windows built-in OCR engine (no extra install)."""
from __future__ import annotations

import asyncio
import io
import logging

log = logging.getLogger(__name__)


def _variants(img):
    """The image as-is, plus an upscaled grayscale copy for small text."""
    from PIL import Image, ImageOps

    img = img.convert("RGB")
    yield img
    w, h = img.size
    if max(w, h) < 2000:
        scale = 2 if max(w, h) >= 800 else 3
        big = img.resize((w * scale, h * scale), Image.LANCZOS)
        yield ImageOps.autocontrast(ImageOps.grayscale(big)).convert("RGB")
    # Light-on-dark screenshots: invert.
    yield ImageOps.invert(img)


async def _recognize(img) -> str:
    import winocr

    result = await winocr.recognize_pil(img, "en")
    return result.text


def ocr_image(img) -> str:
    """Return recognized text for a PIL image ('' if OCR is unavailable)."""
    try:
        return asyncio.run(_recognize(img))
    except Exception:  # noqa: BLE001 - OCR must never crash the server
        log.exception("OCR failed")
        return ""


def image_texts(data: bytes):
    """Yield OCR text for progressively enhanced variants of the image."""
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:  # noqa: BLE001
        log.warning("not a readable image")
        return
    for variant in _variants(img):
        yield ocr_image(variant)
