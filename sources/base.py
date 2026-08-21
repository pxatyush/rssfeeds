"""Shared plumbing every site adapter builds on.

Extraction fallback chain, per item:
  1. Source.extract_article_html()   -- site-specific BeautifulSoup selectors
  2. generic_extract()               -- trafilatura, works reasonably on most sites
  3. render_with_js() + steps 1-2    -- only if allow_js_fallback=True and the
                                         above returned nothing useful
  4. original RSS <description>      -- last resort, never leaves an empty item
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests
import trafilatura
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

MIN_USABLE_CHARS = 200  # below this, treat extraction as a failure


def clean_container(container, extra_strip: tuple[str, ...] = ()) -> None:
    """Strips chrome (nav, ads, share buttons, forms, scripts) common across sites."""
    strip_selectors = (
        "script",
        "style",
        "noscript",
        "form",
        "button",
        "svg",
        "iframe.ad",
        ".advertisement",
        ".newsletter",
        ".share-buttons",
        "aside",
    ) + extra_strip
    for selector in strip_selectors:
        for tag in container.select(selector):
            tag.decompose()
    for figure in container.find_all("figure"):
        if not figure.find("img"):
            figure.decompose()
    for img in container.find_all("img"):
        img.attrs = {k: v for k, v in img.attrs.items() if k in ("src", "alt")}


def usable(html: str | None) -> bool:
    if not html:
        return False
    text = BeautifulSoup(html, "lxml").get_text(strip=True)
    return len(text) > MIN_USABLE_CHARS


def generic_extract(html: str, url: str) -> str | None:
    """Fallback extractor for sites without a custom adapter (trafilatura)."""
    result = trafilatura.extract(
        html,
        url=url,
        output_format="html",
        include_images=True,
        include_links=True,
        favor_recall=True,
    )
    return result if usable(result) else None


@dataclass
class Source:
    slug: str  # output filename stem -> docs/<slug>.xml
    name: str  # display name, e.g. "Psyche"
    feed_url: str  # the site's own (summary-only) RSS/Atom feed
    site_url: str  # homepage, for the "visit site" link
    description: str = ""
    allow_js_fallback: bool = False
    request_delay: float = 1.5
    headers: dict = field(default_factory=lambda: dict(DEFAULT_HEADERS))
    timeout: int = 20

    def fetch_html(self, url: str) -> str | None:
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            print(f"  [{self.slug}] fetch failed for {url}: {exc}")
            return None

    def extract_article_html(self, html: str, url: str) -> str | None:
        """Override in subclasses with site-specific selectors.

        Default: no custom logic, defer straight to the generic extractor.
        """
        return None

    def render_with_js(self, url: str) -> str | None:
        """Headless-browser fetch, used as a fallback for JS-gated content.

        Only invoked when allow_js_fallback=True and the plain-HTTP path
        above produced nothing usable (bot walls, client-side rendering,
        content injected after load, etc). Requires Playwright + browsers
        to be installed; degrades to None (not a crash) if unavailable.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print(f"  [{self.slug}] playwright not installed, skipping JS fallback")
            return None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(user_agent=self.headers.get("User-Agent"))
                page.goto(url, timeout=self.timeout * 1000, wait_until="networkidle")
                html = page.content()
                browser.close()
                return html
        except Exception as exc:  # noqa: BLE001 - fallback path, never fatal
            print(f"  [{self.slug}] JS render failed for {url}: {exc}")
            return None

    def get_full_article(self, url: str) -> tuple[str | None, str]:
        """Returns (html_or_None, status) where status is one of:
        'custom', 'generic', 'js', 'failed'.
        """
        html = self.fetch_html(url)
        if html:
            article = self.extract_article_html(html, url)
            if usable(article):
                return article, "custom"
            article = generic_extract(html, url)
            if usable(article):
                return article, "generic"

        if self.allow_js_fallback:
            rendered = self.render_with_js(url)
            if rendered:
                article = self.extract_article_html(rendered, url)
                if usable(article):
                    return article, "js"
                article = generic_extract(rendered, url)
                if usable(article):
                    return article, "js"

        return None, "failed"

    def polite_sleep(self) -> None:
        time.sleep(self.request_delay)
