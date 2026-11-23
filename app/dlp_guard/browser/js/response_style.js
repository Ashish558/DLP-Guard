// Arms coloring only after the app approves marker-bearing content, then marks
// the next assistant message as it appears or streams into the page.
{
  const css = `.dlp-guard-sensitive-response, .dlp-guard-sensitive-response * { color: ${CFG.responseColor} !important; }`;
  const ID = "dlp-guard-response-color";
  let armed = false;
  let coloredMessage = null;

  const ensure = () => {
    if (document.getElementById(ID)) return;
    const parent = document.head || document.documentElement;
    if (!parent) return;
    const style = document.createElement("style");
    style.id = ID;
    style.textContent = css;
    parent.appendChild(style);
  };

  function assistantIn(node) {
    if (!(node instanceof Element)) node = node && node.parentElement;
    if (!(node instanceof Element)) return null;
    return node.closest(site.assistant_message.join(","));
  }

  const observer = new MutationObserver((records) => {
    if (coloredMessage && !coloredMessage.classList.contains("dlp-guard-sensitive-response")) {
      coloredMessage.classList.add("dlp-guard-sensitive-response");
    }
    if (!armed) return;
    for (const record of records) {
      let message = assistantIn(record.target);
      if (!message) {
        for (const node of record.addedNodes) {
          message = assistantIn(node);
          if (!message && node instanceof Element) {
            message = node.querySelector(site.assistant_message.join(","));
          }
          if (message) break;
        }
      }
      if (message) {
        message.classList.add("dlp-guard-sensitive-response");
        coloredMessage = message;
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
  };
  setInterval(refresh, 1500);
  refresh();
}
