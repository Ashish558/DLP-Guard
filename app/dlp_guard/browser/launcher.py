"""Finds and starts Edge / Chrome with remote debugging in the app's own profile."""
from __future__ import annotations

import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_PORT = 9222


def profile_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "dlp-guard" / "browser-profile"


def find_browser() -> str | None:
    pf, pf86 = os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get(
        "ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        rf"{pf86}\Microsoft\Edge\Application\msedge.exe",
        rf"{pf}\Microsoft\Edge\Application\msedge.exe",
        rf"{pf}\Google\Chrome\Application\chrome.exe",
        rf"{pf86}\Google\Chrome\Application\chrome.exe",
        rf"{local}\Google\Chrome\Application\chrome.exe",
    ]
    return next((c for c in candidates if os.path.exists(c)), None)


def is_debuggable(port: int) -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1).read()
        return True
    except (urllib.error.URLError, OSError):
        return False


def launch(url: str | None = None, *, port: int = DEFAULT_PORT, browser: str | None = None,
           profile: Path | None = None, headless: bool = False) -> subprocess.Popen | None:
    """Start the browser (or open `url` in it if our debuggable instance is already running).

    Chrome/Edge refuse remote debugging on the default profile, so a separate profile
    is used; the user signs in to the sites once there and stays signed in.
    """
    exe = browser or find_browser()
    if not exe:
        raise FileNotFoundError("Neither Microsoft Edge nor Google Chrome was found; pass --browser PATH")
    profile = profile or profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    args = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if headless:
        args.append("--headless=new")
    if url:
        args.append(url)
    return subprocess.Popen(args)
