from __future__ import annotations

import logging

from .base import Confirmation, Dialog

log = logging.getLogger(__name__)


def get_dialog() -> Dialog:
    """Best native dialog available on this machine."""
    try:
        from .windows_taskdialog import WindowsTaskDialog

        return WindowsTaskDialog()
    except Exception as exc:  # noqa: BLE001
        log.warning("TaskDialog unavailable (%s); using Tk fallback", exc)
        from .tk_fallback import TkDialog

        return TkDialog()


__all__ = ["Confirmation", "Dialog", "get_dialog"]
