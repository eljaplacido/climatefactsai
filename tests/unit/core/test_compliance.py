"""
Unit tests for Compliance module.

Tests ComplianceChecker functionality with mocked HTTP requests.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.core.compliance import (
    ComplianceSettings,
    ComplianceChecker,
    get_compliance_checker,
)


class TestComplianceSettings:
    """Test ComplianceSettings class."""

    def test_default_settings(self):
        """Test default compliance settings."""
        settings = ComplianceSettings()

        assert settings.check_robots_txt is True
        assert settings.check_noai is True
        assert settings.respect_tdm_opt_out is True
        assert settings.log_skips is True

    def test_allow_domains_property(self):
        """Test allow_domains property parsing."""
        settings = ComplianceSettings(allow_list="bbc.com,reuters.com,apnews.com")

        domains = settings.allow_domains
        assert len(domains) == 3
        assert "bbc.com" in domains
        assert "reuters.com" in domains

    def test_deny_domains_property(self):
        """Test deny_domains property parsing."""
        settings = ComplianceSettings(deny_list="spam.com,malicious.net")

        domains = settings.deny_domains
        assert len(domains) == 2
        assert "spam.com" in domains
        assert "malicious.net" in domains

    def test_empty_lists(self):
        """Test empty allow/deny lists."""
        settings = ComplianceSettings(allow_list="", deny_list="")

        assert settings.allow_domains == []
        assert settings.deny_domains == []


class TestComplianceChecker:
    """Test ComplianceChecker class."""

    @pytest.fixture
    def checker(self):
        """Create ComplianceChecker instance."""
        settings = ComplianceSettings(
            allow_list="allowed.com",
            deny_list="denied.com"
        )
        return ComplianceChecker(settings)

    @pytest.mark.asyncio
    async def test_check_url_denied_domain(self, checker):
        """Test URL from deny list."""
        result = await checker.check_url("https://denied.com/article")

        assert result["allowed"] is False
        assert "deny list" in result["reason"]
        assert result["checks"]["domain_denied"] is True

    @pytest.mark.asyncio
    async def test_check_url_allowed_domain(self, checker):
        """Test URL from allow list (bypasses other checks)."""
        result = await checker.check_url("https://allowed.com/article")

        assert result["allowed"] is True
        assert "allow list" in result["reason"]
        assert result["checks"]["domain_allowed"] is True

    @pytest.mark.asyncio
    async def test_check_url_robots_txt_disallowed(self, checker):
        """Test URL disallowed by robots.txt."""
        with patch.object(checker, "_check_robots_txt", new_callable=AsyncMock) as mock_robots:
            mock_robots.return_value = False

            result = await checker.check_url("https://example.com/private")

            assert result["allowed"] is False
            assert "robots.txt" in result["reason"]
            assert result["checks"]["robots_txt_allowed"] is False

    @pytest.mark.asyncio
    async def test_check_url_noai_detected(self, checker):
        """Test URL with noai directive."""
        with patch.object(checker, "_check_robots_txt", new_callable=AsyncMock) as mock_robots:
            with patch.object(checker, "_check_page_directives", new_callable=AsyncMock) as mock_directives:
                mock_robots.return_value = True
                mock_directives.return_value = (True, False)  # noai=True, tdm=False

                result = await checker.check_url("https://example.com/article")

                assert result["allowed"] is False
                assert "noai" in result["reason"]
                assert result["checks"]["noai_detected"] is True

    @pytest.mark.asyncio
    async def test_check_url_tdm_opt_out(self, checker):
        """Test URL with TDM opt-out."""
        with patch.object(checker, "_check_robots_txt", new_callable=AsyncMock) as mock_robots:
            with patch.object(checker, "_check_page_directives", new_callable=AsyncMock) as mock_directives:
                mock_robots.return_value = True
                mock_directives.return_value = (False, True)  # noai=False, tdm=True

                result = await checker.check_url("https://example.com/article")

                assert result["allowed"] is False
                assert "TDM" in result["reason"] or "opt-out" in result["reason"]
                assert result["checks"]["tdm_opt_out"] is True

    @pytest.mark.asyncio
    async def test_check_url_all_checks_pass(self, checker):
        """Test URL that passes all compliance checks."""
        with patch.object(checker, "_check_robots_txt", new_callable=AsyncMock) as mock_robots:
            with patch.object(checker, "_check_page_directives", new_callable=AsyncMock) as mock_directives:
                mock_robots.return_value = True
                mock_directives.return_value = (False, False)  # No opt-outs

                result = await checker.check_url("https://example.com/article")

                assert result["allowed"] is True
                assert "passed" in result["reason"]

    @pytest.mark.asyncio
    async def test_check_robots_txt_allowed(self, checker):
        """Test _check_robots_txt when allowed."""
        robots_content = """User-agent: *
Allow: /articles/
Disallow: /admin/"""

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = robots_content

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            result = await checker._check_robots_txt("https://example.com/articles/climate")

            assert result is True

    @pytest.mark.asyncio
    async def test_check_robots_txt_no_file(self, checker):
        """Test _check_robots_txt when robots.txt doesn't exist."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 404

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            result = await checker._check_robots_txt("https://example.com/article")

            # No robots.txt = allow by default
            assert result is True

    @pytest.mark.asyncio
    async def test_check_robots_txt_caching(self, checker):
        """Test that robots.txt is cached."""
        robots_content = "User-agent: *\nAllow: /"

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = robots_content

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            # First call - should fetch
            await checker._check_robots_txt("https://example.com/page1")
            assert mock_client.call_count == 1

            # Second call - should use cache
            await checker._check_robots_txt("https://example.com/page2")
            assert mock_client.call_count == 1  # Not incremented

    @pytest.mark.asyncio
    async def test_check_page_directives_noai_header(self, checker):
        """Test detection of noai in X-Robots-Tag header."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.headers = {"X-Robots-Tag": "noai, nofollow"}
            mock_response.text = "<html></html>"

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            noai, tdm = await checker._check_page_directives("https://example.com/article")

            assert noai is True
            assert tdm is False

    @pytest.mark.asyncio
    async def test_check_page_directives_tdm_header(self, checker):
        """Test detection of TDM-Reservation header."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.headers = {"TDM-Reservation": "1"}
            mock_response.text = "<html></html>"

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            noai, tdm = await checker._check_page_directives("https://example.com/article")

            assert noai is False
            assert tdm is True

    @pytest.mark.asyncio
    async def test_check_page_directives_meta_tags(self, checker):
        """Test detection of noai in meta tags."""
        html_content = """
        <html>
        <head>
            <meta name="robots" content="noai">
        </head>
        <body>Article content</body>
        </html>
        """

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.headers = {}
            mock_response.text = html_content

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            noai, tdm = await checker._check_page_directives("https://example.com/article")

            assert noai is True

    @pytest.mark.asyncio
    async def test_check_page_directives_error_handling(self, checker):
        """Test graceful error handling in _check_page_directives."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Network error")
            )
            mock_client.return_value = mock_context

            # Should fail open (allow)
            noai, tdm = await checker._check_page_directives("https://example.com/article")

            assert noai is False
            assert tdm is False

    def test_build_result(self, checker):
        """Test _build_result method."""
        checks = {
            "domain_allowed": False,
            "domain_denied": False,
            "robots_txt_allowed": True,
        }

        result = checker._build_result(
            allowed=True,
            reason="Test reason",
            checks=checks,
            domain="example.com"
        )

        assert result["allowed"] is True
        assert result["reason"] == "Test reason"
        assert result["checks"] == checks
        assert result["metadata"]["domain"] == "example.com"
        assert "checked_at" in result["metadata"]
        assert "user_agent" in result["metadata"]


class TestGetComplianceChecker:
    """Test get_compliance_checker function."""

    def test_returns_checker_instance(self):
        """Test that function returns ComplianceChecker instance."""
        checker = get_compliance_checker()

        assert isinstance(checker, ComplianceChecker)

    def test_singleton_pattern(self):
        """Test that get_compliance_checker returns the same instance."""
        # Reset singleton
        import app.core.compliance as compliance_module
        compliance_module._compliance_checker = None

        checker1 = get_compliance_checker()
        checker2 = get_compliance_checker()

        # Should return same instance
        assert checker1 is checker2


@pytest.mark.integration
@pytest.mark.skipif(
    True,  # Integration tests require live HTTP endpoints
    reason="Integration tests disabled by default (set RUN_INTEGRATION=1 to enable)"
)
class TestComplianceCheckerIntegration:
    """Integration tests with real HTTP requests."""

    @pytest.fixture
    def real_checker(self):
        """Create ComplianceChecker for integration tests."""
        return ComplianceChecker()

    @pytest.mark.asyncio
    async def test_check_bbc_robots_txt(self, real_checker):
        """Test checking BBC's robots.txt (real request)."""
        # BBC should allow crawling
        result = await real_checker._check_robots_txt("https://www.bbc.com/news")

        # May vary by actual robots.txt content
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_check_real_url_workflow(self, real_checker):
        """Test full compliance check workflow with real URL."""
        # Use a known public URL
        result = await real_checker.check_url("https://www.example.com")

        # Verify structure
        assert "allowed" in result
        assert "reason" in result
        assert "checks" in result
        assert "metadata" in result
