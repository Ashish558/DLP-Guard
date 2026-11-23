# Architecture

## Overview

DLP Guard is one Python desktop process. It starts the user's Edge or Chrome with remote debugging
enabled (in its own profile), attaches to it over the DevTools protocol, and watches the ChatGPT and
Perplexity tabs. Nothing is installed in the browser.

```
┌─────────────────────────── DLP Guard (Python, tray app) ───────────────────────────┐
│ cli ── BrowserController ── Guard ── detectors (text / PDF / OCR)                  │
│            │  (asyncio)       │  └──── dialog (native Windows TaskDialog)          │
│            │                  └─ audit log                                         │
└────────────┼───────────────────────────────────────────────────────────────────────┘
             │ DevTools protocol, WebSocket on 127.0.0.1:9222
┌────────────▼──────────────────────────┐
│ Edge / Chrome (own profile)           │
│  chatgpt.com / perplexity.ai tabs     │
│   injected gate script (prompt, file, │
│   response color) ⇄ binding           │
└───────────────────────────────────────┘
```

The app decides *what* is sensitive and talks to the user. The injected script is the part that can
hold a browser action while the user decides.

## Attaching to the browser

* `browser/launcher.py` finds Edge/Chrome and starts it with `--remote-debugging-port` and a dedicated
  `--user-data-dir` (Chrome and Edge refuse debugging on the default profile). The user signs in once.
* `browser/cdp.py` is a small DevTools client (JSON over a WebSocket).
* `browser/controller.py` calls `Target.setAutoAttach` (waiting for the debugger on new tabs), so every tab,
  existing or new, is attached before its page scripts run. For each tab it:
  1. `Runtime.addBinding` — creates a function the page can call to message the app,
  2. `Page.addScriptToEvaluateOnNewDocument` — injects the gate script into every page load, and runs it
     now in already-open pages.
  It reconnects automatically if the browser is closed and reopened.
* The script does nothing on hosts that are not in `sites.py`. The app also ignores binding messages
  from tabs whose URL is not a guarded site, and every message carries a per-run random token.

## Prompt interception

`browser/js/prompt_gate.js` registers capture-phase listeners on `window` at document start, so it runs
before the site's own handlers:

1. **Enter** (without Shift) in a composer, or a **click** on the send button, is stopped
   (`preventDefault` + `stopImmediatePropagation`). A composer is any text box with a send/submit button
   next to it; this is structural because both sites ship several layouts.
2. The composer text goes to the app through the binding.
3. `allow` (clean, or the user chose Continue): the site's **own send button is clicked** with a `bypass`
   flag so our listeners skip it. The text is never rewritten.
4. `block` (Cancel): nothing is done. The text stays in the composer so it can be edited and resent.

If the text changes while the dialog is open, it is inspected again before sending.

## File interception

`browser/js/file_gate.js` listens (capture phase) for the three ways a file reaches the page:

| Entry point | Event | Hand-off after inspection |
|---|---|---|
| Attach button / hidden inputs | `change` on `input[type=file]` | set `input.files` to the allowed files, re-dispatch `change` |
| Drag and drop | `drop` | dispatch a new `DragEvent` carrying a `DataTransfer` of allowed files |
| Paste (screenshots, files) | `paste` | dispatch a new `ClipboardEvent` with allowed files and the original text |

Both sites start uploading as soon as a file is attached, so inspecting here is "before it is
transmitted". Each file is checked on its own: a mixed selection delivers only the clean or approved
files. Cancelled files are removed and `input.value` is cleared so the same file can be picked again.

## Page-to-app messaging

`bridge.js` sends each request through the binding in 256 KB chunks (files are base64). The app
acknowledges when the last chunk arrives (so the page can tell the app is alive), then replies with
`allow` or `block` after inspection and the dialog, by evaluating a reply function in the tab.
If no acknowledgement arrives within 8 s the page applies the fail mode (block by default) and shows a notice.

## Inspection (app side)

`guard.py` is the decision logic (no browser, no UI), so it is tested with a fake dialog.

* `inspector.py`: normalizes text (upper-case, letters and digits only) and looks for `WALLEDSENSITIVE`.
  OCR often reads `_` as a space and PDF extraction can break lines, so exact matching would miss it.
* `detectors/`: the file type is sniffed from the bytes, not the name.
  * text: decoded as UTF-8 / UTF-16
  * PDF (PyMuPDF): text layer first; pages with images or no text are rendered and OCR'd
  * image: Windows built-in OCR (`winocr`), tried on the original, an enlarged high-contrast copy and an inverted copy
* `dialog/`: `TaskDialogIndirect` through `ctypes` gives a real Windows dialog with buttons labelled exactly
  **Continue** and **Cancel**. It is topmost, Esc / close means Cancel, and Cancel is the default button.
  A Tkinter fallback is used if TaskDialog is unavailable. Only one dialog is shown at a time.
* `audit.py`: JSON lines with site, kind, name, decision. Prompt text is never stored.

Inspection and the dialog run on worker threads, so a waiting dialog never blocks the browser connection.

## Enforcement and failure rules

* The decision is made in the app; the page only does what it is told: `allow` or `block`.
* Anything unclear is **blocked**: app not responding, inspection error, file too large, unreadable file.
  The user sees an on-page notice. `--fail-mode allow` switches this.

## Response coloring

`browser/js/response_style.js` injects one `<style>` rule (`color: ... !important`) for each site's
assistant-message selectors and all their descendants. CSS instead of a DOM observer means streamed and
future messages are covered with no per-message code. A light timer re-adds the rule if the site removes it.

## Per-site configuration

`sites.py` holds hosts and selectors (send buttons, response containers). ChatGPT serves several layouts
(different response markers, textarea vs rich-text composer), so each entry is a list. Send-button
selectors are kept specific because the pages contain other `type=submit` buttons.

## Design choices

* **Own the browser session over DevTools** rather than a network proxy (needs a custom CA, sees uploads
  to other hosts, interferes with normal browsing) or an embedded web view (Google sign-in often blocks
  embedded browsers, and the sites should be used in a real browser).
* **Inspect in the app**: PDF and OCR libraries are Python; one code path for prompts and files.
* **Capture-phase gating of user actions** instead of network interception, because it works before any
  request exists and keeps the composer state intact on Cancel.

## Testing

`tests/test_browser_e2e.py` starts a real headless Edge/Chrome, serves a fake chat page, and checks
the whole chain (attach, inject, key press, dialog, reply, send) including file selection and recoloring.
`tests/test_detection.py` covers the marker matching and the text/PDF/image/scanned-PDF detectors.
