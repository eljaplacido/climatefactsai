"""
Standalone script to fetch live climate news using Perplexity API
and populate the database directly.

This bypasses the complex microservices for MVP testing.
"""

import os
import sys
import json
import time
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5433")),
    "database": os.getenv("POSTGRES_DB", "climatenews"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

# Topics to search for
CLIMATE_TOPICS = [
    "Finland climate change news today",
    "Sweden renewable energy latest news",
    "European climate policy updates 2025",
    "Nordic countries carbon emissions reduction",
    "Finland climate adaptation measures",
    "Baltic Sea climate impact latest research",
]


def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        print(f"  Using config: {DB_CONFIG}")
        return None


def fetch_climate_news_perplexity(query: str) -> Dict[str, Any]:
    """
    Fetch climate news from Perplexity API

    Args:
        query: Search query

    Returns:
        Response from Perplexity API
    """
    url = "https://api.perplexity.ai/chat/completions"

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "llama-3.1-sonar-large-128k-online",
        "messages": [
            {
                "role": "system",
                "content": "You are a climate news researcher. Provide recent, factual climate news articles with sources. Format your response as JSON with fields: articles (array of {title, url, source, published_date, summary, key_claims})."
            },
            {
                "role": "user",
                "content": f"Find recent climate news articles about: {query}. Return as JSON with detailed article information including URLs, sources, and key claims."
            }
        ],
        "temperature": 0.2,
        "max_tokens": 2000,
    }

    try:
        print(f"  Searching Perplexity for: {query}")
        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"  ✗ Perplexity API error: {response.status_code}")
            print(f"    Response: {response.text}")
            return None
    except Exception as e:
        print(f"  ✗ Error calling Perplexity: {e}")
        return None


def parse_perplexity_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse Perplexity response to extract articles

    Args:
        response: Perplexity API response

    Returns:
        List of article dictionaries
    """
    if not response or "choices" not in response:
        return []

    content = response["choices"][0]["message"]["content"]

    # Try to parse as JSON
    try:
        # Find JSON block in the response
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1

        if start_idx != -1 and end_idx > start_idx:
            json_str = content[start_idx:end_idx]
            data = json.loads(json_str)

            if "articles" in data:
                return data["articles"]
    except json.JSONDecodeError:
        pass

    # If JSON parsing fails, create a single article from the content
    # Extract citations from Perplexity response
    citations = response.get("citations", [])

    return [{
        "title": "Climate News Summary",
        "url": citations[0] if citations else "https://perplexity.ai",
        "source": "Perplexity Research",
        "published_date": datetime.now(timezone.utc).isoformat(),
        "summary": content[:500],
        "key_claims": []
    }]


def insert_article(conn, article: Dict[str, Any], country_code: str = "FI") -> str:
    """
    Insert article into database

    Args:
        conn: Database connection
        article: Article dictionary
        country_code: Country code

    Returns:
        Article ID
    """
    cursor = conn.cursor()

    query = """
    INSERT INTO articles (
        url, title, author, published_date, source_name,
        extracted_text, excerpt, language_code, country_code,
        source_credibility_score, tags, reliability_score,
        overall_credibility, created_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
    )
    ON CONFLICT (url) DO UPDATE SET
        updated_at = CURRENT_TIMESTAMP
    RETURNING article_id
    """

    # Prepare data
    url = article.get("url", f"https://perplexity.ai/search/{uuid.uuid4()}")
    title = article.get("title", "Climate News Article")
    source = article.get("source", "Perplexity Research")
    summary = article.get("summary", "")

    # Parse published date
    try:
        if isinstance(article.get("published_date"), str):
            published_date = datetime.fromisoformat(article["published_date"].replace("Z", "+00:00"))
        else:
            published_date = datetime.now(timezone.utc)
    except:
        published_date = datetime.now(timezone.utc)

    # Extract tags from summary
    tags = ["climate", "news"]
    if "renewable" in summary.lower() or "energy" in summary.lower():
        tags.append("renewable-energy")
    if "emission" in summary.lower():
        tags.append("emissions")
    if "policy" in summary.lower():
        tags.append("policy")

    # Convert tags to PostgreSQL array format
    tags_array = "{" + ",".join(f'"{tag}"' for tag in tags) + "}"

    try:
        cursor.execute(query, (
            url,
            title,
            None,  # author
            published_date,
            source,
            summary,  # extracted_text
            summary[:280] if len(summary) > 280 else summary,  # excerpt
            "en",  # language_code
            country_code,
            75,  # source_credibility_score (Perplexity is fairly reliable)
            tags_array,
            70,  # reliability_score
            "MEDIUM",  # overall_credibility
        ))

        result = cursor.fetchone()
        article_id = result[0] if result else None
        conn.commit()

        return str(article_id)
    except Exception as e:
        print(f"    ✗ Error inserting article: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()


def insert_claims(conn, article_id: str, claims: List[str]):
    """
    Insert claims for an article

    Args:
        conn: Database connection
        article_id: Article ID
        claims: List of claim texts
    """
    if not claims:
        return

    cursor = conn.cursor()

    query = """
    INSERT INTO claims (
        article_id, claim_text, claim_type, created_at
    ) VALUES (
        %s, %s, %s, CURRENT_TIMESTAMP
    )
    """

    try:
        for claim in claims:
            cursor.execute(query, (
                article_id,
                claim,
                "factual_data"
            ))
        conn.commit()
        print(f"    ✓ Inserted {len(claims)} claims")
    except Exception as e:
        print(f"    ✗ Error inserting claims: {e}")
        conn.rollback()
    finally:
        cursor.close()


def main():
    """Main function"""
    print("=" * 70)
    print("Climate News MVP - Live Data Population")
    print("Using Perplexity API to fetch real climate news")
    print("=" * 70)
    print()

    # Connect to database
    print("Connecting to database...")
    conn = get_db_connection()

    if not conn:
        print("\n✗ Failed to connect to database. Make sure PostgreSQL is running:")
        print("  docker-compose up -d postgres")
        return 1

    print("✓ Connected to database")
    print()

    total_articles = 0

    # Fetch news for each topic
    for i, topic in enumerate(CLIMATE_TOPICS, 1):
        print(f"[{i}/{len(CLIMATE_TOPICS)}] Fetching news for: {topic}")

        # Call Perplexity API
        response = fetch_climate_news_perplexity(topic)

        if not response:
            print(f"  ✗ Skipping due to API error")
            continue

        # Parse response
        articles = parse_perplexity_response(response)
        print(f"  ✓ Found {len(articles)} articles")

        # Insert articles
        for article in articles:
            article_id = insert_article(conn, article, country_code="FI")

            if article_id:
                print(f"    ✓ Inserted article: {article.get('title', 'Untitled')[:50]}...")
                total_articles += 1

                # Insert claims if available
                if article.get("key_claims"):
                    insert_claims(conn, article_id, article["key_claims"])

        # Rate limiting
        if i < len(CLIMATE_TOPICS):
            print("  Waiting 3 seconds (rate limiting)...")
            time.sleep(3)

        print()

    # Close connection
    conn.close()

    print("=" * 70)
    print(f"✓ Data population complete!")
    print(f"  Total articles inserted: {total_articles}")
    print()
    print("Next steps:")
    print("  1. Test the API: http://localhost:8000/api/articles")
    print("  2. Check stats: http://localhost:8000/api/stats")
    print("  3. Search articles: http://localhost:8000/api/articles?tags=climate")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
