"""
Kafka-asiakaskirjasto agenttiviestintään

Tarjoaa yksinkertaiset abstraktiot Kafka-viestin tuottamiseen ja kuluttamiseen
validoiden JSON-skeemoja.
"""

import json
import time
from typing import Any, Callable, Dict, Optional
from pathlib import Path

from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
import jsonschema
from jsonschema import validate, ValidationError

from .config import get_kafka_settings
from .logger import LoggerMixin


class KafkaClient(LoggerMixin):
    """
    Kafka-asiakasluokka viestien tuottamiseen ja kuluttamiseen
    
    Käyttö tuottajana:
        client = KafkaClient(agent_name="content_discovery")
        client.produce("fact_checking_queue", payload_dict)
    
    Käyttö kuluttajana:
        client = KafkaClient(agent_name="fact_checking")
        client.consume("fact_checking_queue", message_handler_callback)
    """
    
    def __init__(
        self,
        agent_name: str,
        schema_dir: Optional[Path] = None
    ):
        """
        Alusta Kafka-asiakas
        
        Args:
            agent_name: Agentin nimi (käytetään consumer groupissa)
            schema_dir: JSON-skeematiedostojen hakemisto (oletus: /schemas)
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
        """Lataa kaikki JSON-skeematiedostot"""
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
        """Palauta (tai luo) Kafka-tuottaja"""
        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",  # Odota vahvistus kaikilta replikoilta
                retries=3,
                max_in_flight_requests_per_connection=1  # Varmista järjestys
            )
            self.logger.info("Kafka producer created")
        return self._producer
    
    def validate_payload(
        self,
        payload: Dict[str, Any],
        schema_name: str
    ) -> bool:
        """
        Validoi payload JSON-skeemaa vasten
        
        Args:
            payload: Validoitava data
            schema_name: Skeeman nimi (ilman .json-päätettä)
        
        Returns:
            True jos validi, nostaa ValidationError jos ei
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
        """
        Tuota viesti Kafka-aiheeseen
        
        Args:
            topic: Kafka-aihe
            payload: Viestidictionary
            key: Viestiavain (valinnainen, partitioinnille)
            schema_name: JSON-skeeman nimi validointiin
            validate_schema: Validoi payload ennen lähetystä
        
        Returns:
            True jos onnistui, False muuten
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
        """
        Kuluta viestejä Kafka-aiheesta
        
        Args:
            topic: Kafka-aihe
            message_handler: Callback-funktio viestin käsittelyyn.
                           Palauttaa True jos käsittely onnistui.
            group_id: Consumer group ID (oletus: {agent_name}_group)
            schema_name: JSON-skeeman nimi validointiin
            validate_schema: Validoi viestit ennen käsittelyä
            auto_commit: Commitoi offsetit automaattisesti (ei suositella)
        
        Huom: Tämä on blocking-funktio, joka kuuntelee ikuisesti
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
        """Sulje kaikki Kafka-yhteydet"""
        if self._producer:
            self._producer.close()
            self.logger.info("Kafka producer closed")
        if self._consumer:
            self._consumer.close()
            self.logger.info("Kafka consumer closed")


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

