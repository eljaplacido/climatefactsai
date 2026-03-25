"""
Workflow Orchestrator

Hallinnoi päivittäisen työnkulun vaiheiden koordinointia.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone

from structlog.stdlib import BoundLogger

from agents.shared.kafka_client import KafkaClient
from agents.orchestrator.state_machine import StateMachine, WorkflowStatus, StageStatus


class WorkflowOrchestrator:
    """
    Työnkulun koordinaattori
    
    Vastaa:
    1. Työnkulun käynnistämisestä
    2. Vaiheiden delegoimisesta worker-agenteille
    3. Edistymisen seuraamisesta
    4. Virhetilanteiden hallinnasta
    """
    
    def __init__(
        self,
        kafka_client: KafkaClient,
        state_machine: StateMachine,
        logger: BoundLogger
    ):
        """
        Alusta workflow orchestrator
        
        Args:
            kafka_client: Kafka-asiakas viestintään
            state_machine: State machine tilan hallintaan
            logger: Logger
        """
        self.kafka = kafka_client
        self.state_machine = state_machine
        self.logger = logger
    
    def start_daily_workflow(
        self,
        task_id: str,
        location_override: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Käynnistä päivittäinen työnkulku
        
        Args:
            task_id: Tehtävätunniste
            location_override: Valinnainen kohdepaikan override
        
        Returns:
            True jos käynnistys onnistui
        """
        self.logger.info(
            "Starting daily workflow",
            task_id=task_id
        )
        
        # Luo tehtävä state machineen
        task_state = self.state_machine.create_task(
            task_id=task_id,
            workflow_type="DAILY_WORKFLOW",
            metadata={
                "startedAt": datetime.now(timezone.utc).isoformat(),
                "locationOverride": location_override
            }
        )
        
        # Siirry DISCOVERY-tilaan
        if not self.state_machine.transition_to(task_id, WorkflowStatus.DISCOVERY):
            self.logger.error("Failed to transition to DISCOVERY", task_id=task_id)
            return False
        
        # Delegoi Content Discovery -vaihe
        return self._delegate_discovery(task_id)
    
    def _delegate_discovery(self, task_id: str) -> bool:
        """
        Delegoi Content Discovery -vaihe
        
        Args:
            task_id: Tehtävätunniste
        
        Returns:
            True jos delegointi onnistui
        """
        self.logger.info(
            "Delegating to Content Discovery agent",
            task_id=task_id
        )
        
        # Päivitä vaiheen tila
        self.state_machine.update_stage(
            task_id=task_id,
            stage_name="discovery",
            stage_status=StageStatus.IN_PROGRESS
        )
        
        # Luo discovery-käsky
        discovery_task = {
            "command": "discover_content",
            "taskId": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "parameters": {
                "targetLocation": self._get_target_location(task_id),
                "dateRange": {
                    "from": self._get_yesterday_iso(),
                    "to": self._get_today_iso()
                }
            }
        }
        
        # Lähetä Kafkaan
        success = self.kafka.produce(
            topic=self.kafka.settings.kafka_topic_discovery_queue,
            payload=discovery_task,
            key=task_id
        )
        
        if success:
            self.logger.info(
                "Discovery task sent",
                task_id=task_id
            )
        else:
            self.logger.error(
                "Failed to send discovery task",
                task_id=task_id
            )
            self.state_machine.transition_to(task_id, WorkflowStatus.FAILED)
        
        return success
    
    def _delegate_fact_checking(self, task_id: str) -> bool:
        """Delegoi Fact-Checking -vaihe (kutsutaan discovery-vaiheen päätyttyä)"""
        self.logger.info("Delegating to Fact-Checking agent", task_id=task_id)
        
        self.state_machine.transition_to(task_id, WorkflowStatus.FACT_CHECKING)
        self.state_machine.update_stage(
            task_id=task_id,
            stage_name="factChecking",
            stage_status=StageStatus.IN_PROGRESS
        )
        
        # Fact-checking tapahtuu automaattisesti kun Content Discovery
        # julkaisee artikkeleita fact_checking_queue:iin
        return True
    
    def _delegate_content_creation(self, task_id: str) -> bool:
        """Delegoi Content Creation -vaihe"""
        self.logger.info("Delegating to Content Creation agent", task_id=task_id)
        
        self.state_machine.transition_to(task_id, WorkflowStatus.CONTENT_CREATION)
        self.state_machine.update_stage(
            task_id=task_id,
            stage_name="contentCreation",
            stage_status=StageStatus.IN_PROGRESS
        )
        
        # Lähetä content creation -käsky
        creation_task = {
            "command": "create_summary",
            "taskId": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return self.kafka.produce(
            topic=self.kafka.settings.kafka_topic_creation_queue,
            payload=creation_task,
            key=task_id
        )
    
    def _delegate_video_production(self, task_id: str, summary_text: str) -> bool:
        """Delegoi Video Production -vaihe"""
        self.logger.info("Delegating to Video Production agent", task_id=task_id)
        
        self.state_machine.transition_to(task_id, WorkflowStatus.VIDEO_PRODUCTION)
        self.state_machine.update_stage(
            task_id=task_id,
            stage_name="videoProduction",
            stage_status=StageStatus.IN_PROGRESS
        )
        
        video_task = {
            "command": "produce_video",
            "taskId": task_id,
            "summaryText": summary_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "parameters": {
                "aspectRatio": "9:16",
                "maxDurationSeconds": 90,
                "style": "professional_news"
            }
        }
        
        return self.kafka.produce(
            topic=self.kafka.settings.kafka_topic_video_queue,
            payload=video_task,
            key=task_id
        )
    
    def _trigger_hitl_review(self, task_id: str) -> bool:
        """Käynnistä Human-in-the-Loop -tarkistus"""
        self.logger.info("Triggering HITL review", task_id=task_id)
        
        self.state_machine.transition_to(task_id, WorkflowStatus.HITL_REVIEW)
        self.state_machine.update_stage(
            task_id=task_id,
            stage_name="hitlReview",
            stage_status=StageStatus.IN_PROGRESS
        )
        
        # Lähetä notifikaatio tarkistajalle (esim. Slack webhook)
        # Tämä toteutetaan myöhemmin
        self.logger.info(
            "HITL notification sent",
            task_id=task_id,
            review_url=f"http://review.climatenews.com/task/{task_id}"
        )
        
        return True
    
    def _publish_content(self, task_id: str) -> bool:
        """Julkaise hyväksytty sisältö"""
        self.logger.info("Publishing content", task_id=task_id)
        
        self.state_machine.transition_to(task_id, WorkflowStatus.PUBLISHED)
        self.state_machine.update_stage(
            task_id=task_id,
            stage_name="publication",
            stage_status=StageStatus.COMPLETED
        )
        
        # Lähetä publication queue:iin
        publish_task = {
            "command": "publish",
            "taskId": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return self.kafka.produce(
            topic=self.kafka.settings.kafka_topic_publication_queue,
            payload=publish_task,
            key=task_id
        )
    
    def _get_target_location(self, task_id: str) -> Dict[str, Any]:
        """Hae kohdepaikan tiedot tehtävälle"""
        from agents.shared.config import get_settings
        settings = get_settings()
        
        return {
            "name": settings.location.target_location_name,
            "latitude": settings.location.target_location_latitude,
            "longitude": settings.location.target_location_longitude,
            "country": settings.location.target_location_country
        }
    
    def _get_yesterday_iso(self) -> str:
        """Palauta eilisen päivämäärä ISO-formaatissa"""
        from datetime import timedelta
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d")
    
    def _get_today_iso(self) -> str:
        """Palauta tämän päivän päivämäärä ISO-formaatissa"""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    def handle_stage_completion(
        self,
        task_id: str,
        completed_stage: str,
        result_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Käsittele vaiheen valmistuminen ja siirry seuraavaan vaiheeseen
        
        Args:
            task_id: Tehtävätunniste
            completed_stage: Valmistunut vaihe
            result_data: Vaiheen tulosdata
        
        Returns:
            True jos seuraava vaihe käynnistyi onnistuneesti
        """
        self.logger.info(
            "Stage completed",
            task_id=task_id,
            stage=completed_stage
        )
        
        # Päivitä vaiheen tila
        self.state_machine.update_stage(
            task_id=task_id,
            stage_name=completed_stage,
            stage_status=StageStatus.COMPLETED,
            stage_data=result_data
        )
        
        # Määritä seuraava vaihe
        next_stage_map = {
            "discovery": self._delegate_fact_checking,
            "factChecking": self._delegate_content_creation,
            "contentCreation": lambda tid: self._delegate_video_production(
                tid,
                result_data.get("summaryText", "") if result_data else ""
            ),
            "videoProduction": self._trigger_hitl_review,
        }
        
        # Käynnistä seuraava vaihe
        if completed_stage in next_stage_map:
            return next_stage_map[completed_stage](task_id)
        
        return True
    
    def handle_stage_failure(
        self,
        task_id: str,
        failed_stage: str,
        error: str
    ) -> bool:
        """
        Käsittele vaiheen epäonnistuminen
        
        Args:
            task_id: Tehtävätunniste
            failed_stage: Epäonnistunut vaihe
            error: Virheilmoitus
        
        Returns:
            True jos uudelleenyritys käynnistyy
        """
        self.logger.error(
            "Stage failed",
            task_id=task_id,
            stage=failed_stage,
            error=error
        )
        
        # Päivitä vaiheen tila
        self.state_machine.update_stage(
            task_id=task_id,
            stage_name=failed_stage,
            stage_status=StageStatus.FAILED,
            stage_data={"error": error}
        )
        
        # Tarkista uudelleenyritysraja
        attempt_count = self.state_machine.increment_retry(task_id)
        
        if self.state_machine.has_exceeded_retries(task_id):
            self.logger.error(
                "Max retries exceeded, marking workflow as FAILED",
                task_id=task_id,
                attempt_count=attempt_count
            )
            self.state_machine.transition_to(task_id, WorkflowStatus.FAILED)
            return False
        
        # Yritä uudelleen
        self.logger.info(
            "Retrying stage",
            task_id=task_id,
            stage=failed_stage,
            attempt=attempt_count
        )

        # Implementoi retry-logiikka
        # Resetoi vaiheen tila ja käynnistä uudelleen
        self.state_machine.update_stage(
            task_id=task_id,
            stage_name=failed_stage,
            stage_status=StageStatus.PENDING,
            stage_data={"retryAttempt": attempt_count}
        )

        # Delegoi vaihe uudelleen sen nimen perusteella
        retry_success = False

        if failed_stage == "discovery":
            retry_success = self._delegate_discovery(task_id)
        elif failed_stage == "factChecking":
            retry_success = self._delegate_fact_checking(task_id)
        elif failed_stage == "contentCreation":
            retry_success = self._delegate_content_creation(task_id)
        elif failed_stage == "videoProduction":
            # Get task state to retrieve summary text if available
            task_state = self.state_machine.get_task_state(task_id)
            summary_text = task_state.get("metadata", {}).get("summaryText", "")
            retry_success = self._delegate_video_production(task_id, summary_text)
        elif failed_stage == "hitlReview":
            retry_success = self._trigger_hitl_review(task_id)
        elif failed_stage == "publishing":
            retry_success = self._publish_content(task_id)
        else:
            self.logger.error(
                "Unknown stage for retry",
                task_id=task_id,
                stage=failed_stage
            )
            return False

        if retry_success:
            self.logger.info(
                "Stage retry initiated successfully",
                task_id=task_id,
                stage=failed_stage,
                attempt=attempt_count
            )
        else:
            self.logger.error(
                "Stage retry failed to initiate",
                task_id=task_id,
                stage=failed_stage,
                attempt=attempt_count
            )

        return retry_success

