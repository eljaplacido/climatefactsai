"""
Translation Tasks — DeepL-powered article translation for EU multilingual support.

Translates article titles, summaries, and content into target languages
and stores results in the article_translations table.
"""

import os
from typing import Dict, List, Optional

import requests

from app.core.celery_app import app
from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
DEEPL_API_URL = os.getenv(
    "DEEPL_API_URL", "https://api-free.deepl.com/v2/translate"
)

# DeepL supported language codes (subset relevant to EU)
DEEPL_LANGUAGES = {
    "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr",
    "hu", "id", "it", "ja", "ko", "lt", "lv", "nb", "nl", "pl",
    "pt", "ro", "ru", "sk", "sl", "sv", "tr", "uk", "zh",
}

# Default target languages: top 10 global + platform languages
DEFAULT_TARGET_LANGUAGES = ["en", "zh", "es", "hi", "ar", "fr", "pt", "ru", "ja", "de", "fi"]


def _translate_text(
    text: str,
    source_lang: str,
    target_lang: str,
) -> Dict:
    """
    Translate text via DeepL API.

    Returns dict with translated_text, detected_source_language, confidence.
    Falls back gracefully when API key is missing.
    """
    if not text or not text.strip():
        return {
            "translated_text": "",
            "detected_source_language": source_lang,
            "confidence": 0.0,
        }

    if not DEEPL_API_KEY:
        logger.warning("DEEPL_API_KEY not set — skipping translation")
        return {
            "translated_text": text,
            "detected_source_language": source_lang,
            "confidence": 0.0,
        }

    # Normalize language codes for DeepL
    src = source_lang.upper()[:2]
    tgt = target_lang.upper()[:2]

    # DeepL uses EN-US/EN-GB for target, but EN for source
    if tgt == "EN":
        tgt = "EN-US"

    try:
        response = requests.post(
            DEEPL_API_URL,
            data={
                "auth_key": DEEPL_API_KEY,
                "text": text,
                "source_lang": src,
                "target_lang": tgt,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        translation = data["translations"][0]
        return {
            "translated_text": translation["text"],
            "detected_source_language": translation.get(
                "detected_source_language", source_lang
            ).lower(),
            "confidence": 1.0,
        }
    except requests.RequestException as e:
        logger.error("DeepL API request failed: %s", e)
        return {
            "translated_text": text,
            "detected_source_language": source_lang,
            "confidence": 0.0,
        }


@app.task(
    name="app.tasks.translation.translate_article",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="processing_queue",
)
def translate_article(
    self,
    article_id: str,
    target_languages: Optional[List[str]] = None,
):
    """
    Translate a single article into one or more target languages.

    Reads the article's source language from countries table,
    translates title + summary + excerpt, and upserts into
    article_translations.
    """
    targets = target_languages or DEFAULT_TARGET_LANGUAGES
    db = get_db()

    try:
        # Fetch article with its language
        rows = db.execute_query(
            """
            SELECT a.article_id, a.title, a.summary_text, a.excerpt,
                   COALESCE(c.language_code, 'en') AS source_lang
            FROM articles a
            LEFT JOIN countries c ON a.country_code = c.country_code
            WHERE a.article_id = :article_id
            """,
            {"article_id": article_id},
        )
        if not rows:
            logger.warning("Article %s not found for translation", article_id)
            return {"status": "not_found", "article_id": article_id}

        article = rows[0]
        source_lang = article["source_lang"]
        title = article.get("title") or ""
        summary = article.get("summary_text") or article.get("excerpt") or ""

        results = []
        for lang in targets:
            if lang == source_lang:
                continue  # Skip translating to same language

            if lang.lower() not in DEEPL_LANGUAGES:
                logger.info("Skipping unsupported language: %s", lang)
                continue

            # Check if translation already exists
            existing = db.execute_query(
                """
                SELECT translation_id FROM article_translations
                WHERE article_id = :article_id AND to_language = :lang
                """,
                {"article_id": article_id, "lang": lang},
            )
            if existing:
                logger.debug(
                    "Translation already exists: %s → %s", article_id, lang
                )
                continue

            # Translate title and summary
            title_result = _translate_text(title, source_lang, lang)
            summary_result = _translate_text(summary, source_lang, lang)

            avg_confidence = (
                title_result["confidence"] + summary_result["confidence"]
            ) / 2

            # Insert translation
            db.execute_query(
                """
                INSERT INTO article_translations (
                    article_id, from_language, to_language,
                    translated_title, translated_summary,
                    translation_service, translation_confidence
                ) VALUES (
                    :article_id, :from_lang, :to_lang,
                    :title, :summary,
                    'deepl', :confidence
                )
                ON CONFLICT (article_id, to_language) DO UPDATE SET
                    translated_title = EXCLUDED.translated_title,
                    translated_summary = EXCLUDED.translated_summary,
                    translation_confidence = EXCLUDED.translation_confidence,
                    translated_at = NOW()
                RETURNING translation_id
                """,
                {
                    "article_id": article_id,
                    "from_lang": source_lang,
                    "to_lang": lang,
                    "title": title_result["translated_text"],
                    "summary": summary_result["translated_text"],
                    "confidence": avg_confidence,
                },
            )

            results.append({"language": lang, "confidence": avg_confidence})

        logger.info(
            "Translated article %s into %d languages",
            article_id,
            len(results),
        )
        return {
            "status": "success",
            "article_id": article_id,
            "translations": results,
        }

    except Exception as exc:
        logger.error("Translation failed for %s: %s", article_id, exc)
        raise self.retry(exc=exc)


@app.task(
    name="app.tasks.translation.batch_translate_recent",
    queue="processing_queue",
)
def batch_translate_recent(
    limit: int = 20,
    target_languages: Optional[List[str]] = None,
):
    """
    Translate recent untranslated articles.

    Finds articles that have no translations yet and dispatches
    individual translate_article tasks for each.
    """
    db = get_db()
    targets = target_languages or DEFAULT_TARGET_LANGUAGES

    rows = db.execute_query(
        """
        SELECT a.article_id
        FROM articles a
        WHERE NOT EXISTS (
            SELECT 1 FROM article_translations t
            WHERE t.article_id = a.article_id
        )
        ORDER BY a.created_at DESC
        LIMIT :limit
        """,
        {"limit": limit},
    )

    if not rows:
        logger.info("No untranslated articles found")
        return {"status": "no_work", "count": 0}

    count = 0
    for row in rows:
        translate_article.delay(row["article_id"], targets)
        count += 1

    logger.info("Queued %d articles for translation", count)
    return {"status": "queued", "count": count}
