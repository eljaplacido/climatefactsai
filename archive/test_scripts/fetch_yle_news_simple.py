"""
Yksinkertainen YLE-uutisten hakuohjelma
Tallentaa suoraan tietokantaan ilman monimutkaista pipeline:a
"""
import sys
from pathlib import Path
from datetime import datetime
import feedparser

sys.path.insert(0, str(Path(__file__).parent / "agents"))

from shared.database import get_postgres

def fetch_and_save_yle_news():
    """Hae YLE:n uutiset ja tallenna tietokantaan"""
    
    print("\n🔍 Haetaan YLE-uutisia...")
    print("=" * 70)
    
    # Parsea YLE RSS
    feed = feedparser.parse("https://yle.fi/rss/uutiset.rss")
    
    print(f"\n✅ RSS-syöte haettu: {feed.feed.get('title', 'YLE')}")
    print(f"   Uutisia yhteensä: {len(feed.entries)}\n")
    
    # Suodata ilmastoaiheisia
    climate_keywords = [
        'ilmasto', 'climate', 'päästö', 'emission', 'hiili', 'carbon',
        'energia', 'energy', 'sää', 'weather', 'lämpötila', 'temperature',
        'luonto', 'nature', 'ympäristö', 'environment'
    ]
    
    climate_articles = []
    
    for entry in feed.entries[:50]:  # Tarkista 50 uusinta
        title_lower = entry.get('title', '').lower()
        summary_lower = entry.get('summary', '').lower()
        
        # Tarkista löytyykö avainsana
        if any(keyword in title_lower or keyword in summary_lower for keyword in climate_keywords):
            climate_articles.append(entry)
    
    print(f"🌍 Ilmastoaiheisia uutisia: {len(climate_articles)}\n")
    
    # Tallenna tietokantaan
    db = get_postgres()
    saved_count = 0
    
    for i, entry in enumerate(climate_articles, 1):
        title = entry.get('title', 'Untitled')
        url = entry.get('link', '')
        summary = entry.get('summary', '')
        
        # Yritä hakea julkaisupäivä
        published = entry.get('published_parsed')
        if published:
            published_date = datetime(*published[:6])
        else:
            published_date = datetime.now()
        
        print(f"{i}. {title[:65]}...")
        
        # Tallenna tietokantaan
        query = """
            INSERT INTO articles (
                title, url, source_name, extracted_text, 
                language_code, published_date, country_code,
                source_credibility_score
            )
            VALUES (
                :title, :url, :source, :content,
                :lang, :published, :country,
                :credibility
            )
            ON CONFLICT (url) DO NOTHING
            RETURNING article_id
        """
        
        try:
            result = db.execute_query(query, {
                "title": title,
                "url": url,
                "source": "YLE Uutiset",
                "content": summary,
                "lang": "fi",
                "published": published_date,
                "country": "FI",
                "credibility": 95  # YLE on luotettava lähde
            })
            
            if result:
                saved_count += 1
                print(f"   ✅ Tallennettu (ID: {result[0]['article_id']})")
            else:
                print(f"   ⏩ Ohitettu (jo tietokannassa)")
                
        except Exception as e:
            print(f"   ❌ Virhe: {str(e)[:50]}")
    
    print("\n" + "=" * 70)
    print(f"✅ Valmis! Tallennettu {saved_count} uutta artikkelia tietokantaan.")
    print(f"   Yhteensä {saved_count + (len(climate_articles) - saved_count)} ilmastoaiheista uutista.")
    print("\n💡 Päivitä selain nähdäksesi uutiset: http://localhost:3000\n")
    
    db.close()


if __name__ == "__main__":
    fetch_and_save_yle_news()

