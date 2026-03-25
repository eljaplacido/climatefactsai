"""
Keskitetty strukturoitu logging kaikille agenteille

Käyttää structlog-kirjastoa JSON-muotoiseen loggaukseen OpenTelemetry-integraatiolla.
"""

import logging
import sys
from typing import Any, Dict, Optional
from datetime import datetime

import structlog
from structlog.stdlib import BoundLogger
from pythonjsonlogger import jsonlogger

from .config import get_settings


def setup_logging(
    agent_name: str,
    log_level: Optional[str] = None,
    log_format: Optional[str] = None
) -> BoundLogger:
    """
    Alusta strukturoitu logging agentille
    
    Args:
        agent_name: Agentin nimi (esim. "orchestrator", "content_discovery")
        log_level: Loggaustaso (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Loggausformaatti ("json" tai "text")
    
    Returns:
        Konfiguroitu structlog logger
    """
    settings = get_settings()
    
    # Käytä konfiguraatiosta tai parametreista
    log_level = log_level or settings.observability.log_level
    log_format = log_format or settings.observability.log_format
    
    # Aseta Python-loggaustaso
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper())
    )
    
    # Structlog-prosessorit
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Lisää agent_name ja environment jokaiseen lokimerkintään
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Valitse formaatti
    if log_format == "json":
        formatter = jsonlogger.JsonFormatter(
            fmt="%(timestamp)s %(level)s %(name)s %(message)s"
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    # Aseta formatter root loggerille
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logging.root.handlers = [handler]
    
    # Luo ja palauta logger agentti-spesifisillä konteksteilla
    logger = structlog.get_logger(agent_name)
    logger = logger.bind(
        agent_name=agent_name,
        environment=settings.environment,
        service_name=settings.observability.otel_service_name
    )
    
    return logger


def bind_task_context(logger: BoundLogger, task_id: str, **kwargs) -> BoundLogger:
    """
    Liitä task-spesifinen konteksti loggeriin
    
    Args:
        logger: Strukturoitu logger
        task_id: Tehtävätunniste
        **kwargs: Lisäkontekstimuuttujat
    
    Returns:
        Logger task-kontekstilla
    """
    return logger.bind(task_id=task_id, **kwargs)


class LoggerMixin:
    """
    Mixin-luokka, joka lisää logger-attribuutin luokkaan
    
    Käyttö:
        class MyAgent(LoggerMixin):
            def __init__(self):
                self.setup_logger("my_agent")
                
            def process(self):
                self.logger.info("Processing task", task_id="123")
    """
    
    logger: BoundLogger
    
    def setup_logger(self, agent_name: str, **bind_kwargs):
        """Alusta logger tälle agentille"""
        self.logger = setup_logging(agent_name)
        if bind_kwargs:
            self.logger = self.logger.bind(**bind_kwargs)
    
    def log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """
        Loggaa virhe strukturoidusti
        
        Args:
            error: Poikkeus
            context: Lisäkonteksti virheen ympärillä
        """
        error_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_traceback": True  # structlog lisää automaattisesti traceback:in
        }
        
        if context:
            error_data.update(context)
        
        self.logger.error("Error occurred", **error_data, exc_info=True)
    
    def log_api_call(
        self,
        api_name: str,
        endpoint: str,
        method: str = "GET",
        status_code: Optional[int] = None,
        duration_ms: Optional[float] = None,
        **kwargs
    ):
        """
        Loggaa ulkoinen API-kutsu
        
        Args:
            api_name: API:n nimi (esim. "ClimateCheck", "OpenAI")
            endpoint: API-endpoint
            method: HTTP-metodi
            status_code: Vastauksen HTTP-statuskoodi
            duration_ms: Kutsun kesto millisekunneissa
            **kwargs: Lisätietoja
        """
        self.logger.info(
            "API call",
            api_name=api_name,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            **kwargs
        )
    
    def log_agent_handoff(
        self,
        from_agent: str,
        to_agent: str,
        task_id: str,
        payload_schema_version: str,
        **kwargs
    ):
        """
        Loggaa agentin välinen tiedonsiirto
        
        Args:
            from_agent: Lähettäjäagentti
            to_agent: Vastaanottaja-agentti
            task_id: Tehtävätunniste
            payload_schema_version: Käytetty skeemaversio
            **kwargs: Lisätietoja payload:sta
        """
        self.logger.info(
            "Agent handoff",
            from_agent=from_agent,
            to_agent=to_agent,
            task_id=task_id,
            schema_version=payload_schema_version,
            **kwargs
        )
    
    def log_llm_interaction(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_cost_usd: float,
        duration_ms: float,
        **kwargs
    ):
        """
        Loggaa LLM-interaktio kustannuksineen
        
        Args:
            model: LLM-malli (esim. "claude-3-5-sonnet")
            prompt_tokens: Promptin tokenien määrä
            completion_tokens: Vastauksen tokenien määrä
            total_cost_usd: Kokonaiskustannus USD:na
            duration_ms: Kutsun kesto millisekunneissa
            **kwargs: Lisätietoja
        """
        self.logger.info(
            "LLM interaction",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            total_cost_usd=round(total_cost_usd, 6),
            duration_ms=duration_ms,
            **kwargs
        )


# Globaali logger sovellustason tapahtumille
app_logger = setup_logging("app")


if __name__ == "__main__":
    # Testaa logging
    test_logger = setup_logging("test_agent")
    
    test_logger.info("Test info message", key="value")
    test_logger.warning("Test warning", metric=123)
    
    try:
        raise ValueError("Test error")
    except Exception as e:
        test_logger.error("Caught exception", exc_info=True)

