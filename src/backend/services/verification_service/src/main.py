"""
Fact-Checking Agent - Pääohjelma

Vastaa:
1. Väitteiden todentaminen ClimateCheck API:n avulla
2. Datan ristiin tarkistaminen NOAA/NASA -lähteistä
3. Todennusraporttien luominen
4. Verifioidun datan lähetys Content Creation -agentille
"""

import signal
import sys
from typing import Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path

# Add src/backend to path for shared module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from shared.config import get_settings
from shared.logger import setup_logging, LoggerMixin
from shared.kafka_client import KafkaClient
from shared.database import get_redis, get_postgres
from shared.reliability_scorer import ReliabilityScorer

# Local imports from this service
from climate_api import OpenMeteoClient, NOAAClient, NASAPowerClient
from verifier import ClaimVerifier


class FactCheckingAgent(LoggerMixin):
    """
    Fact-Checking -agentti
    
    Kuuntelee fact_checking_queue -aihetta ja todentaa väitteitä.
    """
    
    def __init__(self):
        """Alusta Fact-Checking -agentti"""
        self.setup_logger("fact_checking")
        self.settings = get_settings()
        
        # Kafka-asiakas
        self.kafka = KafkaClient(agent_name="fact_checking")
        
        # Tietokannat
        self.redis = get_redis()
        self.postgres = get_postgres()
        
        # API-asiakkaat (kaikki ilmaiset, ei vaadi API-avaimia)
        self.open_meteo = OpenMeteoClient(
            logger=self.logger
        )

        self.noaa = NOAAClient(
            api_token=self.settings.climate_data.noaa_api_token,
            logger=self.logger
        )

        self.nasa_power = NASAPowerClient(
            logger=self.logger
        )
        
        # Verifier (uses Perplexity as primary, GPT-4o or DeepSeek as fallback)
        llm_api_key = self.settings.llm.openai_api_key
        llm_model = self.settings.llm.gpt_model
        llm_base_url = None
        if not llm_api_key and self.settings.llm.deepseek_api_key:
            llm_api_key = self.settings.llm.deepseek_api_key
            llm_model = self.settings.llm.deepseek_model
            llm_base_url = self.settings.llm.deepseek_base_url
            self.logger.info("Using DeepSeek as LLM fallback for verification")
        self.verifier = ClaimVerifier(
            openai_api_key=llm_api_key or "not-configured",
            model=llm_model,
            logger=self.logger,
            perplexity_api_key=self.settings.llm.perplexity_api_key
        )
        
        self.shutdown_requested = False
        
        self.logger.info(
            "Fact-Checking agent initialized",
            version="1.0.0"
        )
    
    def start(self):
        """Käynnistä agentti"""
        self.logger.info("Starting Fact-Checking agent...")
        
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
        try:
            # Kuuntele fact-checking -viestejä
            self.kafka.consume(
                topic=self.settings.kafka.kafka_topic_factcheck_queue,
                message_handler=self._handle_fact_check_task,
                schema_name="discovery_to_factcheck",
                validate_schema=True
            )
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            self.shutdown()
    
    def _handle_fact_check_task(self, message: Dict[str, Any]) -> bool:
        """
        Käsittele faktatarkistuskäsky
        
        Args:
            message: Kafka-viesti sisältäen artikkelin ja väitteet
        
        Returns:
            True jos onnistui
        """
        task_id = message.get("taskId")
        article_id = message.get("articleId")
        
        self.logger.info(
            "Starting fact-checking",
            task_id=task_id,
            article_id=article_id
        )
        
        try:
            source_article = message.get("sourceArticle", {})
            claims = message.get("claims", [])
            
            if not claims:
                self.logger.warning(
                    "No claims to verify",
                    task_id=task_id,
                    article_id=article_id
                )
                # Lähetä tyhjä verification
                return self._send_verified_content(
                    task_id=task_id,
                    article_id=article_id,
                    source_article=source_article,
                    verified_claims=[]
                )
            
            self.logger.info(
                f"Verifying {len(claims)} claims",
                task_id=task_id,
                claim_count=len(claims)
            )
            
            # Todenna jokainen väite
            verified_claims = []
            api_calls_made = {
                "openMeteo": 0,
                "noaa": 0,
                "nasaPower": 0
            }
            
            for claim in claims:
                verified_claim, api_calls = self._verify_claim(claim, source_article)
                verified_claims.append(verified_claim)
                
                # Päivitä API-kutsu laskurit
                for api_name, count in api_calls.items():
                    api_calls_made[api_name] += count
            
            self.logger.info(
                "Fact-checking completed",
                task_id=task_id,
                verified_claims=len(verified_claims),
                api_calls=api_calls_made
            )
            
            # Tallenna fact-checkit tietokantaan
            self._save_fact_checks_to_db(
                task_id=task_id,
                article_id=article_id,
                verified_claims=verified_claims
            )

            # Update reliability score after fact-checking
            self._update_article_reliability(article_id)

            # Lähetä Content Creation -agentille
            return self._send_verified_content(
                task_id=task_id,
                article_id=article_id,
                source_article=source_article,
                verified_claims=verified_claims,
                api_calls_made=api_calls_made
            )
            
        except Exception as e:
            self.log_error(
                e,
                context={
                    "task_id": task_id,
                    "article_id": article_id,
                    "stage": "fact_checking"
                }
            )
            return False
    
    def _verify_claim(
        self,
        claim: Dict[str, Any],
        source_article: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Dict[str, int]]:
        """
        Todenna yksittäinen väite
        
        Args:
            claim: Väite-dictionary
            source_article: Lähdeartikkeli
        
        Returns:
            (verified_claim, api_calls_count)
        """
        claim_id = claim.get("claimId")
        claim_text = claim.get("claimText")
        location = claim.get("location", {})
        
        self.logger.debug(
            "Verifying claim",
            claim_id=claim_id,
            claim_text=claim_text[:100]
        )
        
        start_time = datetime.now(timezone.utc)
        api_calls_count = {"openMeteo": 0, "noaa": 0, "nasaPower": 0}

        # 1. Hae Open-Meteo -data (primary, aina saatavilla)
        open_meteo_data = None
        if location.get("latitude") and location.get("longitude"):
            open_meteo_data = self.open_meteo.get_climate_data(
                latitude=location["latitude"],
                longitude=location["longitude"],
                days_back=30
            )
            api_calls_count["openMeteo"] = 1 if open_meteo_data else 0

        # 2. Hae NOAA-data (secondary, jos token on asetettu)
        noaa_data = None
        if self.settings.climate_data.noaa_api_token:
            noaa_data = self.noaa.get_climate_data(
                location=location.get("name", "Unknown"),
                data_type="temperature",
                latitude=location.get("latitude"),
                longitude=location.get("longitude")
            )
            api_calls_count["noaa"] = 1 if noaa_data else 0

        # 3. Hae NASA POWER -data (tertiary, täydentävä data)
        nasa_power_data = None
        if location.get("latitude") and location.get("longitude"):
            nasa_power_data = self.nasa_power.get_climate_data(
                latitude=location["latitude"],
                longitude=location["longitude"],
                days_back=30
            )
            api_calls_count["nasaPower"] = 1 if nasa_power_data else 0
        
        # 4. Käytä Perplexity/GPT-4o:ta analysoimaan kaikki data
        verification_result = self.verifier.verify_claim(
            claim_text=claim_text,
            claim_context=claim.get("context", ""),
            open_meteo_data=open_meteo_data,
            noaa_data=noaa_data,
            nasa_power_data=nasa_power_data,
            location=location.get("name")
        )
        
        # 5. Luo verified claim -objekti
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        verified_claim = {
            "claimId": claim_id,
            "claimText": claim_text,
            "claimType": claim.get("claimType", "factual_data"),
            "context": claim.get("context"),
            "verificationStatus": verification_result["status"],
            "confidence": verification_result["confidence"],
            "evidence": verification_result["evidence"],
            "justification": verification_result["justification"],
            "verifiedDate": datetime.now(timezone.utc).isoformat()
        }

        # Lisää Open-Meteo -spesifit tiedot jos saatavilla
        if open_meteo_data:
            verified_claim["climateData"] = {
                "source": "Open-Meteo",
                "hazardType": open_meteo_data.get("hazardType"),
                "riskScore": open_meteo_data.get("riskScore"),
                "data": open_meteo_data.get("data", {})
            }
        
        self.logger.debug(
            "Claim verified",
            claim_id=claim_id,
            status=verification_result["status"],
            confidence=verification_result["confidence"],
            processing_time_ms=processing_time
        )
        
        return verified_claim, api_calls_count
    
    def _save_fact_checks_to_db(
        self,
        task_id: str,
        article_id: str,
        verified_claims: List[Dict[str, Any]]
    ):
        """
        Tallenna fact-checkit tietokantaan
        
        Args:
            task_id: Tehtävätunniste
            article_id: Artikkelin ID
            verified_claims: Lista todennettuja väitteitä
        """
        for verified_claim in verified_claims:
            # Tallenna ensin claim
            claim_query = """
            INSERT INTO claims (
                claim_id, article_id, claim_text, claim_context, claim_type
            ) VALUES (
                :claim_id, :article_id, :claim_text, :claim_context, :claim_type
            )
            ON CONFLICT (claim_id) DO NOTHING
            """
            
            self.postgres.execute_update(
                claim_query,
                params={
                    "claim_id": verified_claim["claimId"],
                    "article_id": article_id,
                    "claim_text": verified_claim["claimText"],
                    "claim_context": verified_claim.get("context"),
                    "claim_type": verified_claim.get("claimType", "factual_data")
                }
            )
            
            # Tallenna fact-check
            fact_check_query = """
            INSERT INTO fact_checks (
                claim_id, verification_status, confidence_score,
                justification, evidence, task_id,
                climatecheck_hazard_type, climatecheck_risk_score
            ) VALUES (
                :claim_id, :verification_status, :confidence_score,
                :justification, :evidence, :task_id,
                :hazard_type, :risk_score
            )
            """

            import json
            climate_data = verified_claim.get("climateData", {})

            self.postgres.execute_update(
                fact_check_query,
                params={
                    "claim_id": verified_claim["claimId"],
                    "verification_status": verified_claim["verificationStatus"],
                    "confidence_score": verified_claim["confidence"],
                    "justification": verified_claim["justification"],
                    "evidence": json.dumps(verified_claim["evidence"]),
                    "task_id": task_id,
                    "hazard_type": climate_data.get("hazardType"),
                    "risk_score": climate_data.get("riskScore")
                }
            )
        
        self.logger.info(
            "Fact-checks saved to database",
            task_id=task_id,
            count=len(verified_claims)
        )

    def _update_article_reliability(self, article_id: str):
        """
        Update article's reliability score after fact-checking

        Args:
            article_id: Article UUID
        """
        try:
            result = ReliabilityScorer.update_article_reliability(
                article_id=article_id,
                postgres_client=self.postgres,
                logger=self.logger
            )

            if result:
                self.logger.info(
                    "Article reliability updated",
                    article_id=article_id,
                    reliability_score=result.get('reliability_score'),
                    credibility_level=result.get('credibility_level')
                )
        except Exception as e:
            self.logger.error(
                "Failed to update article reliability",
                article_id=article_id,
                error=str(e)
            )

    def _send_verified_content(
        self,
        task_id: str,
        article_id: str,
        source_article: Dict[str, Any],
        verified_claims: List[Dict[str, Any]],
        api_calls_made: Dict[str, int] = None
    ) -> bool:
        """
        Lähetä todennettu sisältö Content Creation -agentille
        
        Args:
            task_id: Tehtävätunniste
            article_id: Artikkelin ID
            source_article: Lähdeartikkeli
            verified_claims: Todennetut väitteet
            api_calls_made: API-kutsujen määrät
        
        Returns:
            True jos onnistui
        """
        # Laske overall credibility
        if verified_claims:
            verified_count = sum(
                1 for c in verified_claims
                if c["verificationStatus"] == "VERIFIED"
            )
            ratio = verified_count / len(verified_claims)
            
            if ratio >= 0.8:
                overall_credibility = "HIGH"
            elif ratio >= 0.5:
                overall_credibility = "MEDIUM"
            elif ratio >= 0.2:
                overall_credibility = "LOW"
            else:
                overall_credibility = "MIXED"
        else:
            overall_credibility = "MEDIUM"
        
        # Luo payload
        payload = {
            "schemaVersion": "1.0",
            "taskId": task_id,
            "articleId": article_id,
            "verifiedArticle": {
                **source_article,
                "overallCredibility": overall_credibility,
                "verifiedClaimsCount": sum(
                    1 for c in verified_claims
                    if c["verificationStatus"] == "VERIFIED"
                ),
                "unverifiedClaimsCount": sum(
                    1 for c in verified_claims
                    if c["verificationStatus"] != "VERIFIED"
                )
            },
            "verifiedClaims": verified_claims,
            "metadata": {
                "factCheckTimestamp": datetime.now(timezone.utc).isoformat(),
                "factCheckAgentVersion": "1.0.0",
                "apiCallsMade": api_calls_made or {}
            }
        }
        
        # Lähetä Kafkaan
        success = self.kafka.produce(
            topic=self.settings.kafka.kafka_topic_creation_queue,
            payload=payload,
            key=task_id,
            schema_name="factcheck_to_creation",
            validate_schema=True
        )
        
        if success:
            self.log_agent_handoff(
                from_agent="fact_checking",
                to_agent="content_creation",
                task_id=task_id,
                payload_schema_version="1.0",
                article_id=article_id,
                verified_claims_count=len(verified_claims)
            )
        
        return success
    
    def _handle_shutdown(self, signum, frame):
        """Käsittele shutdown-signaali"""
        self.logger.info(f"Received shutdown signal: {signum}")
        self.shutdown_requested = True
    
    def shutdown(self):
        """Sulje agentti gracefully"""
        self.logger.info("Shutting down Fact-Checking agent...")
        
        self.kafka.close()
        self.redis.close()
        self.postgres.close()
        
        self.logger.info("Fact-Checking agent shut down successfully")


def main():
    """Pääfunktio"""
    print("=" * 60)
    print("Climate News Multi-Agent System")
    print("Fact-Checking Agent v1.0.0")
    print("=" * 60)
    print()
    
    agent = FactCheckingAgent()
    agent.start()


if __name__ == "__main__":
    main()


