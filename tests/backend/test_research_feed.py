"""Research feed — CrossRef mapping + poller behaviour pins (deferred #13).

The route-handler database glue is integration-tested in CI when the
real Postgres is up. Here we pin the parts that have non-trivial logic
without I/O:
  - _crossref_to_item mapping (handles weird CrossRef shapes)
  - _poll_crossref tolerance of HTTP errors / malformed responses
"""

from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from api.research_feed_routes import (
    _crossref_to_item,
    _poll_crossref,
    _auth_admin,
)


# ---------------------------------------------------------------------------
# CrossRef → feed_item mapping.
# ---------------------------------------------------------------------------


class TestCrossrefMapping:
    def test_full_record_maps_cleanly(self):
        work = {
            "DOI": "10.1038/s41586-024-01234-5",
            "title": ["Arctic sea ice extent declined 12% in 2024"],
            "author": [
                {"given": "Jane", "family": "Doe"},
                {"given": "K", "family": "Smith"},
            ],
            "container-title": ["Nature Climate Change"],
            "issued": {"date-parts": [[2024, 7, 15]]},
            "URL": "https://doi.org/10.1038/s41586-024-01234-5",
            "abstract": "We show...",
        }
        item = _crossref_to_item(work)
        assert item is not None
        assert item["doi"] == "10.1038/s41586-024-01234-5"
        assert item["title"] == "Arctic sea ice extent declined 12% in 2024"
        assert item["authors"] == ["Jane Doe", "K Smith"]
        assert item["journal"] == "Nature Climate Change"
        assert item["published_date"] == date(2024, 7, 15)
        assert item["crossref_url"].endswith("01234-5")

    def test_missing_title_returns_none(self):
        # CrossRef occasionally returns work entries without a title (data
        # quality issue). Those should be dropped, not crash the poller.
        assert _crossref_to_item({"DOI": "10.x/y"}) is None
        assert _crossref_to_item({"DOI": "10.x/y", "title": []}) is None

    def test_year_only_date_handled(self):
        work = {
            "title": ["Year-only paper"],
            "issued": {"date-parts": [[2023]]},
        }
        item = _crossref_to_item(work)
        assert item is not None
        # Defaults month=1 day=1 when CrossRef gives only the year.
        assert item["published_date"] == date(2023, 1, 1)

    def test_no_authors_yields_empty_list(self):
        work = {"title": ["Anonymous paper"], "issued": {"date-parts": [[2024]]}}
        item = _crossref_to_item(work)
        assert item is not None
        assert item["authors"] == []

    def test_author_partial_names_dont_crash(self):
        # CrossRef rows may have only family name (consortia, e.g. "IPCC").
        work = {
            "title": ["Partial author paper"],
            "author": [{"family": "IPCC"}, {"given": "First"}],
        }
        item = _crossref_to_item(work)
        assert item["authors"] == ["IPCC", "First"]


# ---------------------------------------------------------------------------
# _poll_crossref — transport tolerance.
# ---------------------------------------------------------------------------


def _mock_client(get_return):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=get_return)
    return client


def _mock_resp(status=200, json_payload=None):
    r = MagicMock()
    r.status_code = status
    r.json = MagicMock(return_value=(json_payload or {}))
    return r


class TestPollCrossref:
    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self):
        result = await _poll_crossref("")
        assert result == []
        result = await _poll_crossref("   ")
        assert result == []

    @pytest.mark.asyncio
    async def test_http_error_returns_empty(self):
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_client(_mock_resp(status=503)),
        ):
            assert await _poll_crossref("arctic ice") == []

    @pytest.mark.asyncio
    async def test_malformed_response_returns_empty(self):
        # CrossRef returned 200 but with unexpected shape — don't crash.
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_client(_mock_resp(json_payload={"not_message": []})),
        ):
            assert await _poll_crossref("x") == []

    @pytest.mark.asyncio
    async def test_happy_path_returns_items(self):
        payload = {
            "message": {
                "items": [
                    {
                        "DOI": "10.x/1",
                        "title": ["Paper One"],
                        "issued": {"date-parts": [[2024]]},
                    },
                    {
                        "DOI": "10.x/2",
                        "title": ["Paper Two"],
                        "issued": {"date-parts": [[2024]]},
                    },
                    {
                        # No title → dropped.
                        "DOI": "10.x/3",
                    },
                ]
            }
        }
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_client(_mock_resp(json_payload=payload)),
        ):
            items = await _poll_crossref("climate")
        assert len(items) == 2
        assert items[0]["doi"] == "10.x/1"
        assert items[1]["doi"] == "10.x/2"

    @pytest.mark.asyncio
    async def test_request_error_returns_empty(self):
        import httpx

        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(side_effect=httpx.ConnectTimeout("simulated"))
        with patch("httpx.AsyncClient", return_value=client):
            assert await _poll_crossref("climate") == []


# ---------------------------------------------------------------------------
# Admin token gate.
# ---------------------------------------------------------------------------


class TestAdminAuthGate:
    def test_503_when_env_var_missing(self, monkeypatch):
        from fastapi import HTTPException

        monkeypatch.delenv("CORPORATE_SYNC_TOKEN", raising=False)
        with pytest.raises(HTTPException) as exc:
            _auth_admin("any-token")
        assert exc.value.status_code == 503

    def test_401_on_wrong_token(self, monkeypatch):
        from fastapi import HTTPException

        monkeypatch.setenv("CORPORATE_SYNC_TOKEN", "expected")
        with pytest.raises(HTTPException) as exc:
            _auth_admin("wrong")
        assert exc.value.status_code == 401

    def test_passes_on_correct_token(self, monkeypatch):
        monkeypatch.setenv("CORPORATE_SYNC_TOKEN", "expected")
        # Returns None — no exception is the contract.
        assert _auth_admin("expected") is None
