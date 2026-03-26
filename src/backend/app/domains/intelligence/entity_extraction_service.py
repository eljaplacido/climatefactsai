"""
Entity Extraction Service for the Knowledge Graph.

Extracts named entities and relationships from article text using LLM
structured prompts, then stores them in the entities / entity_relationships /
article_entities tables for knowledge graph traversal and hybrid RAG.
"""

import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.logging import get_logger
from app.core.database import Database

logger = get_logger(__name__)

ENTITY_TYPES = [
    "PERSON",
    "ORGANIZATION",
    "LOCATION",
    "POLICY",
    "EVENT",
    "TECHNOLOGY",
    "EMISSION_SOURCE",
    "CONCEPT",
]

RELATIONSHIP_TYPES = [
    "CAUSES",
    "AFFECTS",
    "REGULATES",
    "FUNDS",
    "OPPOSES",
    "MITIGATES",
    "REPORTS_ON",
    "LOCATED_IN",
    "MEMBER_OF",
]

EXTRACTION_SYSTEM_PROMPT = """You are a climate-domain named entity and relationship extractor.
Given article text, extract structured entities and relationships.

Return valid JSON with exactly this schema:
{
  "entities": [
    {"name": "string", "type": "ENTITY_TYPE", "description": "one-sentence description"}
  ],
  "relationships": [
    {"source_entity": "entity name", "target_entity": "entity name",
     "relationship_type": "RELATIONSHIP_TYPE", "evidence_text": "quote from article"}
  ]
}

Entity types: PERSON, ORGANIZATION, LOCATION, POLICY, EVENT, TECHNOLOGY, EMISSION_SOURCE, CONCEPT
Relationship types: CAUSES, AFFECTS, REGULATES, FUNDS, OPPOSES, MITIGATES, REPORTS_ON, LOCATED_IN, MEMBER_OF

Rules:
- Extract 3-15 entities. Prefer concrete, named entities.
- Extract 2-10 relationships between those entities.
- Use the entity name exactly as written for relationship source/target.
- Keep descriptions under 100 characters.
- evidence_text should be a short quote (under 200 chars) from the article.
- Return ONLY the JSON object, no markdown fences or commentary.
"""


class EntityExtractionService:
    """Extract entities and relationships from article text and persist to knowledge graph."""

    def __init__(self, db: Database):
        self.db = db

    async def extract_and_store(
        self,
        article_id: str,
        title: str,
        text: str,
    ) -> Dict[str, Any]:
        """
        Extract entities and relationships from article, store in knowledge graph.

        Args:
            article_id: UUID of the article.
            title: Article title.
            text: Article body text (extracted_text or excerpt).

        Returns:
            Summary dict with counts of extracted / linked items.
        """
        # Run LLM extraction
        extraction = await self._llm_extract(title, text)
        if extraction is None:
            return {
                "entities_extracted": 0,
                "relationships_found": 0,
                "new_entities": 0,
                "existing_entities_linked": 0,
                "error": "LLM extraction failed",
            }

        raw_entities = extraction.get("entities", [])
        raw_relationships = extraction.get("relationships", [])

        # Canonicalize and upsert entities
        entity_map: Dict[str, str] = {}  # name -> entity_id
        new_count = 0
        existing_count = 0

        for ent in raw_entities:
            name = (ent.get("name") or "").strip()
            etype = (ent.get("type") or "CONCEPT").upper()
            description = (ent.get("description") or "")[:500]

            if not name:
                continue
            if etype not in ENTITY_TYPES:
                etype = "CONCEPT"

            entity_id, is_new = await self._upsert_entity(
                name=name, entity_type=etype, description=description
            )
            entity_map[name] = entity_id
            if is_new:
                new_count += 1
            else:
                existing_count += 1

        # Insert article_entities junction records
        for name, entity_id in entity_map.items():
            self._link_article_entity(article_id, entity_id)

        # Insert relationships
        rel_count = 0
        for rel in raw_relationships:
            source_name = (rel.get("source_entity") or "").strip()
            target_name = (rel.get("target_entity") or "").strip()
            rel_type = (rel.get("relationship_type") or "AFFECTS").upper()
            evidence = (rel.get("evidence_text") or "")[:500]

            source_id = entity_map.get(source_name)
            target_id = entity_map.get(target_name)

            if not source_id or not target_id:
                continue
            if rel_type not in RELATIONSHIP_TYPES:
                rel_type = "AFFECTS"

            self._insert_relationship(
                source_entity_id=source_id,
                target_entity_id=target_id,
                relationship_type=rel_type,
                article_id=article_id,
                evidence_text=evidence,
            )
            rel_count += 1

        # Generate embeddings for new entities (best-effort)
        await self._generate_entity_embeddings(entity_map)

        summary = {
            "entities_extracted": len(entity_map),
            "relationships_found": rel_count,
            "new_entities": new_count,
            "existing_entities_linked": existing_count,
        }
        logger.info(
            "Entity extraction complete",
            article_id=article_id,
            **summary,
        )
        return summary

    # ------------------------------------------------------------------
    # LLM extraction
    # ------------------------------------------------------------------

    async def _llm_extract(self, title: str, text: str) -> Optional[Dict[str, Any]]:
        """Call LLM to extract entities and relationships as structured JSON."""
        try:
            from app.domains.intelligence.llm_client import llm_chat

            truncated_text = text[:6000]
            prompt = (
                f"Article title: {title}\n\n"
                f"Article text:\n{truncated_text}\n\n"
                "Extract the entities and relationships as described."
            )

            response = llm_chat(
                prompt=prompt,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                max_tokens=2000,
                temperature=0.1,
            )
            if not response:
                logger.warning("LLM returned empty response for entity extraction")
                return None

            # Strip markdown fences if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"Entity extraction JSON parse failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Entity upsert with canonicalization
    # ------------------------------------------------------------------

    async def _upsert_entity(
        self,
        name: str,
        entity_type: str,
        description: str,
    ) -> tuple:
        """
        Find or create an entity. Returns (entity_id, is_new).

        Canonicalization: looks for existing entity with same canonical_name.
        """
        canonical = name.strip().lower()

        existing = self.db.execute_query(
            """SELECT entity_id FROM entities
               WHERE canonical_name = :canonical AND entity_type = :etype
               LIMIT 1""",
            {"canonical": canonical, "etype": entity_type},
        )

        if existing:
            entity_id = str(existing[0]["entity_id"])
            # Increment article_count
            self.db.execute_update(
                "UPDATE entities SET article_count = article_count + 1 WHERE entity_id = :eid",
                {"eid": entity_id},
            )
            return entity_id, False

        # Create new entity
        entity_id = str(uuid4())
        self.db.execute_update(
            """INSERT INTO entities
                   (entity_id, entity_name, entity_type, canonical_name, description, article_count)
               VALUES (:eid, :name, :etype, :canonical, :desc, 1)""",
            {
                "eid": entity_id,
                "name": name,
                "etype": entity_type,
                "canonical": canonical,
                "desc": description,
            },
        )
        return entity_id, True

    # ------------------------------------------------------------------
    # Junction table helpers
    # ------------------------------------------------------------------

    def _link_article_entity(self, article_id: str, entity_id: str) -> None:
        """Insert or update article_entities junction record."""
        try:
            existing = self.db.execute_query(
                """SELECT mention_count FROM article_entities
                   WHERE article_id = :aid AND entity_id = :eid""",
                {"aid": article_id, "eid": entity_id},
            )
            if existing:
                self.db.execute_update(
                    """UPDATE article_entities
                       SET mention_count = mention_count + 1
                       WHERE article_id = :aid AND entity_id = :eid""",
                    {"aid": article_id, "eid": entity_id},
                )
            else:
                self.db.execute_update(
                    """INSERT INTO article_entities (article_id, entity_id, mention_count, salience)
                       VALUES (:aid, :eid, 1, 0.5)""",
                    {"aid": article_id, "eid": entity_id},
                )
        except Exception as e:
            logger.warning(f"Failed to link article-entity: {e}")

    def _insert_relationship(
        self,
        source_entity_id: str,
        target_entity_id: str,
        relationship_type: str,
        article_id: str,
        evidence_text: str,
    ) -> None:
        """Insert an entity relationship record."""
        try:
            rel_id = str(uuid4())
            self.db.execute_update(
                """INSERT INTO entity_relationships
                       (relationship_id, source_entity_id, target_entity_id,
                        relationship_type, strength, confidence, article_id, evidence_text)
                   VALUES (:rid, :src, :tgt, :rtype, 0.5, 0.7, :aid, :evidence)""",
                {
                    "rid": rel_id,
                    "src": source_entity_id,
                    "tgt": target_entity_id,
                    "rtype": relationship_type,
                    "aid": article_id,
                    "evidence": evidence_text,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to insert relationship: {e}")

    # ------------------------------------------------------------------
    # Embedding generation for entities
    # ------------------------------------------------------------------

    async def _generate_entity_embeddings(self, entity_map: Dict[str, str]) -> None:
        """Generate and store embeddings for entities that lack one."""
        try:
            import os
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return

            import openai
            client = openai.OpenAI(api_key=api_key)

            for name, entity_id in entity_map.items():
                # Check if entity already has an embedding
                rows = self.db.execute_query(
                    "SELECT embedding FROM entities WHERE entity_id = :eid AND embedding IS NOT NULL",
                    {"eid": entity_id},
                )
                if rows:
                    continue

                response = client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=name[:8000],
                )
                vector = response.data[0].embedding
                vector_str = "[" + ",".join(str(v) for v in vector) + "]"

                self.db.execute_update(
                    "UPDATE entities SET embedding = :emb::vector WHERE entity_id = :eid",
                    {"emb": vector_str, "eid": entity_id},
                )
        except Exception as e:
            logger.debug(f"Entity embedding generation skipped: {e}")
