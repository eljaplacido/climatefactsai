# 🌍 Visio: Globaali ilmastoviestintäalusta

## 🎯 Suuri kuva

### Nykyinen toteutus (MVP):
> ❌ "Suomen ilmastouutiset - Faktatarkistettuja uutisia Suomesta"

### Todellinen visio:
> ✅ **"Globaali ilmastoviestintäalusta - Valitse mikä tahansa maa/maanosa, saat faktatarkistettuja uutisia + automaattisesti tuotetut videot jaettavaksi TikTokiin, Instagramiin ja YouTube Shortsiin"**

---

## 🚀 Käyttäjän matka (User Journey)

### Vaihe 1: Maailmanlaajuinen uutisvalinta
```
Käyttäjä tulee sivulle
    ↓
Näkee maailmankartan tai maa/maanosa-valikun
    ↓
Valitsee: "Näytä ilmastouutiset Thaimaasta"
    ↓
Järjestelmä:
  - Skannaa thaimaalaisia uutislähteitä
  - Kääntää artikkelit englanniksi/suomeksi
  - Faktatarkistaa väitteet globaalilla datalla
  - Luo yhteenvedon
  - Tuottaa videon (TikTok-muoto)
    ↓
Käyttäjä näkee:
  📰 Artikkelit Thaimaan ilmastouutisista
  🎥 Valmis 60s video, voi jakaa heti
```

### Vaihe 2: Sisällön jakaminen
```
Käyttäjä löytää kiinnostavan uutisen
    ↓
Klikkaa "📹 Luo video"
    ↓
AI generoi 15-60s videon:
  - Tekstistä puhetta (text-to-speech)
  - B-roll -videoleikkeitä
  - Faktatarkistus-grafiikat
    ↓
Käyttäjä:
  ✅ Lataa videon
  ✅ Jakaa suoraan TikTokiin
  ✅ Julkaisee Instagram Reelsiin
  ✅ Lähettää YouTube Shortsiin
```

### Vaihe 3: Automatisoitu julkaisu (tulevaisuus)
```
Käyttäjä yhdistää sosiaalisen median tilit
    ↓
Asettaa: "Julkaise automaattisesti 1 video/päivä Brasilian ilmastouutisista"
    ↓
Järjestelmä:
  - Kerää uutisia
  - Luo videot
  - Julkaisee aikataulun mukaan
  - Optimoi julkaisuajat (paras katselija-aika)
```

---

## 🌐 Tekninen arkkitehtuuri: Globaali skaala

### Nykyinen (Suomi-keskeinen):
```
YLE + HS → PostgreSQL → React UI
```

### Uusi (Globaali):
```
┌─────────────────────────────────────────────────────┐
│         MULTI-LANGUAGE NEWS SOURCES                 │
│  🇫🇮 Finland: YLE, HS                                │
│  🇹🇭 Thailand: Bangkok Post, The Nation             │
│  🇧🇷 Brazil: Folha, O Globo                         │
│  🇺🇸 USA: NYT, WashPost                             │
│  🇮🇳 India: Times of India, Hindu                   │
│  + 150+ muuta maata                                 │
└────────────────┬────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────┐
│       TRANSLATION LAYER (DeepL/Google Translate)    │
│  Thai → English → Finnish/Swedish/Any language      │
└────────────────┬────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────┐
│         FACT-CHECKING (Global Data)                 │
│  • ClimateCheck (global coverage)                   │
│  • NASA FIRMS (fire data)                           │
│  • NOAA (weather/climate)                           │
│  • UN IPCC reports                                  │
│  • World Bank data                                  │
└────────────────┬────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────┐
│          VIDEO PRODUCTION PIPELINE                  │
│  1. Text → Script (Claude)                          │
│  2. Script → Audio (ElevenLabs/Azure TTS)           │
│  3. B-roll → Stock footage (Pexels API)             │
│  4. Captions → Auto-generate + translate            │
│  5. Render → FFmpeg/Remotion                        │
│  Format: 9:16 (vertical), 15-60s                    │
└────────────────┬────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────┐
│       SOCIAL MEDIA DISTRIBUTION API                 │
│  • TikTok API (video upload)                        │
│  • Instagram Graph API (Reels)                      │
│  • YouTube Data API v3 (Shorts)                     │
│  • Twitter/X API (video posts)                      │
│  • LinkedIn API (video posts)                       │
└─────────────────────────────────────────────────────┘
```

---

## 🗺️ UI/UX: Globaali sijaintivalinta

### Option 1: Interaktiivinen maailmankartta (suositeltu)

```
┌────────────────────────────────────────────────────┐
│  🌍 CLIMATE NEWS WORLD                             │
│                                                    │
│     [🗺️ Interactive World Map]                     │
│                                                    │
│     Klikkaa maata nähdäksesi sen ilmastouutiset   │
│                                                    │
│  Currently viewing: 🇫🇮 Finland                    │
│  Switch to: [Country dropdown ▾]                  │
│                                                    │
│  Popular regions:                                  │
│  🌏 Asia-Pacific  🌍 Europe  🌎 Americas          │
│  🌍 Africa        🌏 Middle East                   │
└────────────────────────────────────────────────────┘
```

**Teknologia:**
- React + Leaflet / Mapbox
- GeoJSON country polygons
- Hover: Näytä artikkelimäärä
- Click: Suodata uutiset kyseisestä maasta

### Option 2: Hierarkkinen valinta

```
Manner → Maa → Alue

1. Valitse manner:
   [🌏 Aasia] [🌍 Eurooppa] [🌎 Amerikka] [🌍 Afrikka] [🌏 Oseania]

2. Valitse maa (Aasia):
   [🇹🇭 Thaimaa] [🇮🇳 Intia] [🇨🇳 Kiina] [🇯🇵 Japani] [+ 40 muuta]

3. Valitse alue (Thaimaa):
   [📍 Bangkok] [📍 Phuket] [📍 Chiang Mai] [Kaikki]

→ Näytä 42 artikkelia: Thaimaa, Bangkok
```

---

## 🎥 Video Production Pipeline

### Input:
```json
{
  "article_id": "abc-123",
  "title": "Bangkok floods worsen due to climate change",
  "summary": "Heavy rainfall in Bangkok has caused unprecedented flooding...",
  "claims": [
    {
      "text": "Rainfall increased 40% compared to last year",
      "status": "VERIFIED",
      "confidence": 0.92
    }
  ],
  "location": "Bangkok, Thailand",
  "language": "en"
}
```

### Process:
```
1. Script Generation (Claude 3.5 Sonnet)
   ↓
   "Bangkok is experiencing unprecedented flooding. 
    According to verified data, rainfall has increased 
    40% compared to last year due to climate change..."

2. Text-to-Speech (ElevenLabs / Azure TTS)
   ↓
   [Generated audio file: 45 seconds]

3. Visual Assets (Automated)
   ↓
   - B-roll: Pexels API search "bangkok flood"
   - Fact-check graphics: Dynamic SVG generation
   - Location pin: Map with Bangkok highlighted
   - Captions: Auto-generated from script

4. Video Composition (Remotion / FFmpeg)
   ↓
   - 1080x1920 (9:16 vertical)
   - Background music (royalty-free)
   - Smooth transitions
   - Branded intro/outro

5. Rendering
   ↓
   [Output: bangkok-floods-2024.mp4]
   
6. Metadata generation
   ↓
   - Title: "Bangkok Floods Worsen - Climate Reality Check"
   - Description: "Verified climate news from Bangkok..."
   - Tags: #climatechange #bangkok #floods
   - Captions: Multiple languages (EN, FI, TH)
```

### Output formats:
- **TikTok**: 9:16, up to 10 minutes (pero optimal 15-60s)
- **Instagram Reels**: 9:16, up to 90 seconds
- **YouTube Shorts**: 9:16, up to 60 seconds
- **Full video**: 16:9, 2-5 minutes (YouTube main)

---

## 📱 Social Media API Integration

### TikTok API
```python
from TikTokApi import TikTokApi

def publish_to_tiktok(video_path, caption, hashtags):
    api = TikTokApi()
    
    # Upload video
    response = api.upload_video(
        video_path=video_path,
        caption=f"{caption} {' '.join(hashtags)}",
        privacy_level="public",
        allow_comments=True,
        allow_duet=True,
        allow_stitch=True
    )
    
    return response.video_id
```

### Instagram Reels (Graph API)
```python
import requests

def publish_to_instagram(video_url, caption):
    # 1. Create media container
    container_response = requests.post(
        f"https://graph.instagram.com/v18.0/{INSTAGRAM_BUSINESS_ID}/media",
        data={
            "video_url": video_url,
            "caption": caption,
            "media_type": "REELS"
        }
    )
    
    container_id = container_response.json()["id"]
    
    # 2. Publish media
    publish_response = requests.post(
        f"https://graph.instagram.com/v18.0/{INSTAGRAM_BUSINESS_ID}/media_publish",
        data={"creation_id": container_id}
    )
    
    return publish_response.json()["id"]
```

### YouTube Shorts (Data API v3)
```python
from googleapiclient.discovery import build

def publish_to_youtube(video_path, title, description):
    youtube = build('youtube', 'v3', credentials=credentials)
    
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": f"{title} #Shorts",
                "description": description,
                "tags": ["climate change", "shorts", "news"],
                "categoryId": "25"  # News & Politics
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        },
        media_body=video_path
    )
    
    response = request.execute()
    return response["id"]
```

---

## 🗄️ Database Schema Updates

### Uudet taulut globaalille skaalalle:

```sql
-- Maat ja alueet
CREATE TABLE countries (
    country_id UUID PRIMARY KEY,
    country_code CHAR(2) UNIQUE, -- ISO 3166-1 alpha-2
    country_name VARCHAR(255),
    continent VARCHAR(50),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    news_sources_available INT DEFAULT 0,
    articles_count INT DEFAULT 0
);

-- Kielet ja käännökset
CREATE TABLE article_translations (
    translation_id UUID PRIMARY KEY,
    article_id UUID REFERENCES articles(article_id),
    language_code CHAR(2), -- ISO 639-1
    translated_title TEXT,
    translated_content TEXT,
    translated_by VARCHAR(50), -- 'deepl', 'google', 'human'
    translation_confidence DECIMAL(4, 3)
);

-- Videot
CREATE TABLE videos (
    video_id UUID PRIMARY KEY,
    article_id UUID REFERENCES articles(article_id),
    video_url TEXT NOT NULL,
    video_format VARCHAR(20), -- 'tiktok', 'reels', 'shorts'
    duration_seconds INT,
    resolution VARCHAR(10), -- '1080x1920'
    language_code CHAR(2),
    caption TEXT,
    hashtags TEXT[],
    thumbnail_url TEXT,
    view_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Sosiaalisen median julkaisut
CREATE TABLE social_media_posts (
    post_id UUID PRIMARY KEY,
    video_id UUID REFERENCES videos(video_id),
    platform VARCHAR(50), -- 'tiktok', 'instagram', 'youtube'
    platform_post_id VARCHAR(255), -- TikTok video ID, etc.
    post_url TEXT,
    published_at TIMESTAMP,
    status VARCHAR(50), -- 'scheduled', 'published', 'failed'
    views INT DEFAULT 0,
    likes INT DEFAULT 0,
    comments INT DEFAULT 0,
    shares INT DEFAULT 0
);

-- Käyttäjän sosiaalisen median yhteydet
CREATE TABLE user_social_accounts (
    account_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    platform VARCHAR(50),
    platform_user_id VARCHAR(255),
    access_token TEXT, -- Encrypted!
    refresh_token TEXT, -- Encrypted!
    token_expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    auto_publish BOOLEAN DEFAULT FALSE
);
```

---

## 📊 Content Generation: Multi-format outputs

### 1. Artikkeli (nykyinen)
```
📰 Title
📝 Summary
✅ Fact-checks
🔗 Source link
```

### 2. Video (uusi)
```
🎥 15-60s vertical video
   • Text-to-speech narration
   • B-roll footage
   • Fact-check graphics
   • Captions (multi-language)
   
Formats:
   • TikTok (9:16, up to 10min)
   • Instagram Reels (9:16, up to 90s)
   • YouTube Shorts (9:16, up to 60s)
```

### 3. Social media post (uusi)
```
📱 Caption optimized for each platform
   • TikTok: Short, hashtag-heavy
   • Instagram: Story-driven, emojis
   • YouTube: SEO-optimized, links
   
🏷️ Auto-generated hashtags
   #ClimateChange #Bangkok #Floods #FactChecked
```

---

## 🚧 Implementation Roadmap

### Phase 1: Globaali uutisnäkymä (2-3 viikkoa)
- [ ] Lisää maailmankartta etusivulle
- [ ] Maa/maanosa-valitsin
- [ ] API-parametrit: `country`, `continent`
- [ ] Tietokantaskeemat: `countries`, `article_translations`
- [ ] Käännösintegraatio (DeepL API)

### Phase 2: Video Production MVP (3-4 viikkoa)
- [ ] Claude → Video script generation
- [ ] Text-to-speech (ElevenLabs/Azure)
- [ ] B-roll footage (Pexels API)
- [ ] Video rendering (Remotion/FFmpeg)
- [ ] Tallenna videot tietokantaan
- [ ] Latauslinkki käyttäjälle

### Phase 3: Social Media julkaisu (manuaalinen) (2 viikkoa)
- [ ] "Lataa video" -painike
- [ ] Pre-generated captions ja hashtags
- [ ] Ohjeistus manuaaliseen jakamiseen

### Phase 4: Social Media API integraatio (3-4 viikkoa)
- [ ] OAuth-kirjautuminen (TikTok, Instagram, YouTube)
- [ ] API-yhteydet sosiaalisiin medioihin
- [ ] "Julkaise nyt" -toiminto
- [ ] Aikataulutettu julkaisu

### Phase 5: Täysin automatisoitu pipeline (4-6 viikkoa)
- [ ] Käyttäjäprofiilit ja asetukset
- [ ] Auto-publish -toiminto
- [ ] Monitorointi ja analytiikka (views, likes, shares)
- [ ] A/B-testaus (parhaiden julkaisuaikojen optimointi)

---

## 💰 Liiketoimintamalli (päivitetty)

### B2C (Kuluttajat)
**Free tier:**
- ✅ Lue artikkeleita (max 10/päivä)
- ✅ Lataa 1 video/päivä

**Premium ($9.99/kk):**
- ✅ Unlimited artikkelit ja videot
- ✅ Yhdistä 3 sosiaalisen median tiliä
- ✅ Aikataulutettu julkaisu (5 videota/viikko)
- ✅ Analytiikka

**Pro ($29.99/kk):**
- ✅ Kaikki Premium-ominaisuudet
- ✅ Unlimited sosiaalisen median tilit
- ✅ Unlimited aikataulutettu julkaisu
- ✅ Advanced analytics
- ✅ Custom branding videoihin

### B2B (Media & Influencers)
**Creator tier ($99/kk):**
- ✅ White-label videot
- ✅ API-access omiin systemeihin
- ✅ Bulk video generation
- ✅ Custom voice/brand

**Enterprise (Custom pricing):**
- ✅ Kaikki Creator-ominaisuudet
- ✅ Dedicated infra
- ✅ SLA-tuki
- ✅ Custom integrations

---

## 🎯 Success Metrics

### MVP (3 months):
- 1,000 users
- 50 countries covered
- 100 videos generated/day

### Year 1:
- 50,000 users
- 150+ countries
- 10,000 videos/day
- 1M+ social media views/month

### Year 2:
- 500,000 users
- Global coverage
- 100,000 videos/day
- 100M+ social media views/month
- Partnership with major climate orgs (UN, WWF, etc.)

---

## 🤔 Critical Questions

1. **Monetization:**
   - Onko freemium-malli oikea?
   - API-access hinnoittelu?

2. **Content moderation:**
   - Miten varmistetaan että käyttäjät eivät jakaa väärää tietoa?
   - Miten hoidetaan GDPR eri maissa?

3. **Scalability:**
   - Video rendering on raskasta - pilvipalvelut (AWS Lambda, Google Cloud Run)?
   - CDN videoiden jakamiseen (CloudFlare, AWS CloudFront)?

4. **Partnerships:**
   - Yhteistyö uutismedioiden kanssa?
   - API-access tutkijoille?

---

## 🎉 Visio tiivistettynä

**"Luomme maailman johtavan ilmastoviestintäalustan, joka automatisoi tiedon keräämisen, todentamisen ja jakamisen globaalisti - tehden ilmastotiedosta saavutettavaa kaikille, kaikilla kielillä, kaikilla alustoilla."**

### Lopputulos:
- 🌍 **Kuka tahansa, missä tahansa** voi saada faktatarkistettuja ilmastouutisia omalta alueeltaan
- 🎥 **Valmis video-sisältö** joka on optimoitu TikTokiin, Instagramiin ja YouTube Shortsiin
- 🤖 **Täysin automatisoitu** pipeline uutisista videoiksi ja sosiaaliseen mediaan
- 🌐 **Monikielinen** - käännökset automaattisesti 100+ kielelle

**Tämä ei ole vain "Suomen ilmastouutispalvelu" - tämä on globaali ilmastoviestintäalusta. 🚀**

