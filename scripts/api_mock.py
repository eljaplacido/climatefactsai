"""
Mock API Server for Testing Frontend
Returns sample data without database dependency
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

app = FastAPI(title="Climate News API (Mock)")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock data
MOCK_COUNTRIES = [
    {"country_code": "FI", "country_name": "Finland", "country_name_native": "Suomi", "flag_emoji": "🇫🇮", "language_code": "fi", "is_eu_member": True, "articles_count": 15},
    {"country_code": "SE", "country_name": "Sweden", "country_name_native": "Sverige", "flag_emoji": "🇸🇪", "language_code": "sv", "is_eu_member": True, "articles_count": 12},
    {"country_code": "DE", "country_name": "Germany", "country_name_native": "Deutschland", "flag_emoji": "🇩🇪", "language_code": "de", "is_eu_member": True, "articles_count": 20},
    {"country_code": "FR", "country_name": "France", "country_name_native": "France", "flag_emoji": "🇫🇷", "language_code": "fr", "is_eu_member": True, "articles_count": 18},
    {"country_code": "ES", "country_name": "Spain", "country_name_native": "España", "flag_emoji": "🇪🇸", "language_code": "es", "is_eu_member": True, "articles_count": 14},
]

MOCK_ARTICLES = [
    {
        "article_id": "1",
        "title": "Finland Leads Europe in Renewable Energy Adoption",
        "url": "https://example.com/article1",
        "author": "Climate Reporter",
        "published_date": "2025-10-26T10:00:00Z",
        "source_name": "YLE",
        "source_credibility_score": 92,
        "excerpt": "Finland has announced ambitious plans to achieve carbon neutrality by 2035...",
        "claim_count": 5,
        "verified_claim_count": 4,
        "tags": ["renewable-energy", "policy", "emissions"],
        "content_relevance_score": 0.95,
        "reliability_score": 88,
        "overall_credibility": "HIGH",
        "created_at": "2025-10-26T10:00:00Z",
        "country_code": "FI"
    },
    {
        "article_id": "2",
        "title": "Swedish Carbon Tax Shows Promising Results",
        "url": "https://example.com/article2",
        "author": "Environmental Writer",
        "published_date": "2025-10-25T14:30:00Z",
        "source_name": "SVT",
        "source_credibility_score": 90,
        "excerpt": "Sweden's carbon tax policy has reduced emissions by 15% over the past year...",
        "claim_count": 8,
        "verified_claim_count": 7,
        "tags": ["carbon-tax", "policy", "sweden"],
        "content_relevance_score": 0.92,
        "reliability_score": 86,
        "overall_credibility": "HIGH",
        "created_at": "2025-10-25T14:30:00Z",
        "country_code": "SE"
    },
    {
        "article_id": "3",
        "title": "Germany Expands Wind Energy Infrastructure",
        "url": "https://example.com/article3",
        "author": "Energy Analyst",
        "published_date": "2025-10-24T09:15:00Z",
        "source_name": "DW",
        "source_credibility_score": 85,
        "excerpt": "Germany announces investment of €10 billion in offshore wind farms...",
        "claim_count": 6,
        "verified_claim_count": 5,
        "tags": ["wind-energy", "infrastructure", "germany"],
        "content_relevance_score": 0.88,
        "reliability_score": 82,
        "overall_credibility": "HIGH",
        "created_at": "2025-10-24T09:15:00Z",
        "country_code": "DE"
    },
    {
        "article_id": "4",
        "title": "French Solar Initiative Gains Momentum",
        "url": "https://example.com/article4",
        "author": "Renewable Energy Expert",
        "published_date": "2025-10-23T16:45:00Z",
        "source_name": "France 24",
        "source_credibility_score": 82,
        "excerpt": "France's national solar energy program sees 200% increase in installations...",
        "claim_count": 4,
        "verified_claim_count": 3,
        "tags": ["solar-energy", "france", "renewable"],
        "content_relevance_score": 0.85,
        "reliability_score": 75,
        "overall_credibility": "MEDIUM",
        "created_at": "2025-10-23T16:45:00Z",
        "country_code": "FR"
    },
    {
        "article_id": "5",
        "title": "Spain Faces Drought Challenges Amid Climate Change",
        "url": "https://example.com/article5",
        "author": "Climate Correspondent",
        "published_date": "2025-10-22T11:20:00Z",
        "source_name": "El País",
        "source_credibility_score": 80,
        "excerpt": "Severe drought conditions in southern Spain highlight climate adaptation needs...",
        "claim_count": 7,
        "verified_claim_count": 6,
        "tags": ["drought", "climate-impact", "spain"],
        "content_relevance_score": 0.90,
        "reliability_score": 78,
        "overall_credibility": "MEDIUM",
        "created_at": "2025-10-22T11:20:00Z",
        "country_code": "ES"
    },
]

MOCK_TAGS = [
    {"tag": "renewable-energy", "article_count": 25},
    {"tag": "policy", "article_count": 18},
    {"tag": "emissions", "article_count": 15},
    {"tag": "carbon-tax", "article_count": 12},
    {"tag": "wind-energy", "article_count": 10},
]

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "mode": "mock"}

@app.get("/api/countries")
async def get_countries():
    return MOCK_COUNTRIES

@app.get("/api/articles")
async def get_articles(
    country: str = None,
    credibility: str = None,
    source: str = None,
    limit: int = 20,
    offset: int = 0
):
    filtered = MOCK_ARTICLES.copy()

    if country:
        filtered = [a for a in filtered if a["country_code"] == country.upper()]
    if credibility:
        filtered = [a for a in filtered if a["overall_credibility"] == credibility.upper()]
    if source:
        filtered = [a for a in filtered if source.lower() in a["source_name"].lower()]

    return filtered[offset:offset + limit]

@app.get("/api/articles/{article_id}")
async def get_article(article_id: str):
    for article in MOCK_ARTICLES:
        if article["article_id"] == article_id:
            return {
                **article,
                "full_text": f"Full article text for: {article['title']}",
                "language_code": "en",
                "claims": [
                    {
                        "claim_id": "c1",
                        "claim_text": "Sample claim from article",
                        "claim_context": "Context...",
                        "claim_type": "factual_data",
                        "fact_check": {
                            "verification_status": "VERIFIED",
                            "confidence_score": 0.85,
                            "justification": "Verified by multiple sources",
                            "evidence": {"sources": ["Source 1", "Source 2"]},
                            "verified_date": "2025-10-26T10:00:00Z"
                        }
                    }
                ]
            }
    return {"error": "Article not found"}

@app.get("/api/tags")
async def get_tags(country: str = None):
    return MOCK_TAGS

@app.get("/api/stats")
async def get_stats():
    return {
        "total_articles": 75,
        "articles_today": 5,
        "total_fact_checks": 150,
        "verified_claims": 132,
        "average_confidence": 85.5,
        "last_updated": datetime.utcnow().isoformat()
    }

@app.get("/api/admin/dashboard")
async def admin_dashboard():
    return await get_stats()

@app.get("/api/admin/workflows")
async def admin_workflows(limit: int = 10):
    return []

@app.post("/api/admin/trigger-workflow")
async def trigger_workflow():
    return {
        "task_id": "mock-task-123",
        "status": "triggered",
        "message": "Mock workflow triggered (no actual processing in mock mode)"
    }

if __name__ == "__main__":
    import uvicorn
    print("=" * 70)
    print("Starting Mock API Server for Frontend Testing")
    print("=" * 70)
    print("This server returns sample data without requiring database connection")
    print("Perfect for testing the frontend interface!")
    print("=" * 70)
    uvicorn.run(app, host="0.0.0.0", port=8000)
