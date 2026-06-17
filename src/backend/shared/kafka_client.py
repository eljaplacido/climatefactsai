"""Event-driven messaging for multi-agent coordination via Apache Kafka.

This module provides high-level abstractions for producer/consumer operations
with automatic JSON schema validation, reliable message delivery, and structured
logging. All microservices use KafkaClient for asynchronous agent communication.

Architecture:
    - KafkaClient: Main client for produce/consume operations with schema validation
    - KafkaProducerClient: Legacy wrapper for backward compatibility (API layer)
    - JSON Schema validation for message contracts between agents
    - At-least-once delivery with manual offset commits

Event Flow:
    **Producer (Agent A) → Kafka → Consumer (Agent B):**

    1. Agent A calls produce() with payload dict
    2. Payload validated against JSON schema (optional)
    3. Message serialized to JSON and sent to Kafka topic
    4. Agent B's consume() polls for messages
    5. Message deserialized and validated
    6. Handler callback processes message
    7. Offset committed on success (manual commit for reliability)

Topics (Kafka Event Bus):
    - `discovery_queue` - Ingestion agent output
    - `fact_checking_queue` - Verification agent input
    - `content_creation_queue` - Content agent input
    - `video_queue` - Video agent input
    - `publication_queue` - Final publication events
    - `orchestrator_commands` - Orchestrator commands to agents
    - `orchestrator_responses` - Agent responses to orchestrator
    - `workflow_events` - State change notifications

Usage:
    >>> from shared.kafka_client import KafkaClient
    >>>
    >>> # Producer example
    >>> producer = KafkaClient(agent_name="ingestion_agent")
    >>> producer.produce(
    ...     topic="fact_checking_queue",
    ...     payload={"taskId": "task-123", "articles": [...]},
    ...     schema_name="fact_checking_input"
    ... )
    >>>
    >>> # Consumer example
    >>> def handle_message(payload: dict) -> bool:
    ...     print(f"Processing task {payload['taskId']}")
    ...     # ... process message ...
    ...     return True  # Commit offset
    >>>
    >>> consumer = KafkaClient(agent_name="fact_checking_agent")
    >>> consumer.consume("fact_checking_queue", handle_message)

Example:
    Complete producer-consumer flow between agents:

    ```python
    # Ingestion Agent (Producer)
    class IngestionAgent:
        def __init__(self):
            self.kafka = KafkaClient(agent_name="ingestion")

        def publish_articles(self, task_id: str, articles: List[Dict]):
            self.kafka.produce(
                topic="fact_checking_queue",
                payload={
                    "schemaVersion": "1.0",
                    "taskId": task_id,
                    "articles": articles,
                    "timestamp": datetime.utcnow().isoformat()
                },
                schema_name="fact_checking_input",
                validate_schema=True
            )

    # Verification Agent (Consumer)
    class VerificationAgent:
        def __init__(self):
            self.kafka = KafkaClient(agent_name="verification")

        def start(self):
            self.kafka.consume(
                topic="fact_checking_queue",
                message_handler=self.process_articles,
                schema_name="fact_checking_input"
            )

        def process_articles(self, payload: dict) -> bool:
            try:
                task_id = payload["taskId"]
                articles = payload["articles"]
                # ... verify claims ...
                return True  # Success: commit offset
            except Exception as e:
                logger.error(f"Processing failed: {e}")
                return False  # Retry: don't commit
    ```

JSON Schema Validation:
    Schemas defined in /schemas/*.json enforce message contracts:

    ```json
    {
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "schemaVersion": {"type": "string"},
        "taskId": {"type": "string"},
        "articles": {"type": "array"}
      },
      "required": ["schemaVersion", "taskId", "articles"]
    }
    ```

Performance:
    - Producer: Synchronous with acks=all (reliability over throughput)
    - Consumer: Batch processing (max 10 messages per poll)
    - Manual offset commits for at-least-once delivery guarantee
    - Automatic retry with exponential backoff on transient failures

Note:
    Consumer operations are blocking (infinite loop). Run in dedicated threads
    or async tasks. Use KeyboardInterrupt to gracefully shut down consumers.
"""

import json
import time
from typing import Any, Callable, Dict, Optional
from pathlib import Path

from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
from jsonschema import validate, ValidationError

from .config import get_kafka_settings
from .logger import LoggerMixin


class KafkaClient(LoggerMixin):
    """Kafka client for event-driven agent communication with schema validation.

    This client handles both producer and consumer operations for inter-agent
    messaging. Supports JSON schema validation, reliable delivery with manual
    offset commits, and structured logging for observability.

    Features:
        - Lazy initialization of producer/consumer (created on first use)
        - JSON schema validation from /schemas/*.json files
        - At-least-once delivery with manual offset commits
        - Automatic retry with exponential backoff
        - Partition-aware message keys for ordering
        - Structured logging with agent name, task ID, topic, partition, offset

    Attributes:
        agent_name (str): Name of the agent (used in consumer group and logs)
        settings (KafkaSettings): Configuration from environment
        schemas (Dict[str, Dict]): Loaded JSON schemas for validation
        bootstrap_servers (List[str]): Kafka broker addresses

    Usage (Producer):
        >>> client = KafkaClient(agent_name="ingestion_agent")
        >>> client.produce(
        ...     topic="fact_checking_queue",
        ...     payload={"taskId": "task-123", "articles": [...]},
        ...     schema_name="fact_checking_input"
        ... )

    Usage (Consumer):
        >>> def process_message(payload: dict) -> bool:
        ...     print(f"Task {payload['taskId']}")
        ...     return True  # Commit offset
        >>>
        >>> client = KafkaClient(agent_name="fact_checking_agent")
        >>> client.consume(
        ...     topic="fact_checking_queue",
        ...     message_handler=process_message,
        ...     schema_name="fact_checking_input"
        ... )

    Example:
        Orchestrator coordinating workflow:

        ```python
        class OrchestratorAgent:
            def __init__(self):
                self.kafka = KafkaClient(agent_name="orchestrator")
                self.redis = get_redis()

            def start_workflow(self, task_id: str):
                # Send command to ingestion agent
                self.kafka.produce(
                    topic="orchestrator_commands",
                    payload={
                        "command": "discover_articles",
                        "taskId": task_id,
                        "params": {"country": "FI", "max_articles": 10}
                    }
                )

                # Listen for responses
                def handle_response(payload: dict) -> bool:
                    self.redis.update_task_state(
                        payload["taskId"],
                        {"status": payload["status"]}
                    )
                    return True

                self.kafka.consume("orchestrator_responses", handle_response)
        ```

    Note:
        Producer created lazily on first produce(). Consumer blocks forever
        until KeyboardInterrupt. Schema validation optional but recommended.
    """
    
    def __init__(
        self,
        agent_name: str,
        schema_dir: Optional[Path] = None
    ):
        """Initialize Kafka client with schema loading and connection setup.

        Creates Kafka client for event-driven agent communication with automatic
        JSON schema validation. Loads all schemas from schema_dir on initialization.

        Args:
            agent_name: Agent name (used in consumer group IDs and logging)
            schema_dir: Directory containing JSON schema files (default: /schemas)

        Example:
            >>> client = KafkaClient(agent_name="ingestion_agent")
            >>> # Client ready for produce/consume operations
        """
        self.setup_logger(f"kafka.{agent_name}")
        self.agent_name = agent_name
        self.settings = get_kafka_settings()
        
        # Schema-hakemisto
        if schema_dir is None:
            schema_dir = Path(__file__).parent.parent.parent / "schemas"
        self.schema_dir = schema_dir
        
        # Lataa skeemat
        self.schemas: Dict[str, Dict] = {}
        self._load_schemas()
        
        # Kafka-yhteysasetukset
        self.bootstrap_servers = self.settings.kafka_bootstrap_servers.split(",")
        
        # Tuottaja ja kuluttaja alustetaan tarvittaessa
        self._producer: Optional[KafkaProducer] = None
        self._consumer: Optional[KafkaConsumer] = None
        
        self.logger.info(
            "Kafka client initialized",
            bootstrap_servers=self.bootstrap_servers
        )
    
    def _load_schemas(self):
        """Load all JSON schema files from schemas directory.

        Scans schema_dir for *.json files and loads them into self.schemas dict.
        Schema name is the filename without .json extension.

        Note:
            Logs warning if schema_dir doesn't exist. Continues without schemas
            if loading fails (validation will be skipped).
        """
        if not self.schema_dir.exists():
            self.logger.warning(
                "Schema directory not found",
                schema_dir=str(self.schema_dir)
            )
            return

        for schema_file in self.schema_dir.glob("*.json"):
            try:
                with open(schema_file, "r", encoding="utf-8") as f:
                    schema = json.load(f)
                    schema_name = schema_file.stem
                    self.schemas[schema_name] = schema
                    self.logger.debug(f"Loaded schema: {schema_name}")
            except Exception as e:
                self.logger.error(
                    f"Failed to load schema: {schema_file}",
                    error=str(e)
                )

    def _get_producer(self) -> KafkaProducer:
        """Get or create Kafka producer instance (lazy initialization).

        Creates producer on first call with reliable delivery settings:
        - acks='all': Wait for all replicas to acknowledge
        - retries=3: Retry on transient failures
        - max_in_flight=1: Ensure message ordering

        Returns:
            KafkaProducer: Configured producer instance
        """
        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",  # Wait for acknowledgment from all replicas
                retries=3,
                max_in_flight_requests_per_connection=1  # Ensure ordering
            )
            self.logger.info("Kafka producer created")
        return self._producer
    
    def validate_payload(
        self,
        payload: Dict[str, Any],
        schema_name: str
    ) -> bool:
        """Validate payload against JSON schema specification.

        Enforces message contracts between agents using JSON Schema validation.
        Logs warnings if schema not found (validation skipped).

        Args:
            payload: Message payload dictionary to validate
            schema_name: Schema filename without .json extension

        Returns:
            True if valid or schema not found (lenient mode)

        Raises:
            ValidationError: If payload doesn't match schema specification

        Example:
            >>> client = KafkaClient(agent_name="test")
            >>> payload = {"schemaVersion": "1.0", "taskId": "task-123"}
            >>> client.validate_payload(payload, "fact_checking_input")
        """
        if schema_name not in self.schemas:
            self.logger.warning(
                f"Schema not found: {schema_name}, skipping validation"
            )
            return True
        
        schema = self.schemas[schema_name]
        
        try:
            validate(instance=payload, schema=schema)
            self.logger.debug(f"Payload validated against schema: {schema_name}")
            return True
        except ValidationError as e:
            self.logger.error(
                "Payload validation failed",
                schema_name=schema_name,
                error=str(e),
                payload_preview=str(payload)[:200]
            )
            raise
    
    def produce(
        self,
        topic: str,
        payload: Dict[str, Any],
        key: Optional[str] = None,
        schema_name: Optional[str] = None,
        validate_schema: bool = True
    ) -> bool:
        """Produce message to Kafka topic with optional schema validation.

        Sends message with synchronous acknowledgment (acks=all) for reliability.
        Validates payload against JSON schema before sending if schema_name provided.

        Args:
            topic: Kafka topic name (e.g., "fact_checking_queue")
            payload: Message payload dictionary
            key: Partition key for message ordering (optional)
            schema_name: JSON schema name for validation (optional)
            validate_schema: Enable schema validation (default: True)

        Returns:
            True if message sent successfully, False on error

        Example:
            >>> client = KafkaClient(agent_name="ingestion_agent")
            >>> client.produce(
            ...     topic="fact_checking_queue",
            ...     payload={
            ...         "schemaVersion": "1.0",
            ...         "taskId": "task-123",
            ...         "articles": [...]
            ...     },
            ...     schema_name="fact_checking_input"
            ... )
        """
        producer = self._get_producer()
        
        # Validoi payload tarvittaessa
        if validate_schema and schema_name:
            try:
                self.validate_payload(payload, schema_name)
            except ValidationError:
                return False
        
        # Lähetä viesti
        try:
            future = producer.send(
                topic,
                value=payload,
                key=key
            )
            
            # Odota vahvistus (synkroninen)
            record_metadata = future.get(timeout=10)
            
            self.logger.info(
                "Message produced",
                topic=topic,
                partition=record_metadata.partition,
                offset=record_metadata.offset,
                task_id=payload.get("taskId"),
                schema_name=schema_name
            )
            
            return True
            
        except KafkaError as e:
            self.log_error(
                e,
                context={
                    "topic": topic,
                    "task_id": payload.get("taskId")
                }
            )
            return False
    
    def consume(
        self,
        topic: str,
        message_handler: Callable[[Dict[str, Any]], bool],
        group_id: Optional[str] = None,
        schema_name: Optional[str] = None,
        validate_schema: bool = True,
        auto_commit: bool = False
    ):
        """Consume messages from Kafka topic with manual offset commits.

        Blocking operation that polls for messages indefinitely until KeyboardInterrupt.
        Calls message_handler for each message and commits offset only on success.

        Args:
            topic: Kafka topic to consume from
            message_handler: Callback function that processes message payload.
                           Must return True for successful processing (commits offset).
            group_id: Consumer group ID (default: {agent_name}_group)
            schema_name: JSON schema name for validation (optional)
            validate_schema: Enable schema validation (default: True)
            auto_commit: Enable automatic offset commits (not recommended)

        Example:
            >>> def process_message(payload: dict) -> bool:
            ...     print(f"Processing task {payload['taskId']}")
            ...     # ... process articles ...
            ...     return True  # Success: commit offset
            >>>
            >>> client = KafkaClient(agent_name="verification_agent")
            >>> client.consume(
            ...     topic="fact_checking_queue",
            ...     message_handler=process_message,
            ...     schema_name="fact_checking_input"
            ... )

        Note:
            This is a blocking operation. Run in dedicated thread or process.
            Press Ctrl+C to gracefully shut down consumer.
        """
        if group_id is None:
            group_id = f"{self.settings.kafka_consumer_group_prefix}_{self.agent_name}"
        
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="earliest",  # Aloita alusta jos ei offsettia
            enable_auto_commit=auto_commit,
            max_poll_records=10  # Käsittele 10 viestiä kerralla
        )
        
        self.logger.info(
            "Starting to consume messages",
            topic=topic,
            group_id=group_id
        )
        
        try:
            for message in consumer:
                payload = message.value
                task_id = payload.get("taskId", "unknown")
                
                self.logger.info(
                    "Message received",
                    topic=topic,
                    partition=message.partition,
                    offset=message.offset,
                    task_id=task_id
                )
                
                # Validoi payload
                if validate_schema and schema_name:
                    try:
                        self.validate_payload(payload, schema_name)
                    except ValidationError as e:
                        self.logger.error(
                            "Invalid message received, skipping",
                            task_id=task_id,
                            error=str(e)
                        )
                        consumer.commit()  # Commitoi että skippataan tämä viesti
                        continue
                
                # Käsittele viesti
                try:
                    success = message_handler(payload)
                    
                    if success:
                        consumer.commit()  # Commitoi offset vain onnistuneen käsittelyn jälkeen
                        self.logger.info(
                            "Message processed successfully",
                            task_id=task_id
                        )
                    else:
                        self.logger.warning(
                            "Message processing returned False",
                            task_id=task_id
                        )
                        # Ei commitoida, viesti käsitellään uudelleen
                        
                except Exception as e:
                    self.log_error(
                        e,
                        context={
                            "topic": topic,
                            "task_id": task_id,
                            "offset": message.offset
                        }
                    )
                    # Ei commitoida, viesti käsitellään uudelleen
                    time.sleep(5)  # Backoff ennen uudelleenyritystä
                    
        except KeyboardInterrupt:
            self.logger.info("Consumer interrupted, shutting down")
        finally:
            consumer.close()
            self.logger.info("Consumer closed")
    
    def close(self):
        """Close all Kafka connections and flush pending messages.

        Gracefully shuts down producer/consumer, ensuring all buffered messages
        are sent before closing. Call during application shutdown.

        Note:
            Producer.close() blocks until all pending messages are delivered
            or timeout occurs. Consumer.close() commits offsets before closing.
        """
        if self._producer:
            self._producer.close()
            self.logger.info("Kafka producer closed")
        if self._consumer:
            self._consumer.close()
            self.logger.info("Kafka consumer closed")


class KafkaProducerClient:
    """Legacy wrapper for backward compatibility with older API routes.

    This class provides a simplified interface matching the original API layer
    expectations while delegating to the newer KafkaClient implementation.
    Use KafkaClient directly for new code - this wrapper exists only for
    compatibility during migration.

    Legacy Interface:
        - Default constructor (or optional agent_name)
        - send_message(topic, message) method
        - No schema validation (for backward compatibility)

    Attributes:
        _client (KafkaClient): Internal KafkaClient instance

    Usage:
        >>> # Legacy API code
        >>> producer = KafkaProducerClient()
        >>> producer.send_message("fact_checking_queue", {
        ...     "taskId": "task-123",
        ...     "articles": [...]
        ... })

    Note:
        Prefer using KafkaClient directly for new code. This wrapper will be
        deprecated once all routes are migrated to the new interface.
    """

    def __init__(self, agent_name: str = "api"):
        """Initialize legacy Kafka producer wrapper.

        Args:
            agent_name: Agent name for logging (default: "api")
        """
        # Use a generic agent name so messages are attributed clearly in logs
        self._client = KafkaClient(agent_name=agent_name)

    def send_message(self, topic: str, message: Dict[str, Any]) -> bool:
        """Send JSON message to Kafka topic without schema validation.

        Legacy method for backward compatibility with existing API routes.
        Does not perform schema validation for compatibility reasons.

        Args:
            topic: Kafka topic name
            message: Message payload dictionary

        Returns:
            True if sent successfully, False on error

        Example:
            >>> producer = KafkaProducerClient()
            >>> producer.send_message("fact_checking_queue", {
            ...     "taskId": "task-123",
            ...     "articles": [...]
            ... })
        """
        return self._client.produce(
            topic=topic,
            payload=message,
            key=message.get("task_id") or message.get("taskId"),
            schema_name=None,
            validate_schema=False,
        )


if __name__ == "__main__":
    # Testaa Kafka-asiakasta
    test_client = KafkaClient(agent_name="test")
    
    # Testaa viestien tuottaminen
    test_payload = {
        "schemaVersion": "1.0",
        "taskId": "task-20251010-001",
        "test": "data"
    }
    
    test_client.produce(
        topic="test_topic",
        payload=test_payload,
        key="test-key"
    )

