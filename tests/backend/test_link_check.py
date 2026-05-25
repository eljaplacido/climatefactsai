"""Link-rot detection — classify + probe behaviour (Slice 5a).

Pins the status-mapping taxonomy from mig 046 + the failure modes of
_probe so a regression can't silently turn 'broken' into 'ok'.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from api.admin_link_check_routes import _classify, _probe


# ---------------------------------------------------------------------------
# _classify — pin the mig 046 taxonomy.
# ---------------------------------------------------------------------------


class TestClassify:
    @pytest.mark.parametrize("code,expected", [
        (200, "ok"),
        (201, "ok"),
        (204, "ok"),
        (299, "ok"),
        (301, "redirect"),
        (302, "redirect"),
        (308, "redirect"),
        (400, "broken"),
        (403, "broken"),
        (404, "broken"),
        (410, "broken"),
        (500, "broken"),
        (502, "broken"),
        (503, "broken"),
    ])
    def test_status_to_label(self, code, expected):
        assert _classify(code) == expected


# ---------------------------------------------------------------------------
# _probe — HEAD probe with GET fallback + transport-error tolerance.
# ---------------------------------------------------------------------------


def _mock_client(*head_returns, get_return=None):
    """Build a mock httpx.AsyncClient with HEAD + GET sides."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.head = AsyncMock(side_effect=list(head_returns))
    if get_return is not None:
        client.get = AsyncMock(return_value=get_return)
    return client


def _resp(status_code: int):
    r = MagicMock()
    r.status_code = status_code
    return r


class TestProbe:
    @pytest.mark.asyncio
    async def test_invalid_url_returns_broken(self):
        for url in [None, "", "ftp://x", "not-a-url"]:
            assert await _probe(url) == "broken"

    @pytest.mark.asyncio
    async def test_200_returns_ok(self):
        with patch("httpx.AsyncClient", return_value=_mock_client(_resp(200))):
            assert await _probe("https://example.com/a") == "ok"

    @pytest.mark.asyncio
    async def test_301_returns_redirect(self):
        # follow_redirects=True is on by default, but if the server still
        # surfaces a 3xx that means redirect chain wasn't resolvable.
        with patch("httpx.AsyncClient", return_value=_mock_client(_resp(301))):
            assert await _probe("https://example.com/old") == "redirect"

    @pytest.mark.asyncio
    async def test_404_returns_broken(self):
        with patch("httpx.AsyncClient", return_value=_mock_client(_resp(404))):
            assert await _probe("https://example.com/gone") == "broken"

    @pytest.mark.asyncio
    async def test_405_head_falls_back_to_get(self):
        """Some publishers reject HEAD; we retry with ranged GET. If the
        GET succeeds, status should be ok."""
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_client(_resp(405), get_return=_resp(200)),
        ):
            assert await _probe("https://example.com/strict") == "ok"

    @pytest.mark.asyncio
    async def test_403_head_falls_back_to_get(self):
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_client(_resp(403), get_return=_resp(200)),
        ):
            assert await _probe("https://example.com/forbidden-head") == "ok"

    @pytest.mark.asyncio
    async def test_timeout_returns_broken(self):
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.head = AsyncMock(side_effect=httpx.TimeoutException("simulated"))
        with patch("httpx.AsyncClient", return_value=client):
            assert await _probe("https://example.com/slow") == "broken"

    @pytest.mark.asyncio
    async def test_connect_error_returns_broken(self):
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.head = AsyncMock(side_effect=httpx.ConnectError("dns fail"))
        with patch("httpx.AsyncClient", return_value=client):
            assert await _probe("https://nonexistent.invalid/x") == "broken"
