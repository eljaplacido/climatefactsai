"""Canonical HTML → plain-text cleaner for article body text.

End2End audit follow-up (2026-05-27, Task D) — production articles surface
raw `<img>` / `<p>` / `<a>` tags in the Full Article panel because
`rss_adapter._fetch_and_extract_article_body` fails-soft to the RSS
`<summary>` field, which most publishers populate with HTML markup. The
panel renders text via `whitespace-pre-wrap`, so the tags show through.

This module is the one place that strips that markup. Apply it:
  * In every ingest path that writes `articles.extracted_text` /
    `articles.excerpt` (so fresh rows land clean).
  * In the backfill admin endpoint (so the existing 1664 rows get
    cleaned without re-ingesting).
  * Defensively on read for any legacy row that slipped through.

The cleaner is deliberately conservative: it strips known structural /
media / script tags but otherwise preserves whitespace structure so a
multi-paragraph article stays readable. Uses BeautifulSoup so it
handles malformed HTML the same way the parsers downstream do.
"""

from __future__ import annotations

import re
from typing import Optional

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore[assignment]


# Tags whose contents we discard entirely (scripts, styles, embedded
# media, navigation). These never carry article body text and their
# inner content is almost always noise.
_DROP_TAGS = (
    "script", "style", "iframe", "video", "audio", "object", "embed",
    "form", "input", "button", "nav", "aside", "footer", "header",
    "noscript", "svg", "canvas", "figure", "figcaption",
)

# Tags whose contents we want but whose markup we strip. After
# unwrapping these the textual flow stays intact.
_UNWRAP_TAGS = (
    "a", "span", "em", "i", "strong", "b", "u", "small", "mark",
    "abbr", "cite", "q", "sub", "sup", "code", "kbd", "samp", "var",
    "time", "data",
)

# Block-level tags get a trailing newline so paragraphs stay separated.
_BLOCK_TAGS = (
    "p", "div", "section", "article", "main", "blockquote", "pre",
    "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol", "table",
    "tr", "td", "th", "br",
)

# Repeated whitespace cleanup after the BS4 pass.
_WS_RE = re.compile(r"[ \t]+")
_NL_RE = re.compile(r"\n{3,}")

# "The post X appeared first on Y" footer + WordPress block residue.
_WORDPRESS_FOOTER_RE = re.compile(
    r"\n*The post\s+.+?\s+appeared first on\s+.+?\.\s*$",
    re.IGNORECASE | re.DOTALL,
)


def looks_like_html(text: str) -> bool:
    """Cheap probe — true if the text appears to contain HTML tags.

    Heuristic: a `<tag>` or `<tag attr=...>` pattern in the first 4 KiB.
    We don't run the full clean on every read; only when this fires.
    """
    if not text:
        return False
    head = text[:4096]
    return bool(re.search(r"<[a-zA-Z!/][^<>]{0,200}>", head))


def clean_article_text(text: Optional[str]) -> str:
    """Return a plain-text version of an article body.

    Accepts:
      - Empty / None     -> ""
      - Plain text       -> unchanged (cheap path, no BS4 invocation)
      - HTML / mixed     -> stripped via BeautifulSoup

    The cheap path matters because the ingest writes call this for
    every article and most clean adapters produce plain text already.
    """
    if not text:
        return ""

    if not looks_like_html(text):
        # Plain-text fast path; just normalise whitespace.
        return _normalise_whitespace(text)

    if BeautifulSoup is None:
        # bs4 missing — fall back to a regex tag strip. Imperfect but
        # better than letting raw markup through.
        stripped = re.sub(r"<[^>]+>", " ", text)
        return _normalise_whitespace(stripped)

    soup = BeautifulSoup(text, "html.parser")

    # Drop noise tags wholesale.
    for tag_name in _DROP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Unwrap inline tags so their text content remains.
    for tag_name in _UNWRAP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.unwrap()

    # Insert explicit newlines after block-level tags so paragraph
    # structure survives `get_text(separator=" ")`.
    for tag_name in _BLOCK_TAGS:
        for tag in soup.find_all(tag_name):
            tag.insert_after("\n")

    plain = soup.get_text(separator=" ", strip=False)
    return _normalise_whitespace(plain)


def _normalise_whitespace(text: str) -> str:
    """Collapse runs of spaces/tabs, cap blank lines at 2, strip the
    WordPress 'The post X appeared first on Y' footer that many feeds
    inject verbatim."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS_RE.sub(" ", text)
    text = _NL_RE.sub("\n\n", text)
    text = _WORDPRESS_FOOTER_RE.sub("", text)
    return text.strip()


__all__ = ["clean_article_text", "looks_like_html"]
