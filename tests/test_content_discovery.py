"""
Content Discovery Agent - Yksikkötestit
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

try:
    from content_discovery.claim_extractor import ClaimExtractor
    from content_discovery.scraper import NewsScraperPool
except ImportError:
    pytest.skip(
        "Legacy agents/content_discovery module not found — skipping",
        allow_module_level=True,
    )


class TestClaimExtractor:
    """Testit ClaimExtractor-luokalle"""
    
    @pytest.fixture
    def extractor(self):
        """Fixture: luo ClaimExtractor-instanssi"""
        return ClaimExtractor(logger=None)
    
    def test_extract_claims_with_numbers(self, extractor):
        """Testaa että numeerinen väite tunnistetaan"""
        text = "Lämpötila on noussut 2 astetta viimeisen 50 vuoden aikana."
        
        claims = extractor.extract_claims(text)
        
        assert len(claims) > 0
        assert any("2 astetta" in claim["claimText"] for claim in claims)
    
    def test_extract_claims_with_projection(self, extractor):
        """Testaa että projektioväite tunnistetaan"""
        text = "Merenpinta nousee metrin vuoteen 2100 mennessä."
        
        claims = extractor.extract_claims(text)
        
        assert len(claims) > 0
        assert any("nousee" in claim["claimText"].lower() for claim in claims)
    
    def test_extract_claims_with_research(self, extractor):
        """Testaa että tutkimusviittaus tunnistetaan"""
        text = "Tutkimuksen mukaan ilmastonmuutos kiihtyy."
        
        claims = extractor.extract_claims(text)
        
        assert len(claims) > 0
        claim_types = [claim["claimType"] for claim in claims]
        assert "scientific_claim" in claim_types or "factual_data" in claim_types
    
    def test_claim_has_id(self, extractor):
        """Testaa että jokaisella väitteellä on yksilöllinen ID"""
        text = "Lämpötila nousee 3 astetta. Sateet lisääntyvät 20 prosenttia."
        
        claims = extractor.extract_claims(text)
        
        ids = [claim["claimId"] for claim in claims]
        assert len(ids) == len(set(ids))  # Kaikki ID:t ovat uniikkeja
    
    def test_claim_has_context(self, extractor):
        """Testaa että väitteelle ekstraktoidaan konteksti"""
        text = "Alkuteksti. Lämpötila on noussut 2 astetta. Lopputeksti."
        
        claims = extractor.extract_claims(text)
        
        if claims:
            assert "context" in claims[0]
            assert len(claims[0]["context"]) > 0
    
    def test_empty_text_returns_empty_claims(self, extractor):
        """Testaa että tyhjä teksti palauttaa tyhjän listan"""
        claims = extractor.extract_claims("")
        assert claims == []
    
    def test_location_added_to_claim(self, extractor):
        """Testaa että paikkatieto lisätään väitteeseen"""
        text = "Lämpötila on noussut 2 astetta."
        location = {
            "name": "Helsinki",
            "latitude": 60.1699,
            "longitude": 24.9384,
            "country": "FI"
        }
        
        claims = extractor.extract_claims(text, location=location)
        
        if claims:
            assert "location" in claims[0]
            assert claims[0]["location"]["name"] == "Helsinki"


class TestNewsScraperPool:
    """Testit NewsScraperPool-luokalle"""
    
    @pytest.fixture
    def scraper_pool(self):
        """Fixture: luo NewsScraperPool-instanssi"""
        return NewsScraperPool(
            max_concurrent=5,
            rate_limit_delay=0.1,  # Lyhyt viive testeille
            logger=None
        )
    
    def test_initialization(self, scraper_pool):
        """Testaa että scraper pool alustuu oikein"""
        assert scraper_pool.max_concurrent == 5
        assert scraper_pool.rate_limit_delay == 0.1
        assert scraper_pool.session is not None
    
    def test_is_rss_feed_detection(self, scraper_pool):
        """Testaa RSS-feedin tunnistus"""
        assert scraper_pool._is_rss_feed("https://example.com/feed.rss")
        assert scraper_pool._is_rss_feed("https://example.com/rss.xml")
        assert scraper_pool._is_rss_feed("https://example.com/atom.xml")
        assert not scraper_pool._is_rss_feed("https://example.com/article")
    
    def test_matches_keywords(self, scraper_pool):
        """Testaa avainsanojen matchaus"""
        entry = {
            "title": "Ilmastonmuutos kiihtyy",
            "summary": "Tutkimus osoittaa..."
        }
        
        keywords = ["ilmasto", "climate"]
        assert scraper_pool._matches_keywords(entry, keywords)
        
        keywords_no_match = ["talous", "economy"]
        assert not scraper_pool._matches_keywords(entry, keywords_no_match)
    
    def test_normalize_url(self, scraper_pool):
        """Testaa URL:n normalisointi"""
        base = "https://example.com/news/"
        
        # Suhteellinen URL
        relative = "article/123"
        normalized = scraper_pool._normalize_url(relative, base)
        assert normalized == "https://example.com/news/article/123"
        
        # Absoluuttinen URL
        absolute = "https://other.com/page"
        normalized = scraper_pool._normalize_url(absolute, base)
        assert normalized == "https://other.com/page"
    
    @patch('content_discovery.scraper.requests.Session.get')
    def test_fetch_article_content_success(self, mock_get, scraper_pool):
        """Testaa artikkelin sisällön haku"""
        # Mock HTTP-vastaus
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"""
        <html>
            <head><title>Test Article</title></head>
            <body>
                <h1>Test Title</h1>
                <article>
                    <p>This is a test article about climate change.</p>
                    <p>It contains multiple paragraphs with enough content to pass the length check.</p>
                    <p>Climate change is affecting our planet in many ways.</p>
                </article>
            </body>
        </html>
        """
        mock_get.return_value = mock_response
        
        article = scraper_pool._fetch_article_content("https://example.com/article")
        
        assert article is not None
        assert article["url"] == "https://example.com/article"
        assert "climate" in article["extracted_text"].lower()
        assert len(article["extracted_text"]) >= 200
    
    @patch('content_discovery.scraper.requests.Session.get')
    def test_fetch_article_content_too_short(self, mock_get, scraper_pool):
        """Testaa että liian lyhyet artikkelit hylätään"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"<html><body><p>Short.</p></body></html>"
        mock_get.return_value = mock_response
        
        article = scraper_pool._fetch_article_content("https://example.com/short")
        
        assert article is None
    
    def test_rate_limiting(self, scraper_pool):
        """Testaa että rate limiting toimii"""
        import time
        
        url = "https://example.com/test"
        
        # Ensimmäinen kutsu
        start_time = time.time()
        scraper_pool._apply_rate_limit(url)
        
        # Toinen kutsu heti perään
        scraper_pool._apply_rate_limit(url)
        elapsed = time.time() - start_time
        
        # Pitäisi olla vähintään rate_limit_delay
        assert elapsed >= scraper_pool.rate_limit_delay
    
    def test_close(self, scraper_pool):
        """Testaa että close sulkee session"""
        scraper_pool.close()
        # Session pitäisi olla suljettu
        # (ei ole helppo testata, mutta ainakin varmistetaan ettei kaadu)


@pytest.mark.integration
class TestContentDiscoveryIntegration:
    """Integraatiotestit koko Content Discovery -agentille"""
    
    @pytest.fixture
    def mock_kafka(self):
        """Mock Kafka-asiakas"""
        with patch('content_discovery.main.KafkaClient') as mock:
            yield mock
    
    @pytest.fixture
    def mock_databases(self):
        """Mock tietokannat"""
        with patch('content_discovery.main.get_redis') as mock_redis, \
             patch('content_discovery.main.get_postgres') as mock_postgres:
            yield mock_redis, mock_postgres
    
    def test_agent_initialization(self, mock_kafka, mock_databases):
        """Testaa että agentti alustuu oikein"""
        from content_discovery.main import ContentDiscoveryAgent
        
        agent = ContentDiscoveryAgent()
        
        assert agent.logger is not None
        assert agent.kafka is not None
        assert agent.scraper_pool is not None
        assert agent.claim_extractor is not None
    
    @patch('content_discovery.main.ContentDiscoveryAgent._scan_sources')
    @patch('content_discovery.main.ContentDiscoveryAgent._process_article')
    def test_handle_discovery_task(
        self,
        mock_process,
        mock_scan,
        mock_kafka,
        mock_databases
    ):
        """Testaa discovery-käskyn käsittely"""
        from content_discovery.main import ContentDiscoveryAgent
        
        # Mock scan_sources palauttamaan test-artikkelit
        mock_scan.return_value = [
            {"url": "https://example.com/1", "title": "Test 1"},
            {"url": "https://example.com/2", "title": "Test 2"}
        ]
        mock_process.return_value = True
        
        agent = ContentDiscoveryAgent()
        
        message = {
            "command": "discover_content",
            "taskId": "task-20251010-001",
            "parameters": {
                "targetLocation": {
                    "name": "Helsinki",
                    "latitude": 60.1699,
                    "longitude": 24.9384,
                    "country": "FI"
                },
                "dateRange": {
                    "from": "2025-10-09",
                    "to": "2025-10-10"
                }
            }
        }
        
        result = agent._handle_discovery_task(message)
        
        assert result is True
        assert mock_scan.called
        assert mock_process.call_count == 2  # 2 artikkelia


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


