"""System-tray icon so the app is visibly running (needs pystray)."""
from __future__ import annotations

import os
from typing import Callable

from .audit import default_path


def run_tray(on_quit: Callable[[], None],
             actions: list[tuple[str, Callable[[], None]]] = ()) -> None:
    """Blocks on the tray loop; returns after Quit."""
    import pystray
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (64, 64), "#1f6feb")
    d = ImageDraw.Draw(img)
    d.rectangle((18, 14, 46, 50), outline="white", width=4)
    d.rectangle((26, 28, 38, 36), fill="white")

    def open_log(icon, item):
        path = default_path()
        if path.exists():
            os.startfile(path)  # noqa: S606 - local file, user action

    def quit_(icon, item):
        icon.stop()
        on_quit()

    def handler(fn):
        # pystray requires exactly (icon, item), so no default-argument tricks here.
        def run(icon, item):
            fn()
        return run

    items = [pystray.MenuItem("DLP Guard - running", None, enabled=False)]
    for label, fn in actions:
        items.append(pystray.MenuItem(label, handler(fn)))
    items += [pystray.MenuItem("Open audit log", open_log), pystray.MenuItem("Quit", quit_)]
    pystray.Icon("dlp-guard", img, "DLP Guard", pystray.Menu(*items)).run()
