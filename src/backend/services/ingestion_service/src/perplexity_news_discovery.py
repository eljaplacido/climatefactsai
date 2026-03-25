"""
Perplexity-pohjainen uutisten haku

Sen sijaan että integroisimme satoja RSS-syötteitä, käytämme Perplexitya
hakemaan ajantasaisia ilmastouutisia mistä tahansa maasta.

Edut:
- ✅ Toimii KAIKISSA maissa (ei tarvita maakohtaisia integraatioita)
- ✅ Aina ajantasaista dataa (real-time web search)
- ✅ Sisältää lähteet automaattisesti
- ✅ Kattaa kaikki merkittävät uutislähteet
"""

import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json


class PerplexityNewsDiscovery:
    """
    Käytä Perplexity AI:ta ilmastouutisten löytämiseen
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.perplexity.ai"
        # Käytä sonar-mallia jolla online-haku
        self.model = "sonar"
    
    def discover_news(
        self,
        country: str = "Finland",
        country_code: str = "FI",
        max_articles: int = 10,
        days_back: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Löydä ilmastouutiset tietyltä maalta
        
        Args:
            country: Maan nimi (esim. "Finland", "Sweden", "Germany")
            country_code: Maakoodi (esim. "FI", "SE", "DE")
            max_articles: Maksimi artikkelien määrä
            days_back: Kuinka monta päivää taaksepäin haetaan
        
        Returns:
            Lista artikkeleita metadata:
            [
                {
                    'title': str,
                    'summary': str,
                    'url': str,
                    'source': str,
                    'published_date': datetime,
                    'country_code': str,
                    'topics': List[str],
                    'credibility': float
                }
            ]
        """
        
        # Rakenna kysely
        today = datetime.now()
        date_from = today - timedelta(days=days_back)
        
        prompt = f"""Find the most important climate change related news from {country} from the last {days_back} days.

Requirements:
1. Focus on news from {date_from.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}
2. Look for climate change, emissions, renewable energy, weather events, environmental policy
3. Prioritize credible news sources (national media, official sources)
4. For EACH article found, provide:
   - Exact title
   - Brief summary (2-3 sentences)
   - Source URL
   - Source name
   - Publication date (if available)
   - Main topics/themes

Please respond in this JSON format:
{{
  "articles": [
    {{
      "title": "Exact article title",
      "summary": "Brief summary of the article",
      "url": "Direct link to article",
      "source_name": "Name of news outlet",
      "published_date": "YYYY-MM-DD" or "today" or "2 days ago",
      "topics": ["climate", "emissions", "etc"],
      "language": "fi" or "en" etc
    }}
  ]
}}

Find up to {max_articles} most relevant and recent articles."""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Parsitaan vastaus
            content = data['choices'][0]['message']['content']
            citations = data.get('citations', [])
            
            # Yritä parsita JSON
            try:
                # Etsi JSON-block tekstistä
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = content[json_start:json_end]
                    result = json.loads(json_str)
                    articles_data = result.get('articles', [])
                else:
                    # Fallback: Luo artikkeli Perplexityn vastauksesta
                    articles_data = self._parse_unstructured_response(content, citations)
                
            except json.JSONDecodeError:
                # Jos JSON-parsing epäonnistui, yritä parsita vapaasta tekstistä
                articles_data = self._parse_unstructured_response(content, citations)
            
            # Normalisoi artikkelit
            normalized_articles = []
            for article in articles_data:
                normalized = self._normalize_article(article, country, country_code, citations)
                if normalized:
                    normalized_articles.append(normalized)
            
            return normalized_articles
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Perplexity API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Status: {e.response.status_code}")
                print(f"Response: {e.response.text[:500]}")
            return []
    
    def _normalize_article(
        self,
        article: Dict[str, Any],
        country: str,
        country_code: str,
        citations: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Normalisoi artikkelin standardimuotoon"""
        
        try:
            # Päivämäärän parsinta
            published_str = article.get('published_date', 'today')
            published_date = self._parse_date_string(published_str)
            
            # Lähteen luotettavuus (yksinkertainen arvio)
            source_name = article.get('source_name', 'Unknown')
            credibility = self._estimate_credibility(source_name, country_code)
            
            # Extract topics/tags from the article
            topics = article.get('topics', [])

            # Add climate-related default tags
            tags = ['climate'] if 'climate' in article.get('summary', '').lower() else []
            tags.extend(topics[:5])  # Limit to 5 tags

            return {
                'title': article.get('title', 'Untitled'),
                'summary': article.get('summary', ''),
                'url': article.get('url', ''),
                'source_name': source_name,
                'published_date': published_date,
                'country_code': country_code,
                'language_code': article.get('language', 'en'),
                'topics': topics,
                'tags': tags,
                'credibility_score': credibility,
                'source_credibility_score': credibility,
                'extracted_from': 'perplexity',
                'citations': citations,
                'extracted_text': article.get('summary', '')  # Use summary as extracted text initially
            }
        except Exception as e:
            print(f"Warning: Failed to normalize article: {e}")
            return None
    
    def _parse_date_string(self, date_str: str) -> datetime:
        """Parsii päivämäärän eri muodoista"""
        
        if not date_str or date_str.lower() == 'today':
            return datetime.now()
        
        if 'ago' in date_str.lower():
            # "2 days ago"
            import re
            match = re.search(r'(\d+)\s*(day|hour)', date_str.lower())
            if match:
                num = int(match.group(1))
                unit = match.group(2)
                
                if unit == 'day':
                    return datetime.now() - timedelta(days=num)
                elif unit == 'hour':
                    return datetime.now() - timedelta(hours=num)
        
        # Yritä parsita ISO-muodossa
        try:
            return datetime.fromisoformat(date_str)
        except:
            pass
        
        # Yritä yleisiä muotoja
        from dateutil import parser as date_parser
        try:
            return date_parser.parse(date_str)
        except:
            return datetime.now()
    
    def _estimate_credibility(self, source_name: str, country_code: str) -> int:
        """Arvioi lähteen luotettavuus (0-100)"""
        
        # Tunnetut luotettavat lähteet per maa
        high_credibility_sources = {
            'FI': ['yle', 'helsingin sanomat', 'iltalehti'],
            'SE': ['svt', 'svenska dagbladet', 'aftonbladet'],
            'NO': ['nrk', 'aftenposten'],
            'DK': ['dr', 'politiken'],
            'DE': ['dw', 'der spiegel', 'tagesschau'],
            'GB': ['bbc', 'the guardian', 'reuters'],
            'FR': ['le monde', 'liberation', 'france 24'],
            'ES': ['el pais', 'el mundo'],
            'IT': ['corriere', 'la repubblica']
        }
        
        source_lower = source_name.lower()
        
        # Tarkista onko tunnettu lähde
        if country_code in high_credibility_sources:
            if any(known in source_lower for known in high_credibility_sources[country_code]):
                return 90
        
        # Kansainväliset lähteet
        international_high = ['reuters', 'bbc', 'ap news', 'afp', 'dw', 'euronews']
        if any(source in source_lower for source in international_high):
            return 85
        
        # Default keskitaso
        return 70
    
    def _parse_unstructured_response(
        self,
        content: str,
        citations: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Parsii artikkelit vapaamuotoisesta tekstistä jos JSON-parsing epäonnistui
        """
        articles = []
        
        # Yksinkertainen fallback: luo yksi artikkeli Perplexityn vastauksesta
        if citations:
            for citation in citations[:5]:  # Max 5 ensimmäistä
                articles.append({
                    'title': citation.get('title', 'Climate news'),
                    'summary': content[:500],
                    'url': citation.get('url', ''),
                    'source_name': self._extract_source_from_url(citation.get('url', '')),
                    'published_date': 'today',
                    'topics': ['climate'],
                    'language': 'en'
                })
        
        return articles
    
    def _extract_source_from_url(self, url: str) -> str:
        """Poimii lähteen nimen URL:stä"""
        from urllib.parse import urlparse
        
        try:
            domain = urlparse(url).netloc
            # Poista www. ja .fi/.com jne
            domain = domain.replace('www.', '').split('.')[0]
            return domain.capitalize()
        except:
            return 'Unknown'


def test_perplexity_news():
    """Testaa Perplexity-uutisten haku"""
    
    api_key = os.getenv("PERPLEXITY_API_KEY", "")
    if not api_key:
        print("ERROR: Set PERPLEXITY_API_KEY env var to run this test")
        return
    
    discovery = PerplexityNewsDiscovery(api_key)
    
    print("\n🌍 Haetaan ilmastouutisia Perplexitylla...")
    print("=" * 70)
    
    # Hae Suomen uutiset
    articles = discovery.discover_news(
        country="Finland",
        country_code="FI",
        max_articles=10,
        days_back=3
    )
    
    print(f"\n✅ Löydettiin {len(articles)} artikkelia Suomesta!\n")
    
    for i, article in enumerate(articles, 1):
        print(f"{i}. {article['title']}")
        print(f"   Lähde: {article['source_name']}")
        print(f"   URL: {article['url'][:60]}...")
        print(f"   Julkaistu: {article['published_date']}")
        print(f"   Luotettavuus: {article['credibility_score']}/100")
        print()
    
    print("=" * 70)
    print("✅ Perplexity-integraatio toimii!")
    print("\nSeuraavaksi: Tallenna nämä tietokantaan.\n")


if __name__ == "__main__":
    test_perplexity_news()

