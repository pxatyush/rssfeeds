#!/usr/bin/env python3
"""Rebuilds a full-text RSS feed per registered source into docs/<slug>.xml,
then regenerates docs/index.html to list them. Run via GitHub Actions on a
schedule, or locally with `python fetch_feeds.py`.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import requests

from homepage import render_homepage
from sources import SOURCES
from sources.base import Source

DOCS_DIR = Path("docs")
CACHE_DIR = Path("cache")
MAX_CACHE_ENTRIES = 400


def load_cache(slug: str) -> dict:
    path = CACHE_DIR / f"{slug}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def save_cache(slug: str, cache: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if len(cache) > MAX_CACHE_ENTRIES:
        cache = dict(list(cache.items())[-MAX_CACHE_ENTRIES:])
    (CACHE_DIR / f"{slug}.json").write_text(json.dumps(cache, indent=0))


def cdata(text: str) -> str:
    return "<![CDATA[" + (text or "").replace("]]>", "]]]]><![CDATA[>") + "]]>"


def build_feed_xml(source: Source, channel_meta: dict, items: list[dict]) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" '
        'xmlns:atom="http://www.w3.org/2005/Atom" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:content="http://purl.org/rss/modules/content/">',
        "<channel>",
        f"<title>{cdata(channel_meta['title'])}</title>",
        f"<description>{cdata(channel_meta['description'])}</description>",
        f"<link>{escape(channel_meta['link'])}</link>",
        f'<atom:link href="{escape(source.feed_url)}" rel="self" type="application/rss+xml" />',
        "<language>en</language>",
        f"<lastBuildDate>{escape(channel_meta['lastBuildDate'])}</lastBuildDate>",
    ]
    for it in items:
        parts += [
            "<item>",
            f"<title>{cdata(it['title'])}</title>",
            f"<link>{escape(it['link'])}</link>",
            f'<guid isPermaLink="false">{escape(it["guid"])}</guid>',
            f"<dc:creator>{cdata(it['creator'])}</dc:creator>",
            f"<pubDate>{escape(it['pubDate'])}</pubDate>",
            f"<description>{cdata(it['description'])}</description>",
            f"<content:encoded>{cdata(it['full_html'])}</content:encoded>",
            "</item>",
        ]
    parts.append("</channel></rss>")
    return "\n".join(parts)


def build_source(source: Source) -> dict:
    """Returns homepage status metadata for this source."""
    print(f"\n=== {source.name} ({source.slug}) ===")
    status = {
        "name": source.name,
        "slug": source.slug,
        "site_url": source.site_url,
        "description": source.description,
        "item_count": 0,
        "ok": False,
        "error": None,
        "custom": 0,
        "generic": 0,
        "js": 0,
        "failed": 0,
    }

    try:
        resp = requests.get(source.feed_url, headers=source.headers, timeout=source.timeout)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except (requests.RequestException, ET.ParseError) as exc:
        print(f"  could not read source feed: {exc}")
        status["error"] = str(exc)
        return status

    channel = root.find("channel")
    channel_meta = {
        "title": channel.findtext("title") or source.name,
        "description": channel.findtext("description") or source.description,
        "link": channel.findtext("link") or source.site_url,
        "lastBuildDate": channel.findtext("lastBuildDate") or "",
    }

    cache = load_cache(source.slug)
    items_out = []

    for item in channel.findall("item"):
        link = item.findtext("link", "").strip()
        guid = item.findtext("guid", link).strip()
        title = item.findtext("title", "").strip()
        creator = item.findtext("{http://purl.org/dc/elements/1.1/}creator", "").strip()
        pub_date = item.findtext("pubDate", "").strip()
        description = item.findtext("description", "").strip()

        if guid in cache:
            full_html, extract_status = cache[guid]["html"], cache[guid]["status"]
            print(f"  cached  [{extract_status:>6}]  {title}")
        else:
            full_html, extract_status = source.get_full_article(link)
            source.polite_sleep()
            if full_html is None:
                full_html = description
            print(f"  fetched [{extract_status:>6}]  {title}")
            cache[guid] = {"html": full_html, "status": extract_status}

        status[extract_status] = status.get(extract_status, 0) + 1
        items_out.append(
            {
                "title": title,
                "link": link,
                "guid": guid,
                "creator": creator,
                "pubDate": pub_date,
                "description": description,
                "full_html": full_html,
            }
        )

    save_cache(source.slug, cache)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DOCS_DIR / f"{source.slug}.xml"
    out_path.write_text(build_feed_xml(source, channel_meta, items_out), encoding="utf-8")

    status["item_count"] = len(items_out)
    status["ok"] = True
    print(f"  wrote {out_path} ({len(items_out)} items)")
    return status


def main() -> None:
    all_status = [build_source(source) for source in SOURCES]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "index.html").write_text(render_homepage(all_status, now), encoding="utf-8")
    print(f"\nwrote {DOCS_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
