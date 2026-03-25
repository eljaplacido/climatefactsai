"""
News Scraper Pool - Web scraping -toteutus

Käyttää Scrapy + Playwright -yhdistelmää:
- RSS-feedit: feedparser
- Staattiset sivut: Scrapy
- Dynaamiset sivut: Playwright
"""

import time
import feedparser
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import re

import requests
from structlog.stdlib import BoundLogger
from langdetect import detect


class NewsScraperPool:
    """
    Uutisscraper-pool
    
    Hallinnoi useita rinnakkaisia scraping-tehtäviä rate limiting -säännöillä.
    """
    
    def __init__(
        self,
        max_concurrent: int = 10,
        rate_limit_delay: float = 2.0,
        user_agent: str = "ClimateNewsBot/1.0",
        respect_robots_txt: bool = True,
        logger: Optional[BoundLogger] = None
    ):
        """
        Alusta scraper pool
        
        Args:
            max_concurrent: Maksimi rinnakkaisia pyyntöjä
            rate_limit_delay: Viive pyyntöjen välillä (sekunteina)
            user_agent: HTTP User-Agent -header
            respect_robots_txt: Kunnioita robots.txt
            logger: Logger
        """
        self.max_concurrent = max_concurrent
        self.rate_limit_delay = rate_limit_delay
        self.user_agent = user_agent
        self.respect_robots_txt = respect_robots_txt
        self.logger = logger
        
        # HTTP session
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fi,en;q=0.9",
        })
        
        # Rate limiting
        self.last_request_time = {}
        
        if self.logger:
            self.logger.info(
                "NewsScraperPool initialized",
                max_concurrent=max_concurrent,
                rate_limit_delay=rate_limit_delay
            )
    
    def scrape_source(
        self,
        source_url: str,
        keywords: Optional[List[str]] = None,
        date_range: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Scannaa yksittäinen uutislähde
        
        Args:
            source_url: Lähde-URL (voi olla RSS-feed tai website)
            keywords: Suodatusavainsanat
            date_range: Päivämääräväli {"from": "2025-01-01", "to": "2025-01-02"}
        
        Returns:
            Lista artikkeli-dictionaryja
        """
        # Tarkista onko RSS-feed
        if self._is_rss_feed(source_url):
            return self._scrape_rss_feed(source_url, keywords, date_range)
        else:
            # Tavallinen web-sivu
            return self._scrape_website(source_url, keywords, date_range)
    
    def _is_rss_feed(self, url: str) -> bool:
        """Tarkista onko URL RSS-feed"""
        return url.endswith(('.rss', '.xml', '.atom')) or 'rss' in url.lower() or 'feed' in url.lower()
    
    def _scrape_rss_feed(
        self,
        feed_url: str,
        keywords: Optional[List[str]] = None,
        date_range: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Scannaa RSS-feed
        
        Args:
            feed_url: RSS-feedin URL
            keywords: Suodatusavainsanat
            date_range: Päivämääräväli
        
        Returns:
            Lista artikkeli-dictionaryja
        """
        if self.logger:
            self.logger.debug(f"Parsing RSS feed: {feed_url}")
        
        try:
            # Rate limiting
            self._apply_rate_limit(feed_url)
            
            # Parsea feed
            feed = feedparser.parse(feed_url)
            
            articles = []
            
            for entry in feed.entries:
                # Tarkista päivämäärä
                if date_range and not self._is_in_date_range(entry, date_range):
                    continue
                
                # Tarkista avainsanat
                if keywords and not self._matches_keywords(entry, keywords):
                    continue
                
                # Hae täysi artikkeli
                article_data = self._fetch_article_content(entry.link)
                
                if article_data:
                    # Täydennä RSS-metadatalla
                    article_data.update({
                        "title": entry.get("title", article_data.get("title", "")),
                        "author": entry.get("author", article_data.get("author", "")),
                        "published_date": self._parse_date(entry.get("published")),
                        "source_name": feed.feed.get("title", "Unknown"),
                        "tags": [tag.term for tag in entry.get("tags", [])]
                    })
                    
                    articles.append(article_data)
            
            if self.logger:
                self.logger.info(
                    f"RSS feed scraped",
                    feed_url=feed_url,
                    total_entries=len(feed.entries),
                    matched_articles=len(articles)
                )
            
            return articles
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to scrape RSS feed: {feed_url}", error=str(e))
            return []
    
    def _scrape_website(
        self,
        website_url: str,
        keywords: Optional[List[str]] = None,
        date_range: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Scannaa tavallinen web-sivu
        
        Tämä on yksinkertainen toteutus. Tuotannossa käytettäisiin
        Scrapy-spideria ja Playwright:ta dynaamisille sivuille.
        
        Args:
            website_url: Web-sivun URL
            keywords: Suodatusavainsanat
            date_range: Päivämääräväli
        
        Returns:
            Lista artikkeli-dictionaryja
        """
        if self.logger:
            self.logger.debug(f"Scraping website: {website_url}")
        
        try:
            # Rate limiting
            self._apply_rate_limit(website_url)
            
            # Hae sivu
            response = self.session.get(website_url, timeout=30)
            response.raise_for_status()
            
            # Parsea HTML
            soup = BeautifulSoup(response.content, 'lxml')
            
            # TODO: Implementoi sivukohtainen parsinta
            # Tämä on placeholder - tuotannossa käytettäisiin
            # sivukohtaisia selektoreja
            
            # Esimerkki: etsi artikkeli-linkkejä
            articles = []
            article_links = soup.find_all('a', href=True, class_=['article', 'news-item'])
            
            for link in article_links[:10]:  # Rajoita 10 artikkeliin
                article_url = self._normalize_url(link['href'], website_url)
                article_data = self._fetch_article_content(article_url)
                
                if article_data:
                    # Tarkista avainsanat
                    if keywords and not self._matches_keywords_dict(article_data, keywords):
                        continue
                    
                    articles.append(article_data)
            
            return articles
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to scrape website: {website_url}", error=str(e))
            return []
    
    def _fetch_article_content(self, article_url: str) -> Optional[Dict[str, Any]]:
        """
        Hae yksittäisen artikkelin sisältö
        
        Args:
            article_url: Artikkelin URL
        
        Returns:
            Artikkeli-dictionary tai None
        """
        try:
            # Rate limiting
            self._apply_rate_limit(article_url)
            
            # Hae artikkeli
            response = self.session.get(article_url, timeout=30)
            response.raise_for_status()
            
            # Parsea HTML
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Ekstraktoi sisältö (yksinkertaistettu)
            # Tuotannossa käytettäisiin newspaper3k tai trafilatura
            title = soup.find('h1')
            title_text = title.get_text(strip=True) if title else ""
            
            # Etsi artikkelin runko
            article_body = soup.find('article') or soup.find('div', class_=['content', 'article-body'])
            
            if article_body:
                # Poista skriptit ja tyylit
                for tag in article_body(['script', 'style', 'nav', 'aside', 'footer']):
                    tag.decompose()
                
                extracted_text = article_body.get_text(separator=' ', strip=True)
            else:
                # Fallback: kaikki kappaleet
                paragraphs = soup.find_all('p')
                extracted_text = ' '.join([p.get_text(strip=True) for p in paragraphs])
            
            # Suodata liian lyhyet artikkelit
            if len(extracted_text) < 200:
                return None

            # Ekstraktoi metadata
            author = self._extract_author(soup)
            published_date = self._extract_published_date(soup)
            language = self._detect_language(extracted_text)

            return {
                "url": article_url,
                "title": title_text,
                "extracted_text": extracted_text,
                "author": author,
                "published_date": published_date.isoformat() if published_date else None,
                "source_name": urlparse(article_url).netloc,
                "language": language,
                "tags": [],
                "source_credibility_score": 50,  # Default
                "processing_time_ms": 0
            }
            
        except Exception as e:
            if self.logger:
                self.logger.debug(f"Failed to fetch article: {article_url}", error=str(e))
            return None
    
    def _apply_rate_limit(self, url: str):
        """
        Sovella rate limiting -viive
        
        Args:
            url: URL (domain käytetään rate limiting -avaimena)
        """
        domain = urlparse(url).netloc
        
        if domain in self.last_request_time:
            elapsed = time.time() - self.last_request_time[domain]
            if elapsed < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - elapsed
                time.sleep(sleep_time)
        
        self.last_request_time[domain] = time.time()
    
    def _is_in_date_range(
        self,
        entry: Any,
        date_range: Dict[str, str]
    ) -> bool:
        """Tarkista onko RSS-entry päivämäärävälin sisällä"""
        try:
            entry_date = self._parse_date(entry.get("published"))
            if not entry_date:
                return True  # Jos ei päivämäärää, hyväksy
            
            from_date = datetime.fromisoformat(date_range.get("from", "2000-01-01"))
            to_date = datetime.fromisoformat(date_range.get("to", "2099-12-31"))
            
            return from_date <= entry_date <= to_date
        except:
            return True
    
    def _matches_keywords(self, entry: Any, keywords: List[str]) -> bool:
        """Tarkista sisältääkö RSS-entry avainsanoja"""
        text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
        return any(keyword.lower() in text for keyword in keywords)
    
    def _matches_keywords_dict(self, article: Dict[str, Any], keywords: List[str]) -> bool:
        """Tarkista sisältääkö artikkeli avainsanoja"""
        text = f"{article.get('title', '')} {article.get('extracted_text', '')}".lower()
        return any(keyword.lower() in text for keyword in keywords)
    
    def _parse_date(self, date_string: Optional[str]) -> Optional[datetime]:
        """Parsea päivämäärästring"""
        if not date_string:
            return None
        
        try:
            # feedparser palauttaa struct_time
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_string)
        except:
            return None
    
    def _normalize_url(self, url: str, base_url: str) -> str:
        """Normalisoi suhteellinen URL absoluuttiseksi"""
        from urllib.parse import urljoin
        return urljoin(base_url, url)

    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Ekstraktoi kirjoittajan nimi artikkelista

        Args:
            soup: BeautifulSoup-objekti artikkelista

        Returns:
            Kirjoittajan nimi tai None
        """
        # Yritä löytää kirjoittaja metatageista
        author_meta = soup.find('meta', attrs={'name': 'author'}) or \
                     soup.find('meta', attrs={'property': 'article:author'}) or \
                     soup.find('meta', attrs={'name': 'byl'})

        if author_meta and author_meta.get('content'):
            return author_meta['content'].strip()

        # Yritä löytää author-luokan perusteella
        author_elem = soup.find(class_=re.compile(r'author|byline|writer', re.I)) or \
                     soup.find('span', attrs={'itemprop': 'author'}) or \
                     soup.find('a', attrs={'rel': 'author'})

        if author_elem:
            return author_elem.get_text(strip=True)

        return None

    def _extract_published_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """
        Ekstraktoi julkaisupäivämäärä artikkelista

        Args:
            soup: BeautifulSoup-objekti artikkelista

        Returns:
            Julkaisupäivämäärä datetime-objektina tai None
        """
        # Yritä löytää päivämäärä metatageista
        date_meta = soup.find('meta', attrs={'property': 'article:published_time'}) or \
                   soup.find('meta', attrs={'name': 'publishdate'}) or \
                   soup.find('meta', attrs={'name': 'DC.date.issued'}) or \
                   soup.find('meta', attrs={'itemprop': 'datePublished'})

        if date_meta and date_meta.get('content'):
            try:
                return datetime.fromisoformat(date_meta['content'].replace('Z', '+00:00'))
            except:
                pass

        # Yritä löytää time-elementistä
        time_elem = soup.find('time', attrs={'datetime': True}) or \
                   soup.find('time', attrs={'pubdate': True})

        if time_elem and time_elem.get('datetime'):
            try:
                return datetime.fromisoformat(time_elem['datetime'].replace('Z', '+00:00'))
            except:
                pass

        # Yritä löytää date-luokan perusteella
        date_elem = soup.find(class_=re.compile(r'date|published|time', re.I))

        if date_elem:
            date_text = date_elem.get_text(strip=True)
            return self._parse_date_text(date_text)

        return None

    def _parse_date_text(self, date_text: str) -> Optional[datetime]:
        """
        Parsea päivämäärä tekstistä

        Args:
            date_text: Päivämäärästring

        Returns:
            datetime-objekti tai None
        """
        try:
            # Yritä erilaisia formaatteja
            from dateutil import parser
            return parser.parse(date_text, fuzzy=True)
        except:
            return None

    def _detect_language(self, text: str) -> str:
        """
        Tunnista tekstin kieli

        Args:
            text: Teksti

        Returns:
            Kielikoodi (esim. 'fi', 'en', 'sv')
        """
        try:
            # Käytä vain ensimmäisiä 1000 merkkiä tunnistukseen
            sample = text[:1000] if len(text) > 1000 else text
            return detect(sample)
        except:
            return "fi"  # Fallback suomeksi

    def close(self):
        """Sulje scraper pool"""
        self.session.close()
        if self.logger:
            self.logger.info("NewsScraperPool closed")


