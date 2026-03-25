# 🇪🇺 MVP: Eurooppa-fokus ilmastoviestintäalusta

## 🎯 MVP Scope (Suomi/EU fokus)

### ✅ Toteutetaan HETI (2-3 viikkoa):

#### 1. **Maantieteellinen laajentuminen: Eurooppa**
- 🇫🇮 Suomi (nykyinen)
- 🇸🇪 Ruotsi
- 🇳🇴 Norja
- 🇩🇰 Tanska
- 🇩🇪 Saksa
- 🇬🇧 Iso-Britannia
- 🇫🇷 Ranska
- 🇪🇸 Espanja
- 🇮🇹 Italia
- 🇳🇱 Alankomaat
- 🇵🇱 Puola
- + muut EU-maat (yhteensä ~30 maata)

#### 2. **Uutislähteet per maa (ilmaiset RSS-syötteet)**

**Suomi:**
- YLE (yle.fi/rss) ✅ Käytössä
- Helsingin Sanomat (hs.fi/rss)
- MTV Uutiset (mtvuutiset.fi/rss)

**Ruotsi:**
- SVT (svt.se/rss)
- Svenska Dagbladet (svd.se/rss)
- Aftonbladet (aftonbladet.se/rss)

**Norja:**
- NRK (nrk.no/rss)
- Aftenposten (aftenposten.no/rss)

**Saksa:**
- Deutsche Welle (dw.com/rss)
- Der Spiegel (spiegel.de/rss)
- Tagesschau (tagesschau.de/rss)

**Iso-Britannia:**
- BBC (bbc.com/rss)
- The Guardian (theguardian.com/rss)
- Reuters UK (reuters.com/rss)

...jne per maa

#### 3. **Käännösintegraatio (ilmainen/halpa)**

**Vaihtoehto A: Google Translate API (Free tier)**
- ✅ 500,000 merkkiä/kk ILMAISEKSI
- €20/1M merkkiä sen jälkeen
- Hyvä laatu, nopea

**Vaihtoehto B: DeepL Free API**
- ✅ 500,000 merkkiä/kk ILMAISEKSI
- Parempi laatu kuin Google
- Erityisen hyvä EU-kielille

**Käytämme:** DeepL Free (parempi EU-kielille)

#### 4. **UI/UX päivitykset**

**Etusivu:**
```tsx
┌─────────────────────────────────────────────────┐
│  🌍 Climate News Europe                         │
│                                                 │
│  Valitse maa:                                   │
│  [🇫🇮 Suomi ▾] [Kaikki EU-maat]                │
│                                                 │
│  📊 Tilastot:                                   │
│  - Suomi: 42 artikkelia                         │
│  - Ruotsi: 38 artikkelia                        │
│  - Norja: 24 artikkelia                         │
│                                                 │
│  Suodata:                                       │
│  [📰 YLE] [✅ Korkea] [🇫🇮 Suomi]              │
│                                                 │
│  Artikkelit:                                    │
│  📰 [Artikkeli 1 - YLE - Helsinki]             │
│  📰 [Artikkeli 2 - SVT - Stockholm]            │
│  📰 [Artikkeli 3 - NRK - Oslo]                 │
└─────────────────────────────────────────────────┘
```

**Uusi "Karttanäkymä" sivu:**
```
/map → Interaktiivinen Euroopan kartta
Klikkaa maata → Näe sen uutiset
```

#### 5. **Faktatarkistus (olemassa olevat API:t)**

✅ **Käytössäsi olevat:**
- Claude 3.5 Sonnet (Anthropic API key)
- GPT-4o (OpenAI API key)

✅ **Ilmaiset/halvat:**
- NASA FIRMS API (ilmainen) - Palot, lämpötilat
- NOAA Climate Data API (ilmainen) - Säätila
- ClimateCheck API (jos API key käytössä)

**Ei toteuteta vielä:**
- ❌ Video-tuotanto
- ❌ Sosiaalisen median automatisointi
- ❌ Maksullinen premium-taso

---

## 🗄️ Tietokannan päivitykset

### 1. Euroopan maat -taulu

```sql
-- Lisätään countries-taulu EU-maille
CREATE TABLE IF NOT EXISTS countries (
    country_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_code CHAR(2) UNIQUE NOT NULL, -- ISO 3166-1 alpha-2
    country_name VARCHAR(100) NOT NULL,
    country_name_native VARCHAR(100), -- Maan nimi paikalliskielellä
    continent VARCHAR(50) DEFAULT 'Europe',
    is_eu_member BOOLEAN DEFAULT FALSE,
    language_code CHAR(2) NOT NULL, -- ISO 639-1
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    news_sources_count INT DEFAULT 0,
    articles_count INT DEFAULT 0,
    flag_emoji VARCHAR(10), -- 🇫🇮
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexit
CREATE INDEX idx_countries_code ON countries(country_code);
CREATE INDEX idx_countries_enabled ON countries(enabled);
CREATE INDEX idx_countries_eu ON countries(is_eu_member);

-- Lisää EU-maat
INSERT INTO countries (country_code, country_name, country_name_native, is_eu_member, language_code, latitude, longitude, flag_emoji) VALUES
('FI', 'Finland', 'Suomi', TRUE, 'fi', 64.0, 26.0, '🇫🇮'),
('SE', 'Sweden', 'Sverige', TRUE, 'sv', 62.0, 15.0, '🇸🇪'),
('NO', 'Norway', 'Norge', FALSE, 'no', 60.0, 8.0, '🇳🇴'),
('DK', 'Denmark', 'Danmark', TRUE, 'da', 56.0, 10.0, '🇩🇰'),
('DE', 'Germany', 'Deutschland', TRUE, 'de', 51.0, 9.0, '🇩🇪'),
('GB', 'United Kingdom', 'United Kingdom', FALSE, 'en', 54.0, -2.0, '🇬🇧'),
('FR', 'France', 'France', TRUE, 'fr', 46.0, 2.0, '🇫🇷'),
('ES', 'Spain', 'España', TRUE, 'es', 40.0, -4.0, '🇪🇸'),
('IT', 'Italy', 'Italia', TRUE, 'it', 42.8, 12.8, '🇮🇹'),
('NL', 'Netherlands', 'Nederland', TRUE, 'nl', 52.3, 5.7, '🇳🇱'),
('PL', 'Poland', 'Polska', TRUE, 'pl', 52.0, 20.0, '🇵🇱'),
('BE', 'Belgium', 'België', TRUE, 'nl', 50.8, 4.3, '🇧🇪'),
('AT', 'Austria', 'Österreich', TRUE, 'de', 47.5, 14.5, '🇦🇹'),
('PT', 'Portugal', 'Portugal', TRUE, 'pt', 39.5, -8.0, '🇵🇹'),
('GR', 'Greece', 'Ελλάδα', TRUE, 'el', 39.0, 22.0, '🇬🇷'),
('CZ', 'Czech Republic', 'Česko', TRUE, 'cs', 49.8, 15.5, '🇨🇿'),
('HU', 'Hungary', 'Magyarország', TRUE, 'hu', 47.0, 20.0, '🇭🇺'),
('RO', 'Romania', 'România', TRUE, 'ro', 46.0, 25.0, '🇷🇴'),
('IE', 'Ireland', 'Éire', TRUE, 'ga', 53.0, -8.0, '🇮🇪'),
('SK', 'Slovakia', 'Slovensko', TRUE, 'sk', 48.7, 19.7, '🇸🇰')
ON CONFLICT (country_code) DO NOTHING;
```

### 2. Päivitä articles-taulu

```sql
-- Lisää country_code artikkeleihin
ALTER TABLE articles ADD COLUMN IF NOT EXISTS country_code CHAR(2) REFERENCES countries(country_code);
CREATE INDEX IF NOT EXISTS idx_articles_country ON articles(country_code);

-- Päivitä olemassa olevat artikkelit
UPDATE articles SET country_code = 'FI' WHERE country_code IS NULL;
```

### 3. Käännökset-taulu

```sql
-- Artikkelien käännökset
CREATE TABLE IF NOT EXISTS article_translations (
    translation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID REFERENCES articles(article_id) ON DELETE CASCADE,
    from_language CHAR(2) NOT NULL, -- Alkuperäinen kieli
    to_language CHAR(2) NOT NULL, -- Kohde kieli
    translated_title TEXT,
    translated_summary TEXT,
    translated_content TEXT,
    translation_service VARCHAR(50) DEFAULT 'deepl', -- 'deepl', 'google', 'manual'
    translation_confidence DECIMAL(4, 3), -- 0.000-1.000
    translated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(article_id, to_language)
);

CREATE INDEX idx_translations_article ON article_translations(article_id);
CREATE INDEX idx_translations_language ON article_translations(to_language);
```

---

## 🔧 Backend API päivitykset

### 1. Uudet endpointit

```python
# api/main.py

@app.get("/api/countries")
async def get_countries():
    """Hae kaikki EU-maat"""
    query = """
        SELECT 
            country_code,
            country_name,
            country_name_native,
            flag_emoji,
            articles_count,
            is_eu_member
        FROM countries
        WHERE enabled = TRUE
        ORDER BY country_name
    """
    return db.execute_query(query)

@app.get("/api/countries/{country_code}/articles")
async def get_country_articles(
    country_code: str,
    limit: int = 20,
    offset: int = 0
):
    """Hae maan artikkelit"""
    query = """
        SELECT 
            a.*,
            COUNT(DISTINCT fc.fact_check_id) as fact_check_count
        FROM articles a
        LEFT JOIN claims c ON a.article_id = c.article_id
        LEFT JOIN fact_checks fc ON c.claim_id = fc.claim_id
        WHERE a.country_code = :country_code
        GROUP BY a.article_id
        ORDER BY a.published_date DESC
        LIMIT :limit OFFSET :offset
    """
    return db.execute_query(query, {
        "country_code": country_code.upper(),
        "limit": limit,
        "offset": offset
    })

@app.get("/api/articles")
async def get_articles(
    country: Optional[str] = None,  # UUSI!
    source: Optional[str] = None,
    credibility: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
):
    """Hae artikkelit suodattimilla"""
    query = """
        SELECT 
            a.*,
            c.country_name,
            c.flag_emoji,
            COUNT(DISTINCT fc.fact_check_id) as fact_check_count
        FROM articles a
        LEFT JOIN countries c ON a.country_code = c.country_code
        LEFT JOIN claims cl ON a.article_id = cl.article_id
        LEFT JOIN fact_checks fc ON cl.claim_id = fc.claim_id
        WHERE 1=1
    """
    
    params = {}
    
    if country:
        query += " AND a.country_code = :country"
        params["country"] = country.upper()
    
    if source:
        query += " AND a.source_name = :source"
        params["source"] = source
    
    if credibility:
        # HIGH: > 80, MEDIUM: 50-80, LOW: < 50
        if credibility == "HIGH":
            query += " AND a.source_credibility_score > 80"
        elif credibility == "MEDIUM":
            query += " AND a.source_credibility_score BETWEEN 50 AND 80"
        elif credibility == "LOW":
            query += " AND a.source_credibility_score < 50"
    
    query += """
        GROUP BY a.article_id, c.country_name, c.flag_emoji
        ORDER BY a.published_date DESC
        LIMIT :limit OFFSET :offset
    """
    
    params["limit"] = limit
    params["offset"] = offset
    
    return db.execute_query(query, params)

@app.post("/api/admin/translate-article/{article_id}")
async def translate_article(
    article_id: str,
    target_language: str = "en"
):
    """Käännä artikkeli toiselle kielelle"""
    # Käytetään DeepL API:a
    from services.translation import translate_with_deepl
    
    article = db.get_article(article_id)
    
    translated = translate_with_deepl(
        text=article['content'],
        from_lang=article['language_code'],
        to_lang=target_language
    )
    
    # Tallenna käännös
    db.save_translation(article_id, target_language, translated)
    
    return {"status": "success", "translation_id": translated['id']}
```

### 2. Translation Service (DeepL)

```python
# api/services/translation.py

import requests
from typing import Dict, Optional
import os

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"

def translate_with_deepl(
    text: str,
    from_lang: str,
    to_lang: str
) -> Dict:
    """
    Käännä teksti DeepL API:lla
    
    Args:
        text: Käännettävä teksti
        from_lang: Lähdekieli (fi, sv, en, etc.)
        to_lang: Kohde kieli
    
    Returns:
        {
            'translated_text': str,
            'detected_source_language': str,
            'confidence': float
        }
    """
    
    if not DEEPL_API_KEY:
        # Fallback: Palauta alkuperäinen teksti
        return {
            'translated_text': text,
            'detected_source_language': from_lang,
            'confidence': 0.0
        }
    
    response = requests.post(
        DEEPL_API_URL,
        data={
            'auth_key': DEEPL_API_KEY,
            'text': text,
            'source_lang': from_lang.upper(),
            'target_lang': to_lang.upper()
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        return {
            'translated_text': data['translations'][0]['text'],
            'detected_source_language': data['translations'][0].get('detected_source_language', from_lang),
            'confidence': 1.0  # DeepL ei palauta confidence scorea
        }
    else:
        raise Exception(f"DeepL API error: {response.status_code}")
```

---

## 🎨 Frontend päivitykset

### 1. Maavalitsin-komponentti

```tsx
// frontend/src/components/CountrySelector.tsx

import { useState, useEffect } from 'react';
import { Globe } from 'lucide-react';
import { api } from '../services/api';

interface Country {
  country_code: string;
  country_name: string;
  country_name_native: string;
  flag_emoji: string;
  articles_count: number;
  is_eu_member: boolean;
}

function CountrySelector({ 
  value, 
  onChange 
}: { 
  value: string | null; 
  onChange: (country: string | null) => void 
}) {
  const [countries, setCountries] = useState<Country[]>([]);

  useEffect(() => {
    loadCountries();
  }, []);

  const loadCountries = async () => {
    const data = await api.getCountries();
    setCountries(data);
  };

  return (
    <div className="relative">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        <Globe className="inline h-4 w-4 mr-1" />
        Valitse maa
      </label>
      
      <select
        value={value || ''}
        onChange={(e) => onChange(e.target.value || null)}
        className="w-full border border-gray-300 rounded-lg px-4 py-2.5 bg-white focus:ring-2 focus:ring-climate-green-500 focus:border-transparent"
      >
        <option value="">🇪🇺 Kaikki EU-maat</option>
        
        {countries
          .filter(c => c.is_eu_member)
          .map(country => (
            <option key={country.country_code} value={country.country_code}>
              {country.flag_emoji} {country.country_name} ({country.articles_count})
            </option>
          ))
        }
        
        <optgroup label="Muut Euroopan maat">
          {countries
            .filter(c => !c.is_eu_member)
            .map(country => (
              <option key={country.country_code} value={country.country_code}>
                {country.flag_emoji} {country.country_name} ({country.articles_count})
              </option>
            ))
          }
        </optgroup>
      </select>
      
      {value && (
        <button
          onClick={() => onChange(null)}
          className="absolute right-10 top-10 text-gray-400 hover:text-gray-600"
        >
          ✕
        </button>
      )}
    </div>
  );
}

export default CountrySelector;
```

### 2. Päivitetty HomePage

```tsx
// frontend/src/pages/HomePage.tsx

import { useState, useEffect } from 'react';
import CountrySelector from '../components/CountrySelector';
import ArticleCard from '../components/ArticleCard';
// ... muut importit

function HomePage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [credibilityFilter, setCredibilityFilter] = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL');

  useEffect(() => {
    loadArticles();
  }, [selectedCountry, selectedSource, credibilityFilter]);

  const loadArticles = async () => {
    const data = await api.getArticles({
      country: selectedCountry,
      source: selectedSource,
      credibility: credibilityFilter === 'ALL' ? undefined : credibilityFilter
    });
    setArticles(data);
  };

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="bg-gradient-to-r from-climate-green-600 to-climate-blue-600 rounded-2xl p-8 text-white">
        <h1 className="text-4xl font-bold mb-4">
          🇪🇺 Climate News Europe
        </h1>
        <p className="text-lg text-white/90">
          Faktatarkistettuja ilmastouutisia ympäri Eurooppaa. 
          Valitse maa ja näe mitä siellä tapahtuu.
        </p>
      </div>

      {/* Suodattimet */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Maavalitsin */}
          <CountrySelector 
            value={selectedCountry} 
            onChange={setSelectedCountry} 
          />

          {/* Lähdesuodatin */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              📰 Uutislähde
            </label>
            <select 
              value={selectedSource || ''} 
              onChange={(e) => setSelectedSource(e.target.value || null)}
              className="w-full border rounded-lg px-4 py-2"
            >
              <option value="">Kaikki lähteet</option>
              <option value="YLE">YLE (Suomi)</option>
              <option value="SVT">SVT (Ruotsi)</option>
              <option value="NRK">NRK (Norja)</option>
              <option value="BBC">BBC (UK)</option>
              {/* ... lisää lähteitä */}
            </select>
          </div>

          {/* Luotettavuus */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              ✅ Luotettavuus
            </label>
            <select 
              value={credibilityFilter} 
              onChange={(e) => setCredibilityFilter(e.target.value as any)}
              className="w-full border rounded-lg px-4 py-2"
            >
              <option value="ALL">Kaikki</option>
              <option value="HIGH">Korkea (&gt;80%)</option>
              <option value="MEDIUM">Keskitaso (50-80%)</option>
              <option value="LOW">Matala (&lt;50%)</option>
            </select>
          </div>
        </div>

        {/* Valitut suodattimet */}
        {(selectedCountry || selectedSource) && (
          <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t">
            {selectedCountry && (
              <span className="inline-flex items-center px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                {/* Haetaan country emoji */}
                {selectedCountry}
                <button onClick={() => setSelectedCountry(null)} className="ml-2">✕</button>
              </span>
            )}
            {selectedSource && (
              <span className="inline-flex items-center px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">
                📰 {selectedSource}
                <button onClick={() => setSelectedSource(null)} className="ml-2">✕</button>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Artikkelit */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {articles.map((article) => (
          <ArticleCard key={article.article_id} article={article} />
        ))}
      </div>
    </div>
  );
}

export default HomePage;
```

---

## 📊 Roadmap: MVP → Visio

### ✅ Phase 1: Europa MVP (Nyt - 3 viikkoa)
- [x] Tietokanta: EU-maat
- [ ] Frontend: Maavalitsin
- [ ] API: Country-suodatin
- [ ] Content Discovery: EU RSS-syötteet
- [ ] Käännökset: DeepL Free tier
- [ ] Testaus: 5-10 EU-maata

**Kustannus:** €0/kk (ilmaiset tierit)  
**Tulos:** 10-20 EU-maata, 100+ artikkelia

### 🔄 Phase 2: Karttanäkymä (3-4 viikkoa)
- [ ] Leaflet/Mapbox integraatio
- [ ] Interaktiivinen Euroopan kartta
- [ ] Hover: Näytä artikkelimäärä
- [ ] Click: Suodata maan mukaan

**Kustannus:** €0/kk (Leaflet ilmainen)  
**Tulos:** Visuaalisesti näyttävä UI

### 🌍 Phase 3: Globaali (2-3 kuukautta)
- [ ] Lisää maat: Amerikka, Aasia, Afrikka
- [ ] 100+ maata, 1000+ uutislähdettä
- [ ] Parannetut käännökset

**Kustannus:** €100-500/kk  
**Tulos:** Globaali kattavuus

### 🎥 Phase 4: Video-tuotanto (3-4 kuukautta)
- [ ] Video pipeline (Claude → TTS → Render)
- [ ] Lataa video -toiminto
- [ ] Video-galeria

**Kustannus:** €500-1000/kk  
**Tulos:** Automaattiset videot

### 📱 Phase 5: Social Media (4-6 kuukautta)
- [ ] TikTok/Instagram/YouTube API
- [ ] Automaattinen julkaisu
- [ ] Analytics

**Kustannus:** €1000-2000/kk  
**Tulos:** Täysi automatisointi

---

## 💰 Kustannusarvio MVP (3kk)

| Komponentti | Kustannus/kk | Huomiot |
|-------------|--------------|---------|
| **DeepL Free** | €0 | 500k merkkiä/kk |
| **Anthropic Claude** | €50-100 | Jos käytössä |
| **OpenAI GPT-4** | €50-100 | Jos käytössä |
| **Vercel/Netlify** | €0 | Ilmainen frontend-hosting |
| **Railway/Render** | €0-20 | Backend hosting |
| **PostgreSQL (Supabase)** | €0-25 | 500MB ilmainen |
| **Domain** | €15/vuosi | .eu tai .com |
| **Yhteensä** | **€100-250/kk** | MVP-vaiheessa |

**Jos omat API-avaimet:** ~€50/kk

---

## 🚀 Next Steps (Aloitetaan HETI)

### 1. Tietokanta (30 min)
```bash
# Aja SQL-skriptit
docker exec -it climatenews-postgres psql -U postgres -d climatenews

# Kopioi countries-taulu SQL yllä
```

### 2. Backend API (2h)
- Lisää `/api/countries` endpoint
- Päivitä `/api/articles` ottamaan `country` parametri
- Lisää DeepL translation service

### 3. Frontend (3h)
- Luo CountrySelector-komponentti
- Päivitä HomePage
- Testaa suodattimet

### 4. Content Discovery (4h)
- Lisää EU RSS-syötteet
- Päivitä scraper tunnistamaan maa

**Yhteensä:** ~10h työtä = 1-2 työpäivää

---

## ✅ Checklist

- [ ] Luo `countries`-taulu tietokantaan
- [ ] Lisää EU-maiden data
- [ ] Päivitä API: `/api/countries`
- [ ] Päivitä API: `/api/articles?country=FI`
- [ ] Luo `CountrySelector` komponentti
- [ ] Päivitä `HomePage` käyttämään maavalitsinta
- [ ] Lisää DeepL API key `.env`:iin
- [ ] Luo `translation.py` service
- [ ] Testaa: Valitse Ruotsi → Näe ruotsalaiset uutiset
- [ ] Deploy päivitykset

**Aloitetaanko heti?** 🚀

