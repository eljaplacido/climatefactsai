"""
Translation Routes -- Multi-language content access and translation management.

Supports 10+ languages for article content, enabling global accessibility.
Provides both on-demand translation and pre-translated content retrieval.
API-first design for agentic integration.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from api.auth_routes import get_optional_user
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("translation-api")
router = APIRouter(prefix="/api/translations", tags=["Translations"])

# 10 most widely spoken languages + platform languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "zh": "Chinese (Simplified)",
    "es": "Spanish",
    "hi": "Hindi",
    "ar": "Arabic",
    "fr": "French",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "de": "German",
    "fi": "Finnish",
    "ko": "Korean",
    "it": "Italian",
    "nl": "Dutch",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "pl": "Polish",
    "tr": "Turkish",
    "uk": "Ukrainian",
}

# UI translation keys for frontend i18n
UI_TRANSLATIONS = {
    "en": {
        "nav.home": "News", "nav.map": "Map", "nav.search": "Search",
        "nav.deep_search": "Deep Search", "nav.research": "Research",
        "article.claims": "Claims", "article.verified": "Verified",
        "article.credibility": "Credibility", "article.source": "Source",
        "map.title": "Climate Intelligence World Map",
        "map.publisher_origin": "Publisher Origin",
        "map.countries_discussed": "Countries Discussed",
        "map.query_placeholder": "Ask about climate news...",
        "common.loading": "Loading...", "common.no_results": "No results found",
        "common.filter": "Filter", "common.search": "Search",
        "common.reliability": "Reliability", "common.high": "High",
        "common.medium": "Medium", "common.low": "Low",
    },
    "fi": {
        "nav.home": "Uutiset", "nav.map": "Kartta", "nav.search": "Haku",
        "nav.deep_search": "Syvahaku", "nav.research": "Tutkimus",
        "article.claims": "Vaitokset", "article.verified": "Vahvistettu",
        "article.credibility": "Uskottavuus", "article.source": "Lahde",
        "map.title": "Ilmastotiedustelumaailmankartta",
        "map.publisher_origin": "Julkaisijan alkupera",
        "map.countries_discussed": "Maita kasitelty",
        "map.query_placeholder": "Kysy ilmastouutisista...",
        "common.loading": "Ladataan...", "common.no_results": "Ei tuloksia",
        "common.filter": "Suodata", "common.search": "Haku",
        "common.reliability": "Luotettavuus", "common.high": "Korkea",
        "common.medium": "Keskitaso", "common.low": "Matala",
    },
    "zh": {
        "nav.home": "新闻", "nav.map": "地图", "nav.search": "搜索",
        "nav.deep_search": "深度搜索", "nav.research": "研究",
        "article.claims": "声明", "article.verified": "已验证",
        "article.credibility": "可信度", "article.source": "来源",
        "map.title": "气候情报世界地图",
        "common.loading": "加载中...", "common.no_results": "未找到结果",
    },
    "es": {
        "nav.home": "Noticias", "nav.map": "Mapa", "nav.search": "Buscar",
        "nav.deep_search": "Busqueda profunda", "nav.research": "Investigacion",
        "article.claims": "Afirmaciones", "article.verified": "Verificado",
        "article.credibility": "Credibilidad", "article.source": "Fuente",
        "map.title": "Mapa mundial de inteligencia climatica",
        "common.loading": "Cargando...", "common.no_results": "Sin resultados",
    },
    "fr": {
        "nav.home": "Actualites", "nav.map": "Carte", "nav.search": "Rechercher",
        "nav.deep_search": "Recherche approfondie", "nav.research": "Recherche",
        "article.claims": "Declarations", "article.verified": "Verifie",
        "article.credibility": "Credibilite", "article.source": "Source",
        "map.title": "Carte mondiale du renseignement climatique",
        "common.loading": "Chargement...", "common.no_results": "Aucun resultat",
    },
    "ar": {
        "nav.home": "اخبار", "nav.map": "خريطة", "nav.search": "بحث",
        "article.claims": "ادعاءات", "article.verified": "تم التحقق",
        "article.credibility": "المصداقية", "article.source": "المصدر",
        "map.title": "خريطة الاستخبارات المناخية العالمية",
        "common.loading": "جار التحميل...", "common.no_results": "لا توجد نتائج",
    },
    "pt": {
        "nav.home": "Noticias", "nav.map": "Mapa", "nav.search": "Pesquisar",
        "article.claims": "Declaracoes", "article.verified": "Verificado",
        "map.title": "Mapa mundial de inteligencia climatica",
        "common.loading": "Carregando...", "common.no_results": "Sem resultados",
    },
    "hi": {
        "nav.home": "समाचार", "nav.map": "मानचित्र", "nav.search": "खोजे",
        "article.claims": "दावे", "article.verified": "सत्यापित",
        "map.title": "जलवायु खुफिया विश्व मानचित्र",
        "common.loading": "लोड हो रहा है...", "common.no_results": "कोई परिणाम नहीं",
    },
    "ru": {
        "nav.home": "Новости", "nav.map": "Карта", "nav.search": "Поиск",
        "article.claims": "Утверждения", "article.verified": "Подтверждено",
        "map.title": "Мировая карта климатической разведки",
        "common.loading": "Загрузка...", "common.no_results": "Нет результатов",
    },
    "ja": {
        "nav.home": "ニュース", "nav.map": "地図", "nav.search": "検索",
        "article.claims": "主張", "article.verified": "検証済み",
        "map.title": "気候インテリジェンス世界地図",
        "common.loading": "読み込み中...", "common.no_results": "結果なし",
    },
    "de": {
        "nav.home": "Nachrichten", "nav.map": "Karte", "nav.search": "Suchen",
        "article.claims": "Behauptungen", "article.verified": "Verifiziert",
        "map.title": "Klimaintelligenz-Weltkarte",
        "common.loading": "Wird geladen...", "common.no_results": "Keine Ergebnisse",
    },
}


class TranslatedArticle(BaseModel):
    article_id: str
    original_language: str
    target_language: str
    translated_title: str
    translated_summary: Optional[str] = None
    translation_confidence: float = 0.0
    translation_service: str = "deepl"
    translated_at: Optional[str] = None


class TranslationRequest(BaseModel):
    article_id: str
    target_language: str = Field(..., min_length=2, max_length=5)


class TranslationStatusResponse(BaseModel):
    article_id: str
    available_languages: List[str]
    original_language: str


@router.get("/languages")
async def list_supported_languages():
    """
    List all supported translation languages.

    Returns the full language map for UI rendering and agentic discovery.
    """
    return {
        "languages": [
            {"code": code, "name": name}
            for code, name in SUPPORTED_LANGUAGES.items()
        ],
        "total": len(SUPPORTED_LANGUAGES),
        "default": "en",
    }


@router.get("/ui/{language_code}")
async def get_ui_translations(language_code: str):
    """
    Get UI translation strings for a specific language.

    Used by the frontend i18n system and agentic interfaces to render
    the UI in the user's preferred language.
    """
    lang = language_code.lower()[:2]
    translations = UI_TRANSLATIONS.get(lang)

    if not translations:
        # Fall back to English
        translations = UI_TRANSLATIONS["en"]

    return {
        "language": lang,
        "translations": translations,
        "is_fallback": lang not in UI_TRANSLATIONS,
        "rtl": lang in ("ar", "he", "fa"),
    }


@router.get("/article/{article_id}")
async def get_article_translations(
    article_id: str,
    language: Optional[str] = Query(default=None, description="Specific language code"),
):
    """
    Get all available translations for an article, or a specific language.

    Returns translated title and summary with confidence scores.
    Accessible via agentic features for multilingual content delivery.
    """
    db = get_postgres()

    try:
        if language:
            rows = db.execute_query("""
                SELECT t.article_id, t.from_language, t.to_language,
                       t.translated_title, t.translated_summary,
                       t.translation_confidence, t.translation_service,
                       t.translated_at
                FROM article_translations t
                WHERE t.article_id = :aid AND t.to_language = :lang
            """, {"aid": article_id, "lang": language.lower()})
        else:
            rows = db.execute_query("""
                SELECT t.article_id, t.from_language, t.to_language,
                       t.translated_title, t.translated_summary,
                       t.translation_confidence, t.translation_service,
                       t.translated_at
                FROM article_translations t
                WHERE t.article_id = :aid
                ORDER BY t.to_language
            """, {"aid": article_id})

        if not rows and language:
            # Try to trigger on-demand translation
            return {
                "article_id": article_id,
                "language": language,
                "status": "not_available",
                "message": f"Translation to {SUPPORTED_LANGUAGES.get(language, language)} not yet available. Use POST /api/translations/request to trigger.",
            }

        return {
            "article_id": article_id,
            "translations": [
                TranslatedArticle(
                    article_id=r["article_id"],
                    original_language=r.get("from_language", "en"),
                    target_language=r["to_language"],
                    translated_title=r.get("translated_title", ""),
                    translated_summary=r.get("translated_summary"),
                    translation_confidence=float(r.get("translation_confidence", 0)),
                    translation_service=r.get("translation_service", "deepl"),
                    translated_at=str(r["translated_at"]) if r.get("translated_at") else None,
                ).dict()
                for r in (rows or [])
            ],
            "total": len(rows or []),
        }

    except Exception as e:
        logger.error(f"Translation fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch translations")


@router.post("/request")
async def request_translation(
    request: TranslationRequest,
    current_user: dict = Depends(get_optional_user),
):
    """
    Request on-demand translation of an article to a specific language.

    Queues a Celery translation task. Returns immediately with job status.
    Accessible via agentic features for programmatic translation triggers.
    """
    lang = request.target_language.lower()[:2]

    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Language '{lang}' not supported. Supported: {list(SUPPORTED_LANGUAGES.keys())}",
        )

    try:
        from app.tasks.translation import translate_article
        translate_article.delay(request.article_id, [lang])

        return {
            "status": "queued",
            "article_id": request.article_id,
            "target_language": lang,
            "language_name": SUPPORTED_LANGUAGES[lang],
            "message": f"Translation to {SUPPORTED_LANGUAGES[lang]} has been queued.",
        }
    except Exception as e:
        logger.error(f"Translation request failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue translation")


@router.get("/coverage")
async def get_translation_coverage():
    """
    Get platform-wide translation coverage statistics.

    Shows how many articles are translated into each language.
    Useful for agentic reporting and platform health dashboards.
    """
    db = get_postgres()

    try:
        rows = db.execute_query("""
            SELECT to_language, COUNT(*) as translated_count,
                   AVG(translation_confidence) as avg_confidence
            FROM article_translations
            GROUP BY to_language
            ORDER BY translated_count DESC
        """)

        total_articles = db.execute_query("SELECT COUNT(*) as cnt FROM articles")
        total = total_articles[0]["cnt"] if total_articles else 0

        return {
            "total_articles": total,
            "coverage": [
                {
                    "language": r["to_language"],
                    "language_name": SUPPORTED_LANGUAGES.get(r["to_language"], r["to_language"]),
                    "translated_count": r.get("translated_count", 0),
                    "coverage_pct": round(r.get("translated_count", 0) / max(total, 1) * 100, 1),
                    "avg_confidence": round(float(r.get("avg_confidence", 0)), 2),
                }
                for r in (rows or [])
            ],
            "supported_languages": len(SUPPORTED_LANGUAGES),
        }

    except Exception as e:
        logger.error(f"Translation coverage query failed: {e}")
        return {"total_articles": 0, "coverage": [], "supported_languages": len(SUPPORTED_LANGUAGES)}
