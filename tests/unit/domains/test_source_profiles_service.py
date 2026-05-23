from app.domains.content.source_profiles import SourceProfileService


class TrackingDB:
    def __init__(self):
        self.executed = []

    def execute_query(self, query, params=None):
        self.executed.append((query, params or {}))
        normalized = " ".join(query.split()).lower()

        if "from information_schema.columns" in normalized:
            return []

        if "from source_profiles" in normalized:
            raise Exception('column "reliability_tier" does not exist')

        if "from articles" in normalized and "group by source_name" in normalized:
            return [
                {
                    "source_name": "YLE",
                    "sample_url": "https://yle.fi/news",
                    "article_count": 3,
                    "avg_reliability": 79.2,
                    "verified_claims": 7,
                    "disputed_claims": 1,
                }
            ]

        return []

    def execute_update(self, query, params=None):
        self.executed.append((query, params or {}))
        return 1


class ArticlesSchemaLagDB:
    def __init__(self):
        self.executed = []

    def execute_query(self, query, params=None):
        self.executed.append((query, params or {}))
        normalized = " ".join(query.split()).lower()

        if "from information_schema.columns" in normalized:
            table_name = (params or {}).get("table_name")
            if table_name == "source_profiles":
                return []
            if table_name == "articles":
                return [
                    {"column_name": "source_name"},
                    {"column_name": "url"},
                ]
            return []

        if "from source_profiles" in normalized:
            raise Exception('relation "source_profiles" does not exist')

        if "from articles" in normalized and "group by source_name" in normalized:
            assert "avg(reliability_score)" not in normalized
            assert "claims_count" not in normalized
            assert "verified_claims_count" not in normalized
            return [
                {
                    "source_name": "BBC News",
                    "sample_url": "https://www.bbc.com/news",
                    "article_count": 12,
                    "avg_reliability": None,
                    "verified_claims": 0,
                    "disputed_claims": 0,
                }
            ]

        return []

    def execute_update(self, query, params=None):
        self.executed.append((query, params or {}))
        return 1


def test_list_profiles_falls_back_to_articles_when_schema_lags():
    db = TrackingDB()
    service = SourceProfileService(db)

    profiles = service.list_profiles(limit=10)

    assert len(profiles) == 1
    profile = profiles[0]
    assert profile["source_name"] == "YLE"
    assert profile["source_domain"] == "yle.fi"
    assert profile["credibility_score"] == 79
    assert profile["total_articles_analyzed"] == 3
    assert profile["total_claims_verified"] == 7
    assert profile["total_claims_disputed"] == 1
    assert profile["reliability_tier"] == "public"


def test_list_profiles_handles_articles_schema_lag_without_metrics_columns():
    db = ArticlesSchemaLagDB()
    service = SourceProfileService(db)

    profiles = service.list_profiles(limit=10)

    assert len(profiles) == 1
    profile = profiles[0]
    assert profile["source_name"] == "BBC News"
    assert profile["source_domain"] == "bbc.com"
    assert profile["credibility_score"] == 50
    assert profile["total_articles_analyzed"] == 12
    assert profile["total_claims_verified"] == 0
    assert profile["total_claims_disputed"] == 0
    assert profile["reliability_tier"] == "public"
