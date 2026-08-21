from .base import Source


class GenericSource(Source):
    """Zero-code adapter: `SOURCES.append(GenericSource(slug=..., name=..., feed_url=..., site_url=...))`

    Uses only the generic trafilatura extractor (see base.get_full_article's
    fallback chain). Good enough for most blogs/news sites; write a proper
    <site>.py adapter later if this misses content on a specific site.
    """
