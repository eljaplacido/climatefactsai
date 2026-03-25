"""
Content Discovery Agent - Pääohjelma

Vastaa:
1. Uutislähteiden skannaaminen
2. Artikkelien kerääminen ja ekstraktointi
3. Väitteiden tunnistaminen NLP:llä
4. Datan lähetys Fact-Checking -agentille
"""

import asyncio
import signal
import sys
from typing import Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import get_settings
from shared.logger import setup_logging, LoggerMixin
from shared.kafka_client import KafkaClient
from shared.database import get_redis, get_postgres

from content_discovery.scraper import NewsScraperPool
from content_discovery.claim_extractor import ClaimExtractor


class ContentDiscoveryAgent(LoggerMixin):
    """
    Content Discovery -agentti
    
    Kuuntelee discovery_queue -aihetta ja käsittelee sisällön löytämiskäskyjä.
    """
    
    def __init__(self):
        """Alusta Content Discovery -agentti"""
        self.setup_logger("content_discovery")
        self.settings = get_settings()
        
        # Kafka-asiakas
        self.kafka = KafkaClient(agent_name="content_discovery")
        
        # Tietokannat
        self.redis = get_redis()
        self.postgres = get_postgres()
        
        # Web scraper pool
        self.scraper_pool = NewsScraperPool(
            max_concurrent=self.settings.scraper.scraper_max_concurrent_requests,
            rate_limit_delay=self.settings.scraper.scraper_rate_limit_delay,
            user_agent=self.settings.scraper.scraper_user_agent,
            respect_robots_txt=self.settings.scraper.scraper_respect_robots_txt,
            logger=self.logger
        )
        
        # Claim extractor (NLP)
        self.claim_extractor = ClaimExtractor(logger=self.logger)
        
        # Shutdown flag
        self.shutdown_requested = False
        
        self.logger.info(
            "Content Discovery agent initialized",
            version="1.0.0",
            max_concurrent=self.settings.scraper.scraper_max_concurrent_requests
        )
    
    def start(self):
        """Käynnistä agentti"""
        self.logger.info("Starting Content Discovery agent...")
        
        # Rekisteröi shutdown-handlerit
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
        try:
            # Kuuntele discovery-käskyjä
            self.kafka.consume(
                topic=self.settings.kafka.kafka_topic_discovery_queue,
                message_handler=self._handle_discovery_task,
                schema_name="discovery_to_factcheck",  # Validoi output
                validate_schema=False  # Ei validoida input (käsky-viesti)
            )
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            self.shutdown()
    
    def _handle_discovery_task(self, message: Dict[str, Any]) -> bool:
        """
        Käsittele sisällön löytämiskäsky
        
        Args:
            message: Kafka-viesti sisältäen discovery-käskyn
        
        Returns:
            True jos onnistui
        """
        command = message.get("command")
        task_id = message.get("taskId")
        
        if command != "discover_content":
            self.logger.warning(f"Unknown command: {command}", task_id=task_id)
            return False
        
        self.logger.info("Starting content discovery", task_id=task_id)
        
        # Hae parametrit
        parameters = message.get("parameters", {})
        target_location = parameters.get("targetLocation", {})
        date_range = parameters.get("dateRange", {})
        
        try:
            # 1. Hae uutislähteiden lista
            news_sources = self._get_news_sources()
            
            self.logger.info(
                "Scanning news sources",
                task_id=task_id,
                source_count=len(news_sources)
            )
            
            # 2. Scannaa lähteet ja kerää artikkelit
            articles = self._scan_sources(
                sources=news_sources,
                target_location=target_location,
                date_range=date_range
            )
            
            self.logger.info(
                "Articles discovered",
                task_id=task_id,
                article_count=len(articles)
            )
            
            # 3. Käsittele jokainen artikkeli
            processed_count = 0
            for article_data in articles:
                if self._process_article(article_data, task_id, target_location):
                    processed_count += 1
            
            self.logger.info(
                "Content discovery completed",
                task_id=task_id,
                total_articles=len(articles),
                processed_articles=processed_count
            )
            
            return True
            
        except Exception as e:
            self.log_error(
                e,
                context={
                    "task_id": task_id,
                    "stage": "content_discovery"
                }
            )
            return False
    
    def _get_news_sources(self) -> List[str]:
        """
        Hae uutislähteiden lista
        
        Returns:
            Lista URL:eja
        """
        # Hae konfiguraatiosta
        sources = self.settings.location.news_sources
        
        # Voit myös hakea tietokannasta (source_credibility-taulusta)
        # sources_from_db = self.postgres.execute_query(
        #     "SELECT source_url FROM source_credibility WHERE is_active = true"
        # )
        
        if not sources:
            self.logger.warning("No news sources configured!")
            # Fallback: käytä default-lähteitä
            sources = [
                "https://yle.fi/rss/uutiset.rss",
                "https://www.hs.fi/rss/tuoreimmat.xml",
            ]
        
        return sources
    
    def _scan_sources(
        self,
        sources: List[str],
        target_location: Dict[str, Any],
        date_range: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Scannaa uutislähteet ja palauta relevantit artikkelit
        
        Args:
            sources: Lista lähde-URL:eja
            target_location: Kohdepaikan tiedot
            date_range: Päivämääräväli
        
        Returns:
            Lista artikkeli-dictionaryja
        """
        all_articles = []
        
        for source_url in sources:
            try:
                self.logger.debug(f"Scanning source: {source_url}")
                
                # Käytä scraper poolia
                articles = self.scraper_pool.scrape_source(
                    source_url=source_url,
                    keywords=[
                        "ilmasto", "climate", "ympäristö", "environment",
                        "sustainability", "kestävyys", "päästö", "emission",
                        "renewable", "uusiutuva", "energia"
                    ],
                    date_range=date_range
                )
                
                all_articles.extend(articles)
                
            except Exception as e:
                self.logger.error(
                    f"Failed to scan source: {source_url}",
                    error=str(e)
                )
                continue
        
        return all_articles
    
    def _process_article(
        self,
        article_data: Dict[str, Any],
        task_id: str,
        target_location: Dict[str, Any]
    ) -> bool:
        """
        Käsittele yksittäinen artikkeli
        
        1. Tunnista väitteet
        2. Tallenna artikkeliin tietokantaan
        3. Lähetä Fact-Checking -agentille
        
        Args:
            article_data: Artikkelin data
            task_id: Tehtävätunniste
            target_location: Kohdepaikan tiedot
        
        Returns:
            True jos onnistui
        """
        article_url = article_data.get("url")
        article_title = article_data.get("title")
        
        self.logger.debug(
            "Processing article",
            task_id=task_id,
            url=article_url,
            title=article_title
        )
        
        try:
            # 1. Tunnista väitteet tekstistä
            extracted_text = article_data.get("extracted_text", "")
            claims = self.claim_extractor.extract_claims(
                text=extracted_text,
                location=target_location
            )
            
            self.logger.debug(
                f"Claims extracted",
                task_id=task_id,
                article_url=article_url,
                claim_count=len(claims)
            )
            
            # 2. Tallenna artikkeli tietokantaan (pitkäaikainen muisti)
            article_id = self._save_article_to_db(article_data, task_id)
            
            # 3. Luo handoff-payload Fact-Checking -agentille
            handoff_payload = self._create_factcheck_payload(
                task_id=task_id,
                article_id=article_id,
                article_data=article_data,
                claims=claims
            )
            
            # 4. Lähetä Kafkaan
            success = self.kafka.produce(
                topic=self.settings.kafka.kafka_topic_factcheck_queue,
                payload=handoff_payload,
                key=task_id,
                schema_name="discovery_to_factcheck",
                validate_schema=True
            )
            
            if success:
                self.log_agent_handoff(
                    from_agent="content_discovery",
                    to_agent="fact_checking",
                    task_id=task_id,
                    payload_schema_version="1.0",
                    article_id=article_id,
                    claim_count=len(claims)
                )
            
            return success
            
        except Exception as e:
            self.log_error(
                e,
                context={
                    "task_id": task_id,
                    "article_url": article_url
                }
            )
            return False
    
    def _save_article_to_db(
        self,
        article_data: Dict[str, Any],
        task_id: str
    ) -> str:
        """
        Tallenna artikkeli PostgreSQL-tietokantaan
        
        Args:
            article_data: Artikkelin data
            task_id: Tehtävätunniste
        
        Returns:
            Article ID (UUID)
        """
        query = """
        INSERT INTO articles (
            url, title, author, published_date, source_name,
            extracted_text, language_code, task_id,
            source_credibility_score, created_at
        ) VALUES (
            :url, :title, :author, :published_date, :source_name,
            :extracted_text, :language_code, :task_id,
            :source_credibility_score, CURRENT_TIMESTAMP
        )
        ON CONFLICT (url) DO UPDATE SET
            updated_at = CURRENT_TIMESTAMP
        RETURNING article_id
        """
        
        result = self.postgres.execute_query(
            query,
            params={
                "url": article_data.get("url"),
                "title": article_data.get("title"),
                "author": article_data.get("author"),
                "published_date": article_data.get("published_date"),
                "source_name": article_data.get("source_name"),
                "extracted_text": article_data.get("extracted_text"),
                "language_code": article_data.get("language", "fi"),
                "task_id": task_id,
                "source_credibility_score": article_data.get("source_credibility_score", 50)
            }
        )
        
        article_id = result[0]["article_id"] if result else None
        
        self.logger.debug(
            "Article saved to database",
            article_id=article_id,
            url=article_data.get("url")
        )
        
        return str(article_id)
    
    def _create_factcheck_payload(
        self,
        task_id: str,
        article_id: str,
        article_data: Dict[str, Any],
        claims: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Luo strukturoitu payload Fact-Checking -agentille
        
        Args:
            task_id: Tehtävätunniste
            article_id: Artikkelin ID tietokannassa
            article_data: Artikkelin raakadata
            claims: Tunnistetut väitteet
        
        Returns:
            JSON-payload discovery_to_factcheck.json -skeeman mukaisesti
        """
        return {
            "schemaVersion": "1.0",
            "taskId": task_id,
            "articleId": article_id,
            "sourceArticle": {
                "url": article_data.get("url"),
                "title": article_data.get("title"),
                "publishedDate": article_data.get("published_date"),
                "author": article_data.get("author"),
                "source": article_data.get("source_name"),
                "sourceCredibilityScore": article_data.get("source_credibility_score", 50),
                "extractedText": article_data.get("extracted_text"),
                "language": article_data.get("language", "fi"),
                "tags": article_data.get("tags", [])
            },
            "claims": claims,
            "metadata": {
                "discoveryTimestamp": datetime.now(timezone.utc).isoformat(),
                "processingTimeMs": article_data.get("processing_time_ms", 0),
                "discoveryAgentVersion": "1.0.0"
            }
        }
    
    def _handle_shutdown(self, signum, frame):
        """Käsittele shutdown-signaali"""
        self.logger.info(f"Received shutdown signal: {signum}")
        self.shutdown_requested = True
    
    def shutdown(self):
        """Sulje agentti gracefully"""
        self.logger.info("Shutting down Content Discovery agent...")
        
        # Sulje scraper pool
        self.scraper_pool.close()
        
        # Sulje Kafka-yhteydet
        self.kafka.close()
        
        # Sulje tietokantayhteydet
        self.redis.close()
        self.postgres.close()
        
        self.logger.info("Content Discovery agent shut down successfully")


def main():
    """Pääfunktio"""
    print("=" * 60)
    print("Climate News Multi-Agent System")
    print("Content Discovery Agent v1.0.0")
    print("=" * 60)
    print()
    
    # Luo ja käynnistä agentti
    agent = ContentDiscoveryAgent()
    agent.start()


if __name__ == "__main__":
    main()


