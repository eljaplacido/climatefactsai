"""
Orchestrator Agent - Pääohjelma

Orchestrator-agentti toimii työnkulun pääkoordinaattorina. Se:
1. Vastaanottaa käynnistyskäskyn (ajastettu tai manuaalinen)
2. Luo uuden tehtävän (task) ja seuraa sen tilaa
3. Delegoi työvaiheet työntekijä-agenteille Kafkan kautta
4. Monitoroi vaiheiden edistymistä
5. Käsittelee virheitä ja uudelleenyrityksiä
6. Käynnistää HITL-tarkistuksen
7. Julkaisee lopullisen sisällön
"""

import asyncio
import signal
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path

# Lisää parent-hakemisto PYTHONPATH:iin
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import get_settings
from shared.logger import setup_logging
from shared.kafka_client import KafkaClient
from shared.database import get_redis, get_postgres
from orchestrator.workflow import WorkflowOrchestrator
from orchestrator.state_machine import StateMachine


class OrchestratorAgent:
    """
    Pää-orchestrator-agentti
    
    Toimii event-driven -arkkitehtuurilla:
    - Kuuntelee aloituskäskyä Kafkasta
    - Hallinnoi workflow-instansseja
    - Seuraa agenteilta tulevia tapahtumia
    """
    
    def __init__(self):
        """Alusta Orchestrator"""
        self.settings = get_settings()
        self.logger = setup_logging("orchestrator")
        
        # Kafka-asiakas
        self.kafka = KafkaClient(agent_name="orchestrator")
        
        # Tietokannat
        self.redis = get_redis()
        self.postgres = get_postgres()
        
        # State machine ja workflow orchestrator
        self.state_machine = StateMachine(self.redis, self.logger)
        self.workflow = WorkflowOrchestrator(
            kafka_client=self.kafka,
            state_machine=self.state_machine,
            logger=self.logger
        )
        
        # Seuraa aktiivisia työnkulkuja
        self.active_workflows: Dict[str, Any] = {}
        
        # Shutdown flag
        self.shutdown_requested = False
        
        self.logger.info(
            "Orchestrator agent initialized",
            version="1.0.0",
            environment=self.settings.environment
        )
    
    def start(self):
        """Käynnistä Orchestrator-agentti"""
        self.logger.info("Starting Orchestrator agent...")
        
        # Rekisteröi shutdown-handlerit
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
        # Käynnistä event-kuuntelijat eri säikeissä/prosesseissa
        # Tässä yksinkertaistettu versio - tuotannossa käytettäisiin async/await
        
        try:
            # Kuuntele "start workflow" -käskyjä
            self.logger.info("Listening for workflow start commands...")
            self._listen_for_start_commands()
            
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            self.shutdown()
    
    def _listen_for_start_commands(self):
        """
        Kuuntele työnkulun aloituskäskyjä
        
        Tämä on blocking-funktio, joka kuuntelee Kafka-aihetta.
        Tuotannossa tämä olisi async tai erillisessä säikeessä.
        """
        # Kuuntele "orchestrator_commands" -aihetta
        self.kafka.consume(
            topic="orchestrator_commands",
            message_handler=self._handle_start_command,
            group_id="orchestrator_group",
            auto_commit=False
        )
    
    def _handle_start_command(self, message: Dict[str, Any]) -> bool:
        """
        Käsittele työnkulun aloituskäsky
        
        Args:
            message: Kafka-viesti
        
        Returns:
            True jos onnistui
        """
        command = message.get("command")
        
        if command == "start_daily_workflow":
            self.logger.info("Received daily workflow start command")
            
            # Luo uusi tehtävä
            task_id = self._generate_task_id()
            
            # Käynnistä workflow
            try:
                self.workflow.start_daily_workflow(task_id)
                
                self.logger.info(
                    "Daily workflow started successfully",
                    task_id=task_id
                )
                return True
                
            except Exception as e:
                self.logger.error(
                    "Failed to start daily workflow",
                    task_id=task_id,
                    error=str(e),
                    exc_info=True
                )
                return False
        
        elif command == "manual_trigger":
            # Manuaalinen käynnistys (testaus, hätäpäivitys)
            self.logger.info("Received manual workflow trigger")
            task_id = message.get("taskId") or self._generate_task_id()
            
            try:
                self.workflow.start_daily_workflow(task_id)
                return True
            except Exception as e:
                self.logger.error(f"Manual trigger failed: {e}", exc_info=True)
                return False
        
        else:
            self.logger.warning(f"Unknown command: {command}")
            return False
    
    def _generate_task_id(self) -> str:
        """
        Generoi uniikki tehtävätunniste
        
        Formaatti: task-YYYYMMDD-NNN
        Esim: task-20251010-001
        """
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        
        # Hae tänään luotujen tehtävien määrä Redisistä
        count_key = f"task_count:{today}"
        count = self.redis.increment(count_key, 1)
        
        # Aseta TTL laskurille (48h)
        self.redis.set_with_expiry(count_key, count, expire_seconds=172800)
        
        task_id = f"task-{today}-{count:03d}"
        return task_id
    
    def _handle_shutdown(self, signum, frame):
        """Käsittele shutdown-signaali"""
        self.logger.info(f"Received shutdown signal: {signum}")
        self.shutdown_requested = True
    
    def shutdown(self):
        """Sulje Orchestrator gracefully"""
        self.logger.info("Shutting down Orchestrator agent...")
        
        # Sulje Kafka-yhteydet
        self.kafka.close()
        
        # Sulje tietokantayhteydet
        self.redis.close()
        self.postgres.close()
        
        self.logger.info("Orchestrator agent shut down successfully")


def main():
    """Pääfunktio"""
    print("=" * 60)
    print("Climate News Multi-Agent System")
    print("Orchestrator Agent v1.0.0")
    print("=" * 60)
    print()
    
    # Luo ja käynnistä agentti
    agent = OrchestratorAgent()
    agent.start()


if __name__ == "__main__":
    main()

