"""
Workflow State Machine

Hallinnoi työnkulun tilasiirtymiä ja varmistaa oikean järjestyksen.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from structlog.stdlib import BoundLogger


class WorkflowStatus(str, Enum):
    """Työnkulun mahdolliset tilat"""
    INITIATED = "INITIATED"
    DISCOVERY = "DISCOVERY"
    FACT_CHECKING = "FACT_CHECKING"
    CONTENT_CREATION = "CONTENT_CREATION"
    VIDEO_PRODUCTION = "VIDEO_PRODUCTION"
    HITL_REVIEW = "HITL_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StageStatus(str, Enum):
    """Yksittäisen vaiheen mahdolliset tilat"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StateMachine:
    """
    State machine työnkulun hallintaan
    
    Varmistaa että:
    1. Vaiheet suoritetaan oikeassa järjestyksessä
    2. Virhetilanteissa voidaan palauttaa tila
    3. Edistymistä voidaan seurata
    """
    
    # Sallitut tilasiirtymät
    ALLOWED_TRANSITIONS: Dict[WorkflowStatus, List[WorkflowStatus]] = {
        WorkflowStatus.INITIATED: [WorkflowStatus.DISCOVERY, WorkflowStatus.FAILED],
        WorkflowStatus.DISCOVERY: [WorkflowStatus.FACT_CHECKING, WorkflowStatus.FAILED],
        WorkflowStatus.FACT_CHECKING: [WorkflowStatus.CONTENT_CREATION, WorkflowStatus.FAILED],
        WorkflowStatus.CONTENT_CREATION: [WorkflowStatus.VIDEO_PRODUCTION, WorkflowStatus.HITL_REVIEW, WorkflowStatus.FAILED],
        WorkflowStatus.VIDEO_PRODUCTION: [WorkflowStatus.HITL_REVIEW, WorkflowStatus.FAILED],
        WorkflowStatus.HITL_REVIEW: [WorkflowStatus.APPROVED, WorkflowStatus.CONTENT_CREATION, WorkflowStatus.FAILED],
        WorkflowStatus.APPROVED: [WorkflowStatus.PUBLISHED, WorkflowStatus.FAILED],
        WorkflowStatus.PUBLISHED: [],  # Loppupiste
        WorkflowStatus.FAILED: [WorkflowStatus.INITIATED],  # Voidaan aloittaa alusta
        WorkflowStatus.CANCELLED: [],  # Loppupiste
    }
    
    def __init__(self, redis_client, logger: BoundLogger):
        """
        Alusta state machine
        
        Args:
            redis_client: Redis-asiakas tilan tallennukseen
            logger: Logger
        """
        self.redis = redis_client
        self.logger = logger
    
    def create_task(
        self,
        task_id: str,
        workflow_type: str = "DAILY_WORKFLOW",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Luo uusi tehtävä
        
        Args:
            task_id: Tehtävätunniste
            workflow_type: Työnkulun tyyppi
            metadata: Lisämetadata
        
        Returns:
            Tehtävän tila-dictionary
        """
        now = datetime.now(timezone.utc).isoformat()
        
        task_state = {
            "taskId": task_id,
            "workflowType": workflow_type,
            "status": WorkflowStatus.INITIATED.value,
            "createdAt": now,
            "updatedAt": now,
            "stages": {
                "discovery": {"status": StageStatus.PENDING.value},
                "factChecking": {"status": StageStatus.PENDING.value},
                "contentCreation": {"status": StageStatus.PENDING.value},
                "videoProduction": {"status": StageStatus.PENDING.value},
                "hitlReview": {"status": StageStatus.PENDING.value},
                "publication": {"status": StageStatus.PENDING.value},
            },
            "costTracking": {
                "totalCostUsd": 0.0,
                "llmCosts": {"claude": {}, "gpt4o": {}},
                "apiCosts": {},
            },
            "retry": {
                "attemptCount": 0,
                "maxAttempts": 3,
            },
            "metadata": metadata or {}
        }
        
        # Tallenna Redisiin
        self.redis.set_task_state(task_id, task_state)
        
        self.logger.info(
            "Task created",
            task_id=task_id,
            workflow_type=workflow_type
        )
        
        return task_state
    
    def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Hae tehtävän tila"""
        return self.redis.get_task_state(task_id)
    
    def transition_to(
        self,
        task_id: str,
        new_status: WorkflowStatus
    ) -> bool:
        """
        Siirry uuteen tilaan
        
        Args:
            task_id: Tehtävätunniste
            new_status: Uusi tila
        
        Returns:
            True jos siirtymä onnistui
        """
        task_state = self.get_task_state(task_id)
        if not task_state:
            self.logger.error("Task not found", task_id=task_id)
            return False
        
        current_status = WorkflowStatus(task_state["status"])
        
        # Tarkista että siirtymä on sallittu
        if new_status not in self.ALLOWED_TRANSITIONS[current_status]:
            self.logger.error(
                "Invalid state transition",
                task_id=task_id,
                current_status=current_status.value,
                attempted_status=new_status.value,
                allowed=[ s.value for s in self.ALLOWED_TRANSITIONS[current_status]]
            )
            return False
        
        # Suorita siirtymä
        task_state["status"] = new_status.value
        task_state["updatedAt"] = datetime.now(timezone.utc).isoformat()
        
        self.redis.set_task_state(task_id, task_state)
        
        self.logger.info(
            "State transition",
            task_id=task_id,
            from_status=current_status.value,
            to_status=new_status.value
        )
        
        return True
    
    def update_stage(
        self,
        task_id: str,
        stage_name: str,
        stage_status: StageStatus,
        stage_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Päivitä vaiheen tila
        
        Args:
            task_id: Tehtävätunniste
            stage_name: Vaiheen nimi (esim. "discovery")
            stage_status: Vaiheen uusi tila
            stage_data: Lisätietoja vaiheesta
        
        Returns:
            True jos päivitys onnistui
        """
        task_state = self.get_task_state(task_id)
        if not task_state:
            return False
        
        if stage_name not in task_state["stages"]:
            self.logger.error(f"Unknown stage: {stage_name}", task_id=task_id)
            return False
        
        # Päivitä vaiheen tila
        stage = task_state["stages"][stage_name]
        stage["status"] = stage_status.value
        
        if stage_status == StageStatus.IN_PROGRESS and "startedAt" not in stage:
            stage["startedAt"] = datetime.now(timezone.utc).isoformat()
        
        if stage_status in [StageStatus.COMPLETED, StageStatus.FAILED]:
            stage["completedAt"] = datetime.now(timezone.utc).isoformat()
        
        # Lisää stage-spesifistä dataa
        if stage_data:
            stage.update(stage_data)
        
        task_state["updatedAt"] = datetime.now(timezone.utc).isoformat()
        
        self.redis.set_task_state(task_id, task_state)
        
        self.logger.info(
            "Stage updated",
            task_id=task_id,
            stage=stage_name,
            status=stage_status.value
        )
        
        return True
    
    def add_cost(
        self,
        task_id: str,
        cost_type: str,
        cost_usd: float,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Lisää kustannus tehtävään
        
        Args:
            task_id: Tehtävätunniste
            cost_type: Kustannustyyppi (esim. "claude", "climateCheck")
            cost_usd: Kustannus USD:na
            details: Lisätietoja (esim. token-määrät)
        """
        task_state = self.get_task_state(task_id)
        if not task_state:
            return
        
        # Päivitä kokonaiskustannus
        task_state["costTracking"]["totalCostUsd"] += cost_usd
        
        # Lisää tarkemmat tiedot
        if details:
            if cost_type in ["claude", "gpt4o"]:
                task_state["costTracking"]["llmCosts"][cost_type] = details
            else:
                task_state["costTracking"]["apiCosts"][cost_type] = cost_usd
        
        self.redis.set_task_state(task_id, task_state)
        
        self.logger.debug(
            "Cost added",
            task_id=task_id,
            cost_type=cost_type,
            cost_usd=cost_usd
        )
    
    def increment_retry(self, task_id: str) -> int:
        """
        Kasvata uudelleenyritys-laskuria
        
        Returns:
            Nykyinen yrityskertojen määrä
        """
        task_state = self.get_task_state(task_id)
        if not task_state:
            return 0
        
        task_state["retry"]["attemptCount"] += 1
        attempt_count = task_state["retry"]["attemptCount"]
        
        self.redis.set_task_state(task_id, task_state)
        
        return attempt_count
    
    def has_exceeded_retries(self, task_id: str) -> bool:
        """Tarkista onko uudelleenyritysten raja ylitetty"""
        task_state = self.get_task_state(task_id)
        if not task_state:
            return True
        
        retry = task_state["retry"]
        return retry["attemptCount"] >= retry["maxAttempts"]

