// Recolors every AI response with one injected stylesheet. CSS (not a DOM
// observer) means streamed and later-loaded messages are covered automatically.
// A light timer re-adds the stylesheet if the site's own rendering removes it.
{
  const rule = site.assistant_message.flatMap((s) => [s, `${s} *`]).join(",\n");
  const css = `${rule} { color: ${CFG.responseColor} !important; }`;
  const ID = "dlp-guard-response-color";

  const ensure = () => {
    if (document.getElementById(ID)) return;
    const parent = document.head || document.documentElement;
    if (!parent) return;
    const style = document.createElement("style");
    style.id = ID;
    style.textContent = css;
    parent.appendChild(style);
  };

  ensure();
  setInterval(ensure, 1500);
}
