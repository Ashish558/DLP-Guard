// Holds a prompt submission until the DLP Guard app has inspected it.
// Continue -> the site's own send button is clicked (content untouched).
// Cancel   -> nothing happens; the text stays in the composer.
//
// The composer is found structurally, because both sites ship several layouts:
// any text box with a send/submit button next to it is treated as a composer.
{
  let bypass = false; // true while we re-trigger the site's own submit
  let busy = false;   // true while a check / dialog is open

  const EDITABLE = 'textarea, input[type="text"], input:not([type]), [contenteditable=""], [contenteditable="true"], [role="textbox"]';
  const SEND_LABEL = /^\s*(send|submit)\b/i;
  const siteSend = site.send_button.join(",");

  const isSendButton = (b) =>
    (siteSend && b.matches(siteSend)) ||
    SEND_LABEL.test(b.getAttribute("aria-label") || "") ||
    /send/i.test(b.getAttribute("data-testid") || "");

  /** The send button belonging to the text box `el` (nearest ancestor holding one). */
  function sendButtonFor(el) {
    let node = el;
    for (let i = 0; i < 8 && node; i++, node = node.parentElement) {
      const btn = Array.from(node.querySelectorAll("button")).find(isSendButton);
      if (btn) return btn;
    }
    return null;
  }

  function composerFor(target) {
    if (!(target instanceof Element)) return null;
    const el = target.closest(EDITABLE);
    return el && sendButtonFor(el) ? el : null;
  }

  const textOf = (el) => ("value" in el ? el.value : el.innerText) || "";

  async function gate(el) {
    busy = true;
    try {
      // Loop: if the user edits the text while the dialog is open, re-check.
      for (;;) {
        const text = textOf(el);
        if (!text.trim()) return;
        const action = await askPrompt(text);
        if (action !== "allow" && action !== "allow-sensitive") return; // Cancel / error: leave as is
        if (textOf(el) !== text) continue;             // edited meanwhile: inspect again
        if (action === "allow-sensitive") markSensitiveResponse();
        submit(el);
        return;
      }
    } finally {
      busy = false;
    }
  }

  function submit(el) {
    const btn = sendButtonFor(el);
    bypass = true;
    try {
      if (btn && !btn.disabled) {
        btn.click();
      } else {
        el.dispatchEvent(new KeyboardEvent("keydown", {
          key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true,
        }));
      }
    } finally {
      bypass = false;
    }
  }

  window.addEventListener("keydown", (e) => {
    if (bypass || e.key !== "Enter" || e.shiftKey || e.isComposing) return;
    const el = composerFor(e.target);
    if (!el || !textOf(el).trim()) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if (!busy) gate(el);
  }, true);

  window.addEventListener("click", (e) => {
    if (bypass || !(e.target instanceof Element)) return;
    const btn = e.target.closest("button");
    if (!btn || !isSendButton(btn)) return;
    // The composer is the text box sharing the nearest container with this button.
    let node = btn, el = null;
    for (let i = 0; i < 8 && node && !el; i++, node = node.parentElement) {
      el = Array.from(node.querySelectorAll(EDITABLE)).find((c) => textOf(c).trim()) || null;
    }
    if (!el) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if (!busy) gate(el);
  }, true);
}
