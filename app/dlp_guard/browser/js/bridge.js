// Bridge between the injected page code and the desktop app.
// window[CFG.binding] is created by the app (Runtime.addBinding); the app answers
// through window[CFG.reply]. Everything here shares one closure with the gates.

const FAIL_MODE = CFG.failMode;            // "block" (safe) or "allow"
const MAX_FILE_BYTES = CFG.maxFileBytes;
const CHUNK = 256 * 1024;                  // characters per message
const ACK_TIMEOUT_MS = 8000;               // app must acknowledge receipt within this

const first = (selectors) => {
  for (const s of [].concat(selectors)) {
    const el = document.querySelector(s);
    if (el) return el;
  }
  return null;
};

function notify(text) {
  const show = () => {
    const el = document.createElement("div");
    el.textContent = text;
    el.style.cssText =
      "position:fixed;z-index:2147483647;left:50%;bottom:24px;transform:translateX(-50%);" +
      "background:#b42318;color:#fff;padding:10px 16px;border-radius:8px;" +
      "font:14px system-ui,sans-serif;box-shadow:0 4px 16px rgba(0,0,0,.3)";
    (document.body || document.documentElement).appendChild(el);
    setTimeout(() => el.remove(), 6000);
  };
  show();
}

const pending = new Map();
let seq = 0;

window[CFG.reply] = (id, action) => {
  const p = pending.get(id);
  if (!p) return;
  if (action === "ack") {                  // app received it; now wait for the user
    clearTimeout(p.timer);
    return;
  }
  clearTimeout(p.timer);
  pending.delete(id);
  p.resolve(action);
};

/** Send one inspection request to the app. Resolves to "allow" or "block". */
function ask(kind, name, data) {
  return new Promise((resolve) => {
    const send = window[CFG.binding];
    const fail = (why) => {
      pending.delete(id);
      notify(
        "DLP Guard: " + why + " — this was " +
          (FAIL_MODE === "block" ? "blocked. Start the DLP Guard app and try again." : "sent without inspection.")
      );
      resolve(FAIL_MODE);
    };
    const id = ++seq;
    const entry = { resolve, timer: null };
    pending.set(id, entry);
    if (typeof send !== "function") return fail("the app is not connected");

    const total = Math.max(1, Math.ceil(data.length / CHUNK));
    for (let i = 0; i < total; i++) {
      send(JSON.stringify({
        t: CFG.token, id, kind, site: site.name, name, seq: i, total,
        data: data.slice(i * CHUNK, (i + 1) * CHUNK),
      }));
    }
    entry.timer = setTimeout(() => fail("the app did not respond"), ACK_TIMEOUT_MS);
  });
}

const askPrompt = (text) => ask("prompt", "", text);

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] || "");
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}

/** Inspect one File. Resolves to true if it may proceed. */
async function fileAllowed(file) {
  if (file.size > MAX_FILE_BYTES) {
    notify(`DLP Guard: "${file.name}" is too large to inspect, so it was ${FAIL_MODE === "block" ? "blocked" : "allowed"}.`);
    return FAIL_MODE === "allow";
  }
  let b64;
  try {
    b64 = await fileToBase64(file);
  } catch (_) {
    notify(`DLP Guard: could not read "${file.name}", so it was blocked.`);
    return false;
  }
  return (await ask("file", file.name, b64)) === "allow";
}
