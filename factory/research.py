"""Bounded official feed collection. Retrieved text is evidence, never instructions."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import hashlib
import json
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import httpx

# Fixed endpoints; no arbitrary URL fetching, redirect following or local-network targets.
FEEDS = {'openai': 'https://openai.com/news/rss.xml',
         'google': 'https://blog.google/innovation-and-ai/technology/ai/rss/'}


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain(value, limit):
    parser = Text()
    parser.feed(value)
    return ' '.join(' '.join(parser.parts).split())[:limit]


def parse_feed(body, provider, now=None):
    if len(body) > 2_000_000 or b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():
        raise ValueError('Unsafe or oversized feed')
    root = ET.fromstring(body)
    now = now or datetime.now(timezone.utc)
    items = []
    for node in root.findall('.//item')[:40]:
        title = plain(node.findtext('title', ''), 200)
        url = node.findtext('link', '').strip()
        parsed = urlsplit(url)
        allowed = {'openai.com', 'www.openai.com'} if provider == 'openai' else {'blog.google'}
        if parsed.scheme != 'https' or parsed.hostname not in allowed or parsed.username or parsed.port not in {None, 443}:
            continue
        excerpt = plain(node.findtext('description', ''), 600)
        if not title or not excerpt:
            continue
        published = None
        try:
            date = parsedate_to_datetime(node.findtext('pubDate', ''))
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            published = date.isoformat()
            age = max(0, (now - date).total_seconds() / 86400)
            freshness = round(max(0, 100 - age * 2), 1)
        except (ValueError, TypeError, OverflowError):
            freshness = None
        items.append({'id': hashlib.sha256(url.encode()).hexdigest()[:20], 'url': url,
                      'title': title, 'evidence': excerpt, 'claim': title[:300],
                      'checked_at': now.isoformat(), 'published_at': published,
                      'provider': provider, 'status': 'UNVERIFIED',
                      'confidence_reason': 'Thông báo của nhà cung cấp; chưa kiểm chứng độc lập.',
                      'freshness_heuristic': freshness, 'search_volume': None, 'competition': None})
    return items


def collect(query='', client=None):
    own = client is None
    client = client or httpx.Client(timeout=15, follow_redirects=False)
    items, errors = [], []
    try:
        for provider, url in FEEDS.items():
            try:
                with client.stream('GET', url, headers={'User-Agent': 'AIReviewStudio/1.0'}) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 2_000_000:
                            raise ValueError('Feed too large')
                items.extend(parse_feed(bytes(body), provider))
            except (httpx.HTTPError, ValueError, ET.ParseError):
                errors.append({'provider': provider, 'status': 'UNAVAILABLE'})
    finally:
        if own:
            client.close()
    words = query.casefold().split()
    items = [item for item in items if not words or any(w in (item['title']+' '+item['evidence']).casefold() for w in words)]
    items.sort(key=lambda item: item['freshness_heuristic'] or 0, reverse=True)
    return {'checked_at': datetime.now(timezone.utc).isoformat(), 'query': query,
            'items': items, 'providers': errors, 'ranking': 'Freshness heuristic only; no measured demand data'}
