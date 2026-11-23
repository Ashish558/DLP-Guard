// Inspects files at the moment they are chosen / dropped / pasted, before the
// site sees them (both sites start uploading as soon as a file is attached).
// Allowed files are handed on by re-dispatching the event; blocked files are dropped.
{
  let replaying = false; // true while we re-dispatch an event we already inspected

  /** Inspect files one by one (dialogs are queued by the app). Returns the allowed ones. */
  async function filterAllowed(files) {
    const allowed = [];
    for (const f of files) {
      if (await fileAllowed(f)) allowed.push(f);
    }
    return allowed;
  }

  const toDataTransfer = (files) => {
    const dt = new DataTransfer();
    files.forEach((f) => dt.items.add(f));
    return dt;
  };

  function replay(fn) {
    replaying = true;
    try { fn(); } finally { replaying = false; }
  }

  // --- <input type="file"> (the attach button and its hidden inputs) -------
  window.addEventListener("change", (e) => {
    const input = e.target;
    if (replaying || !(input instanceof HTMLInputElement) || input.type !== "file") return;
    const files = Array.from(input.files || []);
    if (!files.length) return;
    e.stopImmediatePropagation();
    filterAllowed(files).then((allowed) => {
      if (!allowed.length) {
        input.value = ""; // lets the user pick the same file again
        return;
      }
      input.files = toDataTransfer(allowed).files;
      replay(() => input.dispatchEvent(new Event("change", { bubbles: true })));
    });
  }, true);

  // --- drag and drop -------------------------------------------------------
  window.addEventListener("drop", (e) => {
    const files = Array.from(e.dataTransfer ? e.dataTransfer.files : []);
    if (replaying || !files.length) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    const target = e.target;
    filterAllowed(files).then((allowed) => {
      if (!allowed.length) return;
      const ev = new DragEvent("drop", {
        bubbles: true, cancelable: true, clientX: e.clientX, clientY: e.clientY,
        dataTransfer: toDataTransfer(allowed),
      });
      replay(() => target.dispatchEvent(ev));
    });
  }, true);

  // --- paste (screenshots, copied files) -----------------------------------
  window.addEventListener("paste", (e) => {
    const files = Array.from(e.clipboardData ? e.clipboardData.files : []);
    if (replaying || !files.length) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    const target = e.target;
    const text = {
      "text/plain": e.clipboardData.getData("text/plain"),
      "text/html": e.clipboardData.getData("text/html"),
    };
    filterAllowed(files).then((allowed) => {
      if (!allowed.length && !text["text/plain"]) return;
      const dt = toDataTransfer(allowed);
      for (const [t, v] of Object.entries(text)) if (v) dt.setData(t, v);
      const ev = new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData: dt });
      replay(() => target.dispatchEvent(ev));
    });
  }, true);
}
