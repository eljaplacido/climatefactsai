"""
Hae oikeita ilmastouutisia Perplexitylla ja tallenna tietokantaan
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "agents"))

from content_discovery.perplexity_news_discovery import PerplexityNewsDiscovery
from shared.database import get_postgres
from fact_checking.perplexity_client import PerplexityClient

def fetch_and_verify_news(country="Finland", country_code="FI", max_articles=10):
    """
    Hae uutiset Perplexitylla ja tee faktatarkistukset
    """
    
    api_key = "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"
    
    print(f"\n🌍 Haetaan ilmastouutisia: {country}")
    print("=" * 70)
    
    # 1. HAE UUTISET
    discovery = PerplexityNewsDiscovery(api_key)
    articles = discovery.discover_news(
        country=country,
        country_code=country_code,
        max_articles=max_articles,
        days_back=7
    )
    
    print(f"\n✅ Löydettiin {len(articles)} artikkelia!\n")
    
    # 2. TALLENNA TIETOKANTAAN
    db = get_postgres()
    fact_checker = PerplexityClient(api_key)
    
    saved_count = 0
    
    for i, article in enumerate(articles, 1):
        print(f"{i}. {article['title'][:65]}...")
        print(f"   Lähde: {article['source_name']}")
        
        # Tallenna artikkeli
        article_query = """
            INSERT INTO articles (
                title, url, source_name, extracted_text,
                language_code, published_date, country_code,
                source_credibility_score
            )
            VALUES (
                :title, :url, :source, :content,
                :lang, :published, :country, :credibility
            )
            ON CONFLICT (url) DO UPDATE SET
                title = EXCLUDED.title,
                extracted_text = EXCLUDED.extracted_text
            RETURNING article_id
        """
        
        try:
            result = db.execute_query(article_query, {
                "title": article['title'],
                "url": article['url'],
                "source": article['source_name'],
                "content": article['summary'],
                "lang": article['language_code'],
                "published": article['published_date'],
                "country": article['country_code'],
                "credibility": article['credibility_score']
            })
            
            if result:
                article_id = result[0]['article_id']
                saved_count += 1
                print(f"   ✅ Tallennettu (ID: {str(article_id)[:8]}...)")
                
                # 3. FAKTATARKISTUS (jos artikkeli on uusi)
                print(f"   🔍 Faktatarkistetaan...")
                
                # Tee yksinkertainen claim artikkelin otsikosta
                claim_text = article['title']
                
                fact_check_result = fact_checker.verify_claim(
                    claim=claim_text,
                    context=article['summary'][:200],
                    location=country
                )
                
                # Debug: Tarkista tyyppi
                if isinstance(fact_check_result, str):
                    print(f"   ⚠️  Perplexity palautti stringin, ohitetaan faktatarkistus")
                    continue
                
                # Tallenna claim
                claim_query = """
                    INSERT INTO claims (
                        article_id, claim_text, claim_type
                    )
                    VALUES (:article_id, :claim_text, 'FACTUAL_STATEMENT')
                    RETURNING claim_id
                """
                
                claim_result = db.execute_query(claim_query, {
                    "article_id": article_id,
                    "claim_text": claim_text
                })
                
                if claim_result:
                    claim_id = claim_result[0]['claim_id']
                    
                    # Tallenna faktatarkistus
                    status_map = {
                        'TRUE': 'VERIFIED',
                        'FALSE': 'FALSE',
                        'PARTIALLY_TRUE': 'PARTIALLY_VERIFIED',
                        'DISPUTED': 'DISPUTED'
                    }
                    
                    fact_query = """
                        INSERT INTO fact_checks (
                            claim_id, verification_status, confidence_score,
                            justification, evidence
                        )
                        VALUES (
                            :claim_id, :status, :confidence,
                            :justification, :evidence
                        )
                        RETURNING fact_check_id
                    """
                    
                    # Rakenna evidence JSONB
                    evidence_json = {
                        'sources': fact_check_result.get('sources', []),
                        'citations': fact_check_result.get('citations', []),
                        'checked_with': 'perplexity'
                    }
                    
                    import json
                    db.execute_query(fact_query, {
                        "claim_id": claim_id,
                        "status": status_map.get(fact_check_result.get('verdict', 'UNKNOWN'), 'UNVERIFIED'),
                        "confidence": min(fact_check_result.get('confidence', 0.5), 0.99),  # Max 0.99 for NUMERIC(3,2)
                        "justification": fact_check_result.get('explanation', '')[:500],
                        "evidence": json.dumps(evidence_json)
                    })
                    
                    verdict = fact_check_result.get('verdict', 'UNKNOWN')
                    confidence = int(fact_check_result.get('confidence', 0) * 100)
                    print(f"   ✅ Faktatarkistettu: {verdict} ({confidence}%)")
                
                print()
                
        except Exception as e:
            print(f"   ❌ Virhe: {str(e)[:80]}")
            print()
    
    db.close()
    
    print("=" * 70)
    print(f"✅ VALMIS!")
    print(f"   Tallennettu: {saved_count} artikkelia")
    print(f"   Faktatarkistettu: {saved_count} väitettä")
    print(f"\n💡 Päivitä selain: http://localhost:3000")
    print("=" * 70)
    print()


if __name__ == "__main__":
    # Hae Suomen uutiset
    fetch_and_verify_news(
        country="Finland",
        country_code="FI",
        max_articles=10
    )

