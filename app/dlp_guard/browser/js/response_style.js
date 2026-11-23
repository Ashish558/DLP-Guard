// Arms coloring only after the app approves marker-bearing content, then marks
// the next assistant message as it appears or streams into the page.
{
  const css = `.dlp-guard-sensitive-response, .dlp-guard-sensitive-response * { color: ${CFG.responseColor} !important; }`;
  const ID = "dlp-guard-response-color";
  const selector = site.assistant_message.join(",");
  const storageKey = () => `dlp-guard-sensitive-responses:${site.name}:${location.pathname}`;
  let armed = false;

  const ensure = () => {
    if (document.getElementById(ID)) return;
    const parent = document.head || document.documentElement;
    if (!parent) return;
    const style = document.createElement("style");
    style.id = ID;
    style.textContent = css;
    parent.appendChild(style);
  };

  function isAssistant(node) {
    return node instanceof Element && node.matches(selector);
  }

  function assistantMessages() {
    const matches = Array.from(document.querySelectorAll(selector));
    return matches.filter((node) => !node.parentElement?.closest(selector));
  }

  function assistantIn(node) {
    if (!(node instanceof Element)) node = node && node.parentElement;
    if (!(node instanceof Element)) return null;
    let message = node.closest(selector);
    if (!message) return null;
    for (let parent = message.parentElement?.closest(selector); parent; parent = parent.parentElement?.closest(selector)) {
      message = parent;
    }
    return message;
  }

  function savedIndexes() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey()) || "[]");
      return Array.isArray(saved) ? saved.filter(Number.isSafeInteger) : [];
    } catch (error) {
      console.warn("DLP Guard could not restore sensitive response highlights.", error);
      return [];
    }
  }

  function persistIndex(index) {
    const indexes = savedIndexes();
    if (indexes.includes(index)) return;
    indexes.push(index);
    try {
      sessionStorage.setItem(storageKey(), JSON.stringify(indexes));
    } catch (error) {
      console.warn("DLP Guard could not save a sensitive response highlight.", error);
    }
  }

  function restoreHighlights() {
    const messages = assistantMessages();
    for (const index of savedIndexes()) {
      const message = messages[index];
      if (message && !message.classList.contains("dlp-guard-sensitive-response")) {
        message.classList.add("dlp-guard-sensitive-response");
      }
    }
  }

  const observer = new MutationObserver((records) => {
    restoreHighlights();
    if (!armed) return;
    for (const record of records) {
      let message = assistantIn(record.target);
      if (!message) {
        for (const node of record.addedNodes) {
          message = assistantIn(node);
          if (!message && node instanceof Element) {
            const candidate = isAssistant(node) ? node : node.querySelector(selector);
            if (candidate) message = assistantIn(candidate);
          }
          if (message) break;
        }
      }
      if (message) {
        message.classList.add("dlp-guard-sensitive-response");
        persistIndex(assistantMessages().indexOf(message));
        armed = false;
        return;
      }
    }
  });

  let observedRoot = null;
  const observeDocument = () => {
    const root = document.documentElement;
    if (!root || root === observedRoot) return;
    observer.disconnect();
    observer.observe(root, {
      attributes: true, attributeFilter: ["class"], childList: true, characterData: true, subtree: true,
    });
    observedRoot = root;
  };

  window.markSensitiveResponse = () => { armed = true; };
  const refresh = () => {
    ensure();
    observeDocument();
    restoreHighlights();
  };
  setInterval(refresh, 1500);
  refresh();
}
