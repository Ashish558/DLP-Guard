# DLP Guard

A standalone desktop application that acts as a lightweight Data Loss Prevention tool for
**ChatGPT** (chatgpt.com) and **Perplexity** (perplexity.ai) used in a web browser.

Before a prompt or file leaves the browser, DLP Guard checks it for the marker `WALLED_SENSITIVE`
(text prompts, text files, PDFs and images). If it is found, a **native Windows dialog** asks you to
**Continue** or **Cancel**. After you continue, the next AI response appears in orange.

**No browser extension, plugin or add-on is used.** DLP Guard is a Python desktop app. It starts your
normal Edge or Chrome and watches it from outside over the browser's built-in DevTools debugging protocol.
See [docs/architecture.md](docs/architecture.md).

## Requirements

* Windows 10/11 (native dialog and OCR use built-in Windows APIs)
* Python 3.10+
* Microsoft Edge or Google Chrome

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[tray,dev]"
```

## Run

```powershell
.venv\Scripts\python -m dlp_guard
```

(Use `pythonw` instead of `python` to run without a console window.)

1. A tray icon appears and Edge (or Chrome) opens ChatGPT. This browser uses its **own profile**
   (`%LOCALAPPDATA%\dlp-guard\browser-profile`), because Chrome and Edge do not allow debugging on your
   everyday profile.
2. **Sign in once** to ChatGPT and Perplexity in that window. You stay signed in on later runs.
3. Use the sites normally. The tray menu has **Open ChatGPT**, **Open Perplexity**, **Open audit log** and **Quit**.

Options: `--browser PATH` (choose a browser), `--port N` (debug port, default 9222), `--no-tray`,
`--fail-mode allow` (see below), `--no-launch` (attach to a browser you started yourself with
`--remote-debugging-port=9222 --user-data-dir=...`).

## What it does

* **Type a prompt** containing `WALLED_SENSITIVE` and press Enter (or click send): a dialog shows
  "a text prompt" and a preview. **Continue** sends it unchanged. **Cancel** blocks it; the text stays in the box.
* **Attach, drop or paste a file** (txt, PDF or image): it is inspected before the site receives it.
  Sensitive files show a dialog with the file name. **Cancel** drops the file; you can pick it again later.
* Clean prompts and files go through with no extra step.
* Responses to approved marker-bearing content appear in orange. Change `RESPONSE_COLOR` in
  `app/dlp_guard/browser/inject.py`.
* If the app stops responding, actions are **blocked** with an on-page notice (`--fail-mode allow` lets them through).

The audit log is `%LOCALAPPDATA%\dlp-guard\audit.jsonl` (site, kind, file name, decision; never content).

## Tests and test files

```powershell
.venv\Scripts\python scripts\make_fixtures.py    # writes fixtures/ (txt, pdf, scanned pdf, png; clean and sensitive)
.venv\Scripts\python -m pytest -q
```

The suite includes an end-to-end test that starts a real headless Edge/Chrome, attaches the app to a
local fake chat page, and drives it with real key presses and file selections.
The `fixtures/sensitive.*` files are ready for manual testing on the real sites.

## Limits

* Windows only for now (dialog and OCR). The dialog is behind an interface so other platforms can be added.
* Only the browser started by DLP Guard is watched. Other browsers and your everyday profile are not.
* The browser's debug port (127.0.0.1 only) lets other programs on the same PC control that browser.
  Do not use it for anything you would not run locally.
* Content a site generates itself (for example ChatGPT turning a very long paste into an attachment) is
  not seen by the file gate.
* Files over 40 MB are not inspected (blocked, with a notice). Images and scanned PDFs rely on OCR; text that is
  tiny, stylized or low-contrast may be missed. Only the first 20 image-bearing PDF pages are OCR'd.
* Site layouts change often. All selectors live in `app/dlp_guard/sites.py`.
* Formats other than text, PDF and images (for example .docx) are scanned as raw text, which will not see
  inside compressed files.
