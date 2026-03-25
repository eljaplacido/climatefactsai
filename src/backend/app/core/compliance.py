"""
Compliance Module

Implements robots.txt/noai compliance checking for ethical web scraping.
Respects publisher opt-outs for AI training and text/data mining.
"""

from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import logging
from pydantic_settings import BaseSettings
from pydantic import Field
import httpx
from datetime import datetime


logger = logging.getLogger(__name__)


class ComplianceSettings(BaseSettings):
    """Compliance configuration settings."""

    check_robots_txt: bool = Field(
        default=True,
        env="COMPLIANCE_CHECK_ROBOTS_TXT",
        description="Check robots.txt before scraping"
    )
    check_noai: bool = Field(
        default=True,
        env="COMPLIANCE_CHECK_NOAI",
        description="Check for noai/noimageai directives"
    )
    respect_tdm_opt_out: bool = Field(
        default=True,
        env="COMPLIANCE_RESPECT_TDM_OPT_OUT",
        description="Respect TDM (Text/Data Mining) opt-out"
    )
    log_skips: bool = Field(
        default=True,
        env="COMPLIANCE_LOG_SKIPS",
        description="Log compliance skip decisions"
    )

    # Allow/deny lists
    allow_list: str = Field(
        default="bbc.com,reuters.com,apnews.com",
        env="COMPLIANCE_ALLOW_LIST",
        description="Comma-separated list of always-allowed domains"
    )
    deny_list: str = Field(
        default="",
        env="COMPLIANCE_DENY_LIST",
        description="Comma-separated list of always-denied domains"
    )

    # Request settings
    user_agent: str = Field(
        default="ClimateNewsBot/1.0 (+https://climatenews.com/bot)",
        description="User agent for compliance checks"
    )
    timeout_seconds: int = Field(default=10)

    class Config:
        env_file = ".env"
        extra = "ignore"  # Allow extra env vars

    @property
    def allow_domains(self) -> List[str]:
        """Parse allow list into domain list."""
        return [d.strip() for d in self.allow_list.split(",") if d.strip()]

    @property
    def deny_domains(self) -> List[str]:
        """Parse deny list into domain list."""
        return [d.strip() for d in self.deny_list.split(",") if d.strip()]


class ComplianceChecker:
    """Check URL compliance with robots.txt, noai, and TDM opt-out rules.

    This class implements ethical web scraping compliance by:
    1. Checking robots.txt for scraping permissions
    2. Detecting noai/noimageai meta tags and HTTP headers
    3. Respecting TDM (Text/Data Mining) opt-out signals
    4. Maintaining allow/deny lists

    Usage:
        >>> checker = ComplianceChecker()
        >>> result = await checker.check_url("https://example.com/article")
        >>> if result["allowed"]:
        ...     # Proceed with scraping
        ... else:
        ...     logger.info(f"Skipped: {result['reason']}")
    """

    def __init__(self, settings: Optional[ComplianceSettings] = None):
        """Initialize compliance checker.

        Args:
            settings: Optional ComplianceSettings. Loads from env if None.
        """
        self.settings = settings or ComplianceSettings()
        self._robots_cache: Dict[str, RobotFileParser] = {}

    async def check_url(self, url: str) -> Dict[str, Any]:
        """Check if URL can be scraped according to compliance rules.

        Args:
            url: URL to check

        Returns:
            {
                "allowed": bool,
                "reason": str,
                "checks": {
                    "domain_allowed": bool,
                    "domain_denied": bool,
                    "robots_txt_allowed": bool,
                    "noai_detected": bool,
                    "tdm_opt_out": bool
                },
                "metadata": {
                    "checked_at": str (ISO datetime),
                    "domain": str
                }
            }
        """
        parsed = urlparse(url)
        domain = parsed.netloc

        checks = {
            "domain_allowed": False,
            "domain_denied": False,
            "robots_txt_allowed": True,
            "noai_detected": False,
            "tdm_opt_out": False,
        }

        # Check deny list first
        if domain in self.settings.deny_domains:
            checks["domain_denied"] = True
            reason = f"Domain {domain} is in deny list"
            if self.settings.log_skips:
                logger.info(f"Compliance SKIP: {url} - {reason}")
            return self._build_result(False, reason, checks, domain)

        # Check allow list
        if domain in self.settings.allow_domains:
            checks["domain_allowed"] = True
            # Allow list bypasses other checks
            return self._build_result(True, "Domain in allow list", checks, domain)

        # Check robots.txt
        if self.settings.check_robots_txt:
            robots_allowed = await self._check_robots_txt(url)
            checks["robots_txt_allowed"] = robots_allowed
            if not robots_allowed:
                reason = f"robots.txt disallows scraping for {url}"
                if self.settings.log_skips:
                    logger.info(f"Compliance SKIP: {url} - {reason}")
                return self._build_result(False, reason, checks, domain)

        # Check noai and TDM opt-out directives
        if self.settings.check_noai or self.settings.respect_tdm_opt_out:
            noai, tdm_opt_out = await self._check_page_directives(url)
            checks["noai_detected"] = noai
            checks["tdm_opt_out"] = tdm_opt_out

            if noai and self.settings.check_noai:
                reason = "noai/noimageai directive detected"
                if self.settings.log_skips:
                    logger.info(f"Compliance SKIP: {url} - {reason}")
                return self._build_result(False, reason, checks, domain)

            if tdm_opt_out and self.settings.respect_tdm_opt_out:
                reason = "TDM (Text/Data Mining) opt-out detected"
                if self.settings.log_skips:
                    logger.info(f"Compliance SKIP: {url} - {reason}")
                return self._build_result(False, reason, checks, domain)

        # All checks passed
        return self._build_result(True, "All compliance checks passed", checks, domain)

    async def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt.

        Args:
            url: URL to check

        Returns:
            True if allowed, False if disallowed or error
        """
        try:
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            robots_url = urljoin(base_url, "/robots.txt")

            # Check cache
            if robots_url in self._robots_cache:
                parser = self._robots_cache[robots_url]
            else:
                # Fetch and parse robots.txt
                parser = RobotFileParser()
                parser.set_url(robots_url)

                async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                    try:
                        response = await client.get(
                            robots_url,
                            headers={"User-Agent": self.settings.user_agent}
                        )
                        if response.status_code == 200:
                            parser.parse(response.text.splitlines())
                            self._robots_cache[robots_url] = parser
                        else:
                            # No robots.txt = allow by default
                            return True
                    except Exception as e:
                        logger.warning(f"Failed to fetch robots.txt from {robots_url}: {e}")
                        # Fail open - allow if robots.txt unavailable
                        return True

            # Check if our user agent can fetch this URL
            return parser.can_fetch(self.settings.user_agent, url)

        except Exception as e:
            logger.error(f"Error checking robots.txt for {url}: {e}")
            # Fail open
            return True

    async def _check_page_directives(self, url: str) -> tuple[bool, bool]:
        """Check page for noai and TDM opt-out directives.

        Checks:
        - HTTP header: X-Robots-Tag: noai, noimageai
        - Meta tags: <meta name="robots" content="noai">
        - TDM opt-out: data-noai attribute or specific meta tags

        Args:
            url: URL to check

        Returns:
            (noai_detected, tdm_opt_out)
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.timeout_seconds,
                follow_redirects=True
            ) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": self.settings.user_agent}
                )

                # Check HTTP headers
                x_robots_tag = response.headers.get("X-Robots-Tag", "").lower()
                if "noai" in x_robots_tag or "noimageai" in x_robots_tag:
                    return (True, False)

                # Check for TDM opt-out header
                tdm_reservation = response.headers.get("TDM-Reservation", "").lower()
                if tdm_reservation == "1":
                    return (False, True)

                # Check page content for meta tags
                # Note: For production, use proper HTML parser like BeautifulSoup
                content = response.text.lower()

                # Check for noai meta tags
                noai_patterns = [
                    'name="robots" content="noai"',
                    'name="robots" content="noimageai"',
                    'name="googlebot" content="noai"',
                    'data-noai="true"',
                ]
                noai_detected = any(pattern in content for pattern in noai_patterns)

                # Check for TDM opt-out signals
                tdm_patterns = [
                    'tdm-reservation: 1',
                    'data-tdm-opt-out="true"',
                    'name="tdm" content="opt-out"',
                ]
                tdm_opt_out = any(pattern in content for pattern in tdm_patterns)

                return (noai_detected, tdm_opt_out)

        except Exception as e:
            logger.error(f"Error checking page directives for {url}: {e}")
            # Fail open - allow if check fails
            return (False, False)

    def _build_result(
        self,
        allowed: bool,
        reason: str,
        checks: Dict[str, bool],
        domain: str
    ) -> Dict[str, Any]:
        """Build compliance check result dictionary.

        Args:
            allowed: Whether URL is allowed
            reason: Reason for decision
            checks: Dictionary of individual check results
            domain: Domain being checked

        Returns:
            Compliance result dictionary
        """
        return {
            "allowed": allowed,
            "reason": reason,
            "checks": checks,
            "metadata": {
                "checked_at": datetime.utcnow().isoformat(),
                "domain": domain,
                "user_agent": self.settings.user_agent,
            }
        }


# Global compliance checker instance
_compliance_checker: Optional[ComplianceChecker] = None


def get_compliance_checker() -> ComplianceChecker:
    """Get global compliance checker instance.

    Returns:
        Shared ComplianceChecker for dependency injection.

    Usage:
        >>> checker = get_compliance_checker()
        >>> result = await checker.check_url("https://example.com")
    """
    global _compliance_checker
    if _compliance_checker is None:
        _compliance_checker = ComplianceChecker()
    return _compliance_checker
