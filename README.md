# RELAY

Full-text RSS proxies for sites whose own feeds only ship a summary +
"read on site" link. Rebuilds each registered feed with the full
article HTML injected into `<content:encoded>`, hosted on GitHub Pages,
with a homepage listing everything active.

## Setup

```bash
git init && git add . && git commit -m "Init"
gh repo create relay --public --source=. --push
# or push to an existing empty GitHub repo manually
```

GitHub → **Settings → Pages → Source: Deploy from a branch → Branch:
main, folder: /docs → Save**.

**Actions tab → Rebuild feeds → Run workflow** to populate feeds
immediately instead of waiting for the 3-hourly cron.

Your homepage: `https://<user>.github.io/<repo>/`
Each feed: `https://<user>.github.io/<repo>/<slug>.xml`

## Adding a new site

Three ways, in increasing order of effort:

**1. No code — `GenericSource`.** Uses [trafilatura](https://github.com/adbar/trafilatura)'s
generic article extraction, which works decently on most blogs/news sites.
Uncomment the example in `sources/__init__.py` and fill in the URLs:

```python
GenericSource(
    slug="example",
    name="Example Site",
    feed_url="https://example.com/feed.xml",
    site_url="https://example.com",
    description="One-line description shown on the homepage.",
),
```

**2. Custom selectors.** If generic extraction misses content (grabs the
nav, drops images, cuts off early), write a small adapter — copy
`sources/psyche.py` as a template:

```python
from bs4 import BeautifulSoup
from .base import Source, clean_container

class MySiteSource(Source):
    def __init__(self):
        super().__init__(
            slug="mysite", name="My Site",
            feed_url="https://mysite.com/feed.xml",
            site_url="https://mysite.com",
            description="...",
        )

    def extract_article_html(self, html: str, url: str) -> str | None:
        soup = BeautifulSoup(html, "lxml")
        container = soup.select_one("div.article-body")  # <- inspect the site's own HTML
        if container is None:
            return None
        clean_container(container)  # strips script/style/ads/share-buttons/etc
        return str(container)
```

Register it in `sources/__init__.py`. If `extract_article_html` returns
`None` (selector didn't match), the pipeline automatically falls back to
generic extraction, then to the original summary — a wrong selector never
breaks the feed, it just quietly downgrades.

**3. JS-rendering fallback.** Some sites only inject article content via
client-side JS, or gate it behind a bot check that a plain `requests` call
won't pass. Set `allow_js_fallback=True` on the source; when both the
custom and generic extractors come back empty on the plain HTML, it
retries with a headless Chromium render (Playwright) before falling back
to the summary. Off by default since it's slower — only turn it on for
sites that actually need it.

## How extraction falls back

Per article, in order, first one that returns usable content wins:

1. Site-specific `extract_article_html()` (if the adapter defines one)
2. Generic `trafilatura` extraction
3. Same two steps again, against a JS-rendered page (only if `allow_js_fallback=True`)
4. Original RSS `<description>` — never left empty

`cache/<slug>.json` remembers already-processed article URLs (and which
fallback tier they hit) so re-runs only fetch new items. Check the Actions
log or a card's stats on the homepage to see if a site is mostly hitting
tier 1 (matched) or falling through to summaries.

## Files

```
sources/
  base.py      shared fetch/extract/fallback logic, Source base class
  psyche.py    Psyche adapter (verified against a real article page)
  aeon.py      Aeon adapter (unverified — same publisher as Psyche, likely
               same template, but written without a sample page — check the
               homepage stats after first run)
  generic.py   zero-code adapter, trafilatura only
fetch_feeds.py  orchestrator: builds every source's feed + the homepage
homepage.py     docs/index.html generator (self-contained, inline CSS/JS)
docs/           published to GitHub Pages
cache/          per-source dedup cache, committed by the Action
```
