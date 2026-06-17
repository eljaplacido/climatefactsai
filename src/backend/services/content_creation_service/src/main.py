"""
Content Creation Service - Main Entry Point

Responsible for:
- Generating article summaries from verified claims
- Creating reader-friendly narratives
- Formatting content for publication
"""

import os
import json
import sys
from typing import Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path

from kafka import KafkaConsumer

# Add src/backend to path for shared module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from shared.kafka_client import KafkaClient
from shared.database import PostgresClient
from shared.logger import setup_logger
from content_creator import ContentCreator


class ContentCreationService:
    """
    Content Creation Service

    Transforms verified claims into polished, publishable articles.
    """

    def __init__(self):
        """Initialize Content Creation Service"""
        # Logger
        self.logger = setup_logger("content_creation")

        # Kafka
        self.kafka = KafkaClient()

        # PostgreSQL
        self.postgres = PostgresClient()

        # Content Creator requires a real Perplexity API key. Synthetic fallback
        # has been removed; if no key is configured the service refuses to start
        # rather than emitting fake summaries.
        perplexity_api_key = os.getenv("PERPLEXITY_API_KEY", "").strip()
        if not perplexity_api_key:
            raise RuntimeError(
                "ContentCreationService: PERPLEXITY_API_KEY is required. "
                "Set the env var or do not start this worker."
            )
        self.content_creator = ContentCreator(perplexity_api_key)
        self.provider = "perplexity"

        self.logger.info(
            "ContentCreationService initialized",
            provider=self.provider
        )

    def run(self):
        """Start the service"""
        self.logger.info("Starting Content Creation Service")

        # Listen to content_creation_queue
        consumer = KafkaConsumer(
            self.kafka.settings.kafka_topic_content_creation_queue,
            bootstrap_servers=self.kafka.settings.kafka_bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id="content_creation_group",
            auto_offset_reset='earliest'
        )

        self.logger.info(
            "Listening for content creation tasks",
            topic=self.kafka.settings.kafka_topic_content_creation_queue
        )

        try:
            for message in consumer:
                task = message.value
                self._process_content_task(task)
        except KeyboardInterrupt:
            self.logger.info("Shutting down Content Creation Service")
        finally:
            consumer.close()
            self.kafka.close()
            self.postgres.close()

    def _process_content_task(self, task: Dict[str, Any]):
        """
        Process a content creation task

        Args:
            task: Content creation task from Kafka
        """
        task_id = task.get("taskId")
        command = task.get("command")

        self.logger.info(
            "Processing content creation task",
            task_id=task_id,
            command=command
        )

        try:
            if command == "create_summary":
                self._create_article_summary(task)
            elif command == "create_content":
                self._create_full_content(task)
            else:
                self.logger.warning(
                    "Unknown command",
                    task_id=task_id,
                    command=command
                )

        except Exception as e:
            self.logger.error(
                "Failed to process content task",
                task_id=task_id,
                error=str(e),
                exc_info=True
            )

            # Publish failure event
            self._publish_failure(task_id, str(e))

    def _create_article_summary(self, task: Dict[str, Any]):
        """
        Create an article summary from verified claims

        Args:
            task: Task containing article ID and verified claims
        """
        task_id = task.get("taskId")
        article_id = task.get("articleId")
        verified_claims = task.get("verifiedClaims", [])
        source_article = task.get("sourceArticle", {})

        self.logger.info(
            "Creating article summary",
            task_id=task_id,
            article_id=article_id,
            verified_claims_count=len(verified_claims)
        )

        start_time = datetime.now(timezone.utc)

        # Prepare articles data for ContentCreator
        articles = [{
            "title": source_article.get("title", ""),
            "summary": source_article.get("extractedText", "")[:500],
            "url": source_article.get("url", ""),
            "verified_claims": verified_claims
        }]

        country = task.get("parameters", {}).get("country", "Finland")
        language = task.get("parameters", {}).get("language", "en")

        # Generate summary using ContentCreator
        summary_result = self.content_creator.create_summary(
            articles=articles,
            country=country,
            language=language
        )

        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Save to database
        self._save_generated_content(
            task_id=task_id,
            article_id=article_id,
            content=summary_result,
            processing_time_ms=processing_time * 1000
        )

        # Publish content ready event
        self._publish_content_ready(task_id, article_id, summary_result)

        self.logger.info(
            "Article summary created",
            task_id=task_id,
            article_id=article_id,
            processing_time_seconds=processing_time
        )

    def _create_full_content(self, task: Dict[str, Any]):
        """
        Create full article content with fact-check integration

        Args:
            task: Task containing verification results
        """
        task_id = task.get("taskId")
        article_id = task.get("articleId")
        verification_results = task.get("verificationResults", [])

        self.logger.info(
            "Creating full content",
            task_id=task_id,
            article_id=article_id,
            verification_count=len(verification_results)
        )

        # Build narrative from verification results
        high_confidence_claims = [
            v for v in verification_results
            if v.get("confidenceScore", 0) >= 0.70
        ]

        # Generate content (similar to summary but with more detail)
        articles = [{
            "title": task.get("sourceArticle", {}).get("title", ""),
            "summary": "\n".join([
                f"• {claim.get('claimText', '')} (Confidence: {claim.get('confidenceScore', 0):.0%})"
                for claim in high_confidence_claims
            ])
        }]

        country = task.get("parameters", {}).get("country", "Finland")
        language = task.get("parameters", {}).get("language", "en")

        content_result = self.content_creator.create_summary(
            articles=articles,
            country=country,
            language=language
        )

        # Enhance with fact-check elements
        content_result["factCheckElements"] = self._build_fact_check_elements(
            verification_results
        )

        # Save and publish
        self._save_generated_content(task_id, article_id, content_result)
        self._publish_content_ready(task_id, article_id, content_result)

        self.logger.info(
            "Full content created",
            task_id=task_id,
            article_id=article_id
        )

    def _build_fact_check_elements(
        self,
        verification_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Build interactive fact-check elements

        Args:
            verification_results: List of verification results

        Returns:
            List of fact-check elements for UI
        """
        elements = []

        for result in verification_results:
            element = {
                "claimId": result.get("claimId"),
                "claimText": result.get("claimText"),
                "verificationStatus": result.get("verificationStatus"),
                "confidenceScore": result.get("confidenceScore", 0),
                "sources": [
                    {
                        "name": source.get("sourceName"),
                        "url": source.get("sourceUrl")
                    }
                    for source in result.get("sources", [])
                ],
                "verdict": result.get("verdict", ""),
                "evidenceSummary": result.get("evidenceSummary", "")
            }
            elements.append(element)

        return elements

    def _save_generated_content(
        self,
        task_id: str,
        article_id: str,
        content: Dict[str, Any],
        processing_time_ms: float = 0
    ):
        """
        Save generated content to database

        Args:
            task_id: Task identifier
            article_id: Article identifier
            content: Generated content
            processing_time_ms: Processing time in milliseconds
        """
        query = """
        UPDATE articles
        SET
            summary = :summary,
            content = :content,
            metadata = :metadata,
            updated_at = :updated_at
        WHERE id = :article_id
        """

        metadata = {
            "task_id": task_id,
            "key_findings": content.get("key_findings", []),
            "impact_analysis": content.get("impact_analysis", ""),
            "confidence_assessment": content.get("confidence_assessment", ""),
            "recommended_actions": content.get("recommended_actions", []),
            "processing_time_ms": processing_time_ms,
            "created_with": content.get("created_with", self.provider)
        }

        self.postgres.execute_update(
            query,
            params={
                "article_id": article_id,
                "summary": content.get("summary_plain_text", ""),
                "content": content.get("summary_markdown", ""),
                "metadata": json.dumps(metadata),
                "updated_at": datetime.now(timezone.utc)
            }
        )

        self.logger.info(
            "Generated content saved to database",
            task_id=task_id,
            article_id=article_id
        )

    def _publish_content_ready(
        self,
        task_id: str,
        article_id: str,
        content: Dict[str, Any]
    ):
        """
        Publish content ready event to orchestrator

        Args:
            task_id: Task identifier
            article_id: Article identifier
            content: Generated content
        """
        message = {
            "event": "content_ready",
            "taskId": task_id,
            "articleId": article_id,
            "summary": content.get("summary_plain_text", ""),
            "wordCount": len(content.get("summary_plain_text", "").split()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        self.kafka.produce(
            topic=self.kafka.settings.kafka_topic_orchestrator_responses,
            payload=message,
            key=task_id
        )

        self.logger.info(
            "Content ready notification published",
            task_id=task_id,
            article_id=article_id
        )

    def _publish_failure(self, task_id: str, error: str):
        """
        Publish failure event

        Args:
            task_id: Task identifier
            error: Error message
        """
        message = {
            "event": "content_creation_failed",
            "taskId": task_id,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        self.kafka.produce(
            topic=self.kafka.settings.kafka_topic_orchestrator_responses,
            payload=message,
            key=task_id
        )

        self.logger.error(
            "Content creation failure published",
            task_id=task_id,
            error=error
        )


def main():
    """Main entry point"""
    service = ContentCreationService()
    service.run()


if __name__ == "__main__":
    main()
