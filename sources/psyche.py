from bs4 import BeautifulSoup

from .base import Source, clean_container


class PsycheSource(Source):
    def __init__(self):
        super().__init__(
            slug="psyche",
            name="Psyche",
            feed_url="https://psyche.co/feed.rss",
            site_url="https://psyche.co",
            description="Full-text proxy for Psyche's ideas, guides, notes-to-self and turning-points.",
            allow_js_fallback=False,  # site is server-rendered, plain HTTP is enough
        )

    def extract_article_html(self, html: str, url: str) -> str | None:
        soup = BeautifulSoup(html, "lxml")
        container = soup.select_one("div.article-content") or soup.select_one("article")
        if container is None:
            return None
        clean_container(container)
        return str(container)
