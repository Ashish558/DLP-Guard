"""Per-site configuration. Every selector that can break when a site changes lives here."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Site:
    name: str
    hosts: tuple[str, ...]
    start_url: str
    # Send-button selectors (kept specific: pages also contain other submit buttons).
    send_button: tuple[str, ...] = ()
    # Selectors for AI response containers, used for recoloring.
    assistant_message: tuple[str, ...] = ()

    def to_js(self) -> dict:
        d = asdict(self)
        d["hosts"] = list(self.hosts)
        d["send_button"] = list(self.send_button)
        d["assistant_message"] = list(self.assistant_message)
        return d


CHATGPT = Site(
    name="ChatGPT",
    hosts=("chatgpt.com",),
    start_url="https://chatgpt.com/",
    send_button=(
        'button[data-testid="send-button"]',
        'button[aria-label="Send prompt"]',
        'button[aria-label="Send message"]',
    ),
    # ChatGPT ships several layouts, each marking the answer differently:
    #   classic: data-message-author-role   newer: data-assistant-markdown-root
    #   latest:  data-markdown-text-style / data-response-body
    # All are listed; extra matches are harmless.
    assistant_message=(
        '[data-message-author-role="assistant"]',
        "[data-assistant-markdown-root]",
        '[data-markdown-text-style="assistant-message"]',
        "[data-response-body]",
    ),
)

PERPLEXITY = Site(
    name="Perplexity",
    hosts=("www.perplexity.ai", "perplexity.ai"),
    start_url="https://www.perplexity.ai/",
    send_button=(
        'button[data-testid="submit-button"]',
        'button[aria-label="Submit"]',
    ),
    assistant_message=('[id^="markdown-content-"]', "div.prose"),
)

DEFAULT_SITES: tuple[Site, ...] = (CHATGPT, PERPLEXITY)


def site_for_host(host: str, sites: tuple[Site, ...] = DEFAULT_SITES) -> Site | None:
    return next((s for s in sites if host in s.hosts), None)
