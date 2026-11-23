"""Generate test files into fixtures/: python scripts/make_fixtures.py"""
from __future__ import annotations

import io
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "fixtures"
SENSITIVE = "Quarterly figures. Internal only: WALLED_SENSITIVE. Do not share."
CLEAN = "Quarterly figures. Nothing confidential here."


def png_bytes(text: str) -> bytes:
    img = Image.new("RGB", (900, 160), "white")
    ImageDraw.Draw(img).text((24, 56), text, fill="black", font=ImageFont.truetype("arial.ttf", 30))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def text_pdf(text: str) -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 100), text, fontsize=14)
    return doc.tobytes()


def scanned_pdf(text: str) -> bytes:
    """A PDF whose only content is a picture of text (no text layer)."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(fitz.Rect(40, 60, 555, 160), stream=png_bytes(text))
    return doc.tobytes()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for tag, text in (("sensitive", SENSITIVE), ("clean", CLEAN)):
        (OUT / f"{tag}.txt").write_text(text, encoding="utf-8")
        (OUT / f"{tag}.pdf").write_bytes(text_pdf(text))
        (OUT / f"{tag}.png").write_bytes(png_bytes(text))
        (OUT / f"{tag}_scanned.pdf").write_bytes(scanned_pdf(text))
    print("fixtures written to", OUT)


if __name__ == "__main__":
    main()
