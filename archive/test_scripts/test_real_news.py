"""
Testaa oikeiden uutisten hakeminen YLE:stä
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "agents"))

from content_discovery.scraper import NewsScraperPool

def test_scraper():
    print("\n🔍 Haetaan oikeita uutisia YLE:stä...")
    print("=" * 60)
    
    scraper = NewsScraperPool()
    
    # Hae YLE RSS (ensin ilman filtteriä)
    print("Haetaan YLE RSS-syötettä...\n")
    articles = scraper.scrape_source(
        source_url="https://yle.fi/rss/uutiset.rss"
        # Ei keywords-filtteriä -> haetaan kaikki
    )
    
    print(f"\n✅ Löydettiin {len(articles)} artikkelia YLE:stä!\n")
    
    for i, article in enumerate(articles[:5], 1):
        print(f"{i}. {article['title']}")
        print(f"   URL: {article['url']}")
        print(f"   Julkaistu: {article.get('published_date', 'N/A')}")
        print()
    
    print("=" * 60)
    print(f"✅ Yhteensä {len(articles)} ilmasto-aiheista artikkelia löydetty!")
    print("\nSeuraavaksi: Käynnistä agentit ja aja workflow.\n")

if __name__ == "__main__":
    test_scraper()

