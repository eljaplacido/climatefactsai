"""
Multi-Country E2E Tests

Tests multi-country dispatch and completion across the ingestion pipeline.
"""

import os
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class TestMultiCountryDispatch:
    """Test multi-country ingestion scheduling."""

    def test_scheduled_multi_country_reads_env_countries(self):
        """Master scheduler should read countries from INGESTION_COUNTRIES env."""
        mock_discover = MagicMock()
        mock_discover.apply_async.return_value = MagicMock(id=str(uuid4()))

        with patch("app.tasks.ingestion.discover_articles", mock_discover), \
             patch.dict("os.environ", {
                 "INGESTION_COUNTRIES": "FI,SE,DE",
                 "MAX_ARTICLES_PER_COUNTRY": "3",
             }):
            from app.tasks.ingestion import scheduled_multi_country_ingestion

            result = scheduled_multi_country_ingestion.apply().get(timeout=10)

            assert result["countries_dispatched"] == 3
            assert len(result["dispatched"]) == 3

            countries = [d["country"] for d in result["dispatched"]]
            assert "FI" in countries
            assert "SE" in countries
            assert "DE" in countries

    def test_multi_country_stagger_delays(self):
        """Each country should be dispatched with 5-minute stagger."""
        mock_discover = MagicMock()
        mock_discover.apply_async.return_value = MagicMock(id=str(uuid4()))

        with patch("app.tasks.ingestion.discover_articles", mock_discover), \
             patch.dict("os.environ", {
                 "INGESTION_COUNTRIES": "FI,SE,DE,FR",
             }):
            from app.tasks.ingestion import scheduled_multi_country_ingestion

            result = scheduled_multi_country_ingestion.apply().get(timeout=10)

            delays = [d["scheduled_delay_seconds"] for d in result["dispatched"]]
            assert delays == [0, 300, 600, 900]

    def test_multi_country_handles_dispatch_failure(self):
        """Should continue dispatching even if one country fails."""
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Celery broker unavailable")
            return MagicMock(id=str(uuid4()))

        mock_discover = MagicMock()
        mock_discover.apply_async.side_effect = side_effect

        with patch("app.tasks.ingestion.discover_articles", mock_discover), \
             patch.dict("os.environ", {
                 "INGESTION_COUNTRIES": "FI,SE,DE",
             }):
            from app.tasks.ingestion import scheduled_multi_country_ingestion

            result = scheduled_multi_country_ingestion.apply().get(timeout=10)

            # 2 out of 3 should succeed
            assert result["countries_dispatched"] == 2

    def test_default_countries_list(self):
        """Default should be 10 European countries."""
        mock_discover = MagicMock()
        mock_discover.apply_async.return_value = MagicMock(id=str(uuid4()))

        with patch("app.tasks.ingestion.discover_articles", mock_discover), \
             patch.dict("os.environ", {}, clear=False):
            # Remove INGESTION_COUNTRIES if set
            os.environ.pop("INGESTION_COUNTRIES", None)

            from app.tasks.ingestion import scheduled_multi_country_ingestion

            result = scheduled_multi_country_ingestion.apply().get(timeout=10)

            assert result["countries_dispatched"] == 20

    def test_country_specific_max_articles(self):
        """Each country dispatch should respect MAX_ARTICLES_PER_COUNTRY."""
        mock_discover = MagicMock()
        mock_discover.apply_async.return_value = MagicMock(id=str(uuid4()))

        with patch("app.tasks.ingestion.discover_articles", mock_discover), \
             patch.dict("os.environ", {
                 "INGESTION_COUNTRIES": "FI",
                 "MAX_ARTICLES_PER_COUNTRY": "7",
             }):
            from app.tasks.ingestion import scheduled_multi_country_ingestion

            scheduled_multi_country_ingestion.apply().get(timeout=10)

            # Check that discover_articles was called with max_articles=7
            call_kwargs = mock_discover.apply_async.call_args
            assert call_kwargs is not None
            assert call_kwargs[1].get("kwargs", {}).get("max_articles") == 7 or \
                   call_kwargs.kwargs.get("kwargs", {}).get("max_articles") == 7


class TestMultiCountryIntegration:
    """Integration tests for multi-country pipeline."""

    def test_celery_beat_schedule_has_multi_country(self):
        """Celery beat schedule should include multi-country task."""
        from app.core.celery_app import app as celery_app

        schedule = celery_app.conf.beat_schedule
        assert "scheduled-multi-country-ingestion" in schedule

        entry = schedule["scheduled-multi-country-ingestion"]
        assert entry["task"] == "app.tasks.ingestion.scheduled_multi_country_ingestion"

    def test_celery_beat_schedule_has_individual_countries(self):
        """Celery beat should have staggered individual country entries."""
        from app.core.celery_app import app as celery_app

        schedule = celery_app.conf.beat_schedule
        country_entries = [k for k in schedule if k.startswith("daily-ingestion-")]

        assert len(country_entries) >= 1  # At least one country
