"""Native Windows dialog (TaskDialogIndirect) with Continue / Cancel buttons."""
from __future__ import annotations

import ctypes
from ctypes import wintypes

from .base import Confirmation

ID_CONTINUE = 100
ID_CANCEL = 2                      # IDCANCEL: Esc and the close button map here
TDF_ALLOW_DIALOG_CANCELLATION = 0x0008
TDF_POSITION_RELATIVE_TO_WINDOW = 0x1000
TDN_CREATED = 0
WARNING_ICON = 0xFFFF              # MAKEINTRESOURCE(-1)
HWND_TOPMOST = -1
SWP_NOMOVE, SWP_NOSIZE = 0x2, 0x1
SW_SHOWNORMAL = 1


class _Button(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("id", ctypes.c_int), ("text", wintypes.LPCWSTR)]


_CALLBACK = ctypes.WINFUNCTYPE(
    ctypes.HRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
    wintypes.LPARAM, ctypes.c_void_p,
)


class _Config(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("hwndParent", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE),
        ("dwFlags", wintypes.DWORD),
        ("dwCommonButtons", wintypes.DWORD),
        ("pszWindowTitle", wintypes.LPCWSTR),
        ("pszMainIcon", ctypes.c_void_p),
        ("pszMainInstruction", wintypes.LPCWSTR),
        ("pszContent", wintypes.LPCWSTR),
        ("cButtons", wintypes.UINT),
        ("pButtons", ctypes.POINTER(_Button)),
        ("nDefaultButton", ctypes.c_int),
        ("cRadioButtons", wintypes.UINT),
        ("pRadioButtons", ctypes.c_void_p),
        ("nDefaultRadioButton", ctypes.c_int),
        ("pszVerificationText", wintypes.LPCWSTR),
        ("pszExpandedInformation", wintypes.LPCWSTR),
        ("pszExpandedControlText", wintypes.LPCWSTR),
        ("pszCollapsedControlText", wintypes.LPCWSTR),
        ("pszFooterIcon", ctypes.c_void_p),
        ("pszFooter", wintypes.LPCWSTR),
        ("pfCallback", _CALLBACK),
        ("lpCallbackData", ctypes.c_void_p),
        ("cxWidth", wintypes.UINT),
    ]


def _bring_to_front(hwnd, msg, wparam, lparam, data):
    if msg == TDN_CREATED:
        user32 = ctypes.windll.user32
        # A process started with a hidden-window flag would otherwise show this hidden.
        user32.ShowWindow(hwnd, SW_SHOWNORMAL)
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        user32.SetForegroundWindow(hwnd)
    return 0


_keepalive = _CALLBACK(_bring_to_front)


class WindowsTaskDialog:
    def __init__(self) -> None:
        # Fails with AttributeError off-Windows, or if comctl32 v6 is not active.
        self._fn = ctypes.windll.comctl32.TaskDialogIndirect

    def confirm(self, c: Confirmation) -> bool:
        buttons = (_Button * 2)(_Button(ID_CONTINUE, "Continue"), _Button(ID_CANCEL, "Cancel"))
        cfg = _Config()
        cfg.cbSize = ctypes.sizeof(_Config)
        cfg.dwFlags = TDF_ALLOW_DIALOG_CANCELLATION
        cfg.pszWindowTitle = "DLP Guard"
        cfg.pszMainIcon = WARNING_ICON
        cfg.pszMainInstruction = "Sensitive content detected"
        cfg.pszContent = (
            f"The marker WALLED_SENSITIVE was found in {c.what} "
            f"being sent to {c.site}.\n\n{c.label}: {c.name}\n\n"
            "Continue to send it anyway, or Cancel to block it."
        )
        cfg.cButtons = 2
        cfg.pButtons = buttons
        cfg.nDefaultButton = ID_CANCEL      # Enter = the safe choice
        cfg.pfCallback = _keepalive
        cfg.cxWidth = 0

        chosen = ctypes.c_int(0)
        self._fn(ctypes.byref(cfg), ctypes.byref(chosen), None, None)
        return chosen.value == ID_CONTINUE
