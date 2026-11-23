"""python -m dlp_guard [--no-tray] [--browser PATH] [--port N] [--fail-mode block|allow]"""
from __future__ import annotations

import argparse
import logging
import threading

from .audit import AuditLog
from .browser import DEFAULT_PORT, BrowserController, find_browser, is_debuggable, launch
from .dialog import get_dialog
from .guard import Guard
from .sites import CHATGPT, DEFAULT_SITES, PERPLEXITY


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="dlp_guard", description="DLP Guard desktop app")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="browser remote-debugging port")
    ap.add_argument("--browser", help="path to msedge.exe / chrome.exe (auto-detected by default)")
    ap.add_argument("--no-launch", action="store_true",
                    help="do not start a browser; attach to one already running with --remote-debugging-port")
    ap.add_argument("--fail-mode", choices=("block", "allow"), default="block",
                    help="what the page does if this app stops responding (default: block)")
    ap.add_argument("--no-tray", action="store_true", help="run in the console, no tray icon")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    controller = BrowserController(Guard(get_dialog(), AuditLog()), DEFAULT_SITES,
                                   port=args.port, fail_mode=args.fail_mode)
    controller.start()

    def open_site(site) -> None:
        launch(site.start_url, port=args.port, browser=args.browser)

    if not args.no_launch:
        if find_browser() is None and not args.browser:
            raise SystemExit("Neither Microsoft Edge nor Google Chrome was found. Use --browser PATH.")
        if not is_debuggable(args.port):
            open_site(CHATGPT)
    print(f"DLP Guard is watching the browser on debug port {args.port}. Ctrl+C to stop.")

    stop = threading.Event()
    try:
        if args.no_tray:
            stop.wait()
        else:
            try:
                from .tray import run_tray
                run_tray(stop.set, [("Open ChatGPT", lambda: open_site(CHATGPT)),
                                    ("Open Perplexity", lambda: open_site(PERPLEXITY))])
            except ImportError:
                print("pystray not installed; running without a tray icon")
                stop.wait()
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()
