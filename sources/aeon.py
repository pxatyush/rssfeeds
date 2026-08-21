from bs4 import BeautifulSoup

from .base import Source, clean_container


class AeonSource(Source):
    """UNVERIFIED: mirrors Psyche's selectors since both sites share the same
    publisher (Aeon Media) and likely the same Next.js template. If Actions
    logs show this always falling back to 'generic' for Aeon items, view-source
    a live Aeon essay and fix `extract_article_html` below to match.
    """

    def __init__(self):
        super().__init__(
            slug="aeon",
            name="Aeon",
            feed_url="https://aeon.co/feed.rss",
            site_url="https://aeon.co",
            description="Full-text proxy for Aeon essays and videos.",
            allow_js_fallback=False,
        )

    def extract_article_html(self, html: str, url: str) -> str | None:
        soup = BeautifulSoup(html, "lxml")
        container = soup.select_one("div.article-content") or soup.select_one("article")
        if container is None:
            return None
        clean_container(container)
        return str(container)
