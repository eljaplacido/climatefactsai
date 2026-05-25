"""full_text_fetch — pin extraction behaviour + failure modes (Slice 4b).

The helper is graceful-degradation: it MUST never raise. These tests pin
each failure mode + the happy-path extraction, mocking httpx so we don't
hit the network.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from shared.full_text_fetch import (
    fetch_full_text,
    MIN_USEFUL_LENGTH,
    MAX_RESPONSE_BYTES,
    _strip_chrome,
    _extract_main_text,
)
from bs4 import BeautifulSoup


def _mock_response(status=200, text="", content_type="text/html; charset=utf-8"):
    """Build a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.content = text.encode("utf-8")
    resp.headers = {"content-type": content_type}
    return resp


def _mock_client(get_return):
    """Build a mock httpx.AsyncClient context manager."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=get_return)
    return client


# ---------------------------------------------------------------------------
# Pure-function helpers
# ---------------------------------------------------------------------------


class TestStripChrome:
    def test_removes_script_style_nav(self):
        html = """
        <html><body>
            <script>var x = 1;</script>
            <style>p { color: red; }</style>
            <nav>Menu</nav>
            <article><p>Real content here.</p></article>
            <footer>Copyright 2026</footer>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        _strip_chrome(soup)
        remaining = soup.get_text()
        assert "Real content here" in remaining
        assert "var x = 1" not in remaining
        assert "Menu" not in remaining
        assert "Copyright 2026" not in remaining

    def test_removes_class_or_id_share_widgets(self):
        html = """
        <body>
            <article><p>Main content paragraph.</p></article>
            <div class="newsletter-signup">Subscribe!</div>
            <div id="sidebar-related">Related articles</div>
            <div class="social-share-buttons">Share me</div>
        </body>
        """
        soup = BeautifulSoup(html, "html.parser")
        _strip_chrome(soup)
        remaining = soup.get_text()
        assert "Main content paragraph" in remaining
        assert "Subscribe" not in remaining
        assert "Related articles" not in remaining
        assert "Share me" not in remaining


class TestExtractMainText:
    def test_prefers_article_tag(self):
        html = """
        <body>
            <p>Body-level paragraph that shouldn't appear.</p>
            <article>
                <p>This is the real article paragraph with enough length.</p>
                <p>Second paragraph in the article also long enough.</p>
            </article>
        </body>
        """
        text = _extract_main_text(BeautifulSoup(html, "html.parser"))
        assert "real article paragraph" in text
        assert "Second paragraph" in text

    def test_falls_back_to_body_paragraphs(self):
        html = """
        <body>
            <p>First paragraph long enough for extraction.</p>
            <p>Second paragraph long enough too.</p>
            <p>X</p>  <!-- too short, filtered -->
        </body>
        """
        text = _extract_main_text(BeautifulSoup(html, "html.parser"))
        assert "First paragraph" in text
        assert "Second paragraph" in text
        assert text.count("\n\n") >= 1  # paragraphs are joined with blank lines


# ---------------------------------------------------------------------------
# fetch_full_text — failure modes + happy path
# ---------------------------------------------------------------------------


class TestFetchFullTextHappyPath:
    @pytest.mark.asyncio
    async def test_extracts_article_text(self):
        html = (
            "<html><body><article>"
            + "".join(
                f"<p>This is a substantial paragraph number {i} in the article body. "
                "It has more than twenty characters so the extractor keeps it.</p>"
                for i in range(5)
            )
            + "</article></body></html>"
        )

        with patch("httpx.AsyncClient", return_value=_mock_client(_mock_response(text=html))):
            text = await fetch_full_text("https://example.com/article", compliance_check=False)
        assert text is not None
        assert "substantial paragraph number 0" in text
        assert "substantial paragraph number 4" in text
        assert len(text) >= MIN_USEFUL_LENGTH


class TestFetchFullTextFailureModes:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_url", [None, "", "ftp://example.com/x", "not-a-url"])
    async def test_returns_none_for_invalid_url(self, bad_url):
        text = await fetch_full_text(bad_url, compliance_check=False)
        assert text is None

    @pytest.mark.asyncio
    async def test_returns_none_for_http_404(self):
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_client(_mock_response(status=404, text="")),
        ):
            text = await fetch_full_text("https://example.com/missing", compliance_check=False)
        assert text is None

    @pytest.mark.asyncio
    async def test_returns_none_for_non_html_content_type(self):
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_client(
                _mock_response(
                    text="binary data here",
                    content_type="application/pdf",
                )
            ),
        ):
            text = await fetch_full_text("https://example.com/file.pdf", compliance_check=False)
        assert text is None

    @pytest.mark.asyncio
    async def test_returns_none_when_extracted_too_short(self):
        # Real HTML but the extracted body is below MIN_USEFUL_LENGTH.
        html = "<html><body><article><p>Short body.</p></article></body></html>"
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_client(_mock_response(text=html)),
        ):
            text = await fetch_full_text("https://example.com/x", compliance_check=False)
        assert text is None

    @pytest.mark.asyncio
    async def test_never_raises_on_transport_error(self):
        import httpx

        async def boom(*args, **kwargs):
            raise httpx.ConnectTimeout("simulated timeout")

        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(side_effect=httpx.ConnectTimeout("simulated"))

        with patch("httpx.AsyncClient", return_value=client):
            text = await fetch_full_text("https://example.com/x", compliance_check=False)
        # Returns None, doesn't raise.
        assert text is None

    @pytest.mark.asyncio
    async def test_returns_none_for_oversized_response(self):
        # Build something larger than MAX_RESPONSE_BYTES.
        big_html = "<p>X</p>" * (MAX_RESPONSE_BYTES // 5)
        resp = _mock_response(text=big_html)
        # _mock_response built content from text already; override to be
        # explicitly oversized.
        resp.content = b"x" * (MAX_RESPONSE_BYTES + 1)
        with patch("httpx.AsyncClient", return_value=_mock_client(resp)):
            text = await fetch_full_text("https://example.com/x", compliance_check=False)
        assert text is None
