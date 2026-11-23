import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import make_fixtures  # noqa: E402
from dlp_guard import detectors, inspector  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def fixtures():
    make_fixtures.main()


def read(name: str) -> bytes:
    return (ROOT / "fixtures" / name).read_bytes()


@pytest.mark.parametrize("text", [
    "WALLED_SENSITIVE", "xx walled_sensitive yy", "WALLED SENSITIVE",
    "WALLED-\nSENSITIVE", "prefix_WALLED_SENSITIVE_suffix",
])
def test_marker_variants_match(text):
    assert inspector.contains_marker(text)


@pytest.mark.parametrize("text", ["", "hello world", "WALLED only", "SENSITIVE only"])
def test_non_matches(text):
    assert not inspector.contains_marker(text)


@pytest.mark.parametrize("ext", ["txt", "pdf", "png", "_scanned.pdf"])
def test_sensitive_files_detected(ext):
    name = "sensitive" + (ext if ext.startswith("_") else "." + ext)
    assert detectors.scan_file(read(name))


@pytest.mark.parametrize("ext", ["txt", "pdf", "png", "_scanned.pdf"])
def test_clean_files_pass(ext):
    name = "clean" + (ext if ext.startswith("_") else "." + ext)
    assert not detectors.scan_file(read(name))


def test_kind_sniffing():
    assert detectors.kind_of(read("clean.pdf")) == "pdf"
    assert detectors.kind_of(read("clean.png")) == "image"
    assert detectors.kind_of(read("clean.txt")) == "text"


def test_utf16_text():
    assert detectors.scan_file("hi WALLED_SENSITIVE".encode("utf-16"))


def test_garbage_does_not_crash():
    assert not detectors.scan_file(b"%PDF-1.4 not really a pdf")
    assert not detectors.scan_file(b"\x89PNG\r\n\x1a\nnope")
