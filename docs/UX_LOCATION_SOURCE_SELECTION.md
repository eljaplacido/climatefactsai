# UX-suunnittelu: Uutiskanavan ja sijaintipohjainen suodatus

## 📊 Nykyinen tilanne

### Mitä ON toteutettu:
✅ **Tietokannassa:**
- `articles.source_name` - Uutiskanavan nimi (YLE, HS, MTV)
- `articles.location_name` - Maantieteellinen alue (Helsinki, Tampere)
- `articles.location_latitude/longitude` - GPS-koordinaatit
- Indeksit näille kentille suorituskyvyn optimointiin

### Mitä EI OLE toteutettu:
❌ **Frontend:**
- Ei suodatinta uutiskanavalle
- Ei sijaintivalitsinta
- Vain "Luotettavuus"-suodatin (HIGH/MEDIUM/LOW)

❌ **API:**
- Ei parametreja `source` tai `location` haussa
- Kaikki käyttäjät näkevät samat uutiset

❌ **Käyttäjäprofiili:**
- Ei henkilökohtaisia asetuksia
- Ei tallennettuja suodattimia

---

## 🎯 Käyttäjätarpeet

### Kuluttajan perspektiivi:

**Kysymys:** *"Haluan nähdä ilmastouutiset Oulusta YLE:stä - miten teen sen?"*

**Tällä hetkellä:** ❌ **Ei mahdollista**
- Järjestelmä näyttää kaikki artikkelit kaikista lähteistä ja kaikista paikoista
- Käyttäjä joutuu manuaalisesti selaamaan

---

## 💡 UX-ratkaisuvaihtoehdot

### Vaihtoehto 1: **Dropdown-suodattimet** (Yksinkertainen)

```
┌─────────────────────────────────────────────────┐
│  [📍 Kaikki paikat ▾] [📰 Kaikki lähteet ▾]    │
└─────────────────────────────────────────────────┘

📍 Kaikki paikat ▾
  ✓ Kaikki
  ○ Helsinki
  ○ Tampere  
  ○ Oulu
  ○ Lappi

📰 Kaikki lähteet ▾
  ✓ Kaikki
  ○ YLE
  ○ Helsingin Sanomat
  ○ MTV Uutiset
```

**Edut:**
- ✅ Yksinkertainen toteuttaa
- ✅ Tuttu käyttäjälle
- ✅ Ei vaadi kirjautumista

**Haitat:**
- ⚠️ Valinnat eivät tallennu
- ⚠️ Ei personointia

---

### Vaihtoehto 2: **Karttapohjainen valinta** (Visuaalinen)

```
┌─────────────────────────────────────────────────┐
│     🗺️  Suomen kartta                           │
│                                                 │
│      [📍] Helsinki (42 artikkelia)             │
│                                                 │
│           [📍] Tampere (18 artikkelia)         │
│                                                 │
│                  [📍] Oulu (12 artikkelia)     │
│                                                 │
│                    [📍] Rovaniemi (8 art)      │
└─────────────────────────────────────────────────┘
```

**Edut:**
- ✅ Intuitiivinen sijainnin valinta
- ✅ Näyttää artikkelimäärät alueittain
- ✅ "Wau-efekti" - erottuu kilpailijoista

**Haitat:**
- ⚠️ Vaatii karttakirjaston (Leaflet, Mapbox)
- ⚠️ Monimutkaisempi mobiilinäkymä

---

### Vaihtoehto 3: **Personoitu dashboard** (Kehittynyt)

```
┌─────────────────────────────────────────────────┐
│  👤 Tervetuloa, Matti!                          │
│                                                 │
│  📍 Sinun alueesi: Helsinki                     │
│  📰 Suosikit: YLE, HS                           │
│                                                 │
│  [⚙️ Muokkaa asetuksia]                         │
└─────────────────────────────────────────────────┘

Sinun uutisesi (Helsinki, YLE & HS):
  📰 [Artikkeli 1]
  📰 [Artikkeli 2]
  ...

Muut alueet:
  📰 [Artikkeli Oulusta]
```

**Edut:**
- ✅ Paras käyttäjäkokemus
- ✅ Valinnat tallentuvat
- ✅ Mahdollisuus useille "seurantakohteille"

**Haitat:**
- ⚠️ Vaatii käyttäjähallinnan (kirjautuminen)
- ⚠️ Monimutkaisempi backend
- ⚠️ GDPR-vaatimukset

---

## 🚀 Suositus: Vaiheittainen toteutus

### Vaihe 1 (MVP): **Yksinkertaiset dropdownit** 📅 1-2 viikkoa

**Frontend:**
```tsx
// HomePage.tsx
const [selectedSource, setSelectedSource] = useState<string | null>(null);
const [selectedLocation, setSelectedLocation] = useState<string | null>(null);

// Hae suodatetut artikkelit
api.getArticles({
  source: selectedSource,
  location: selectedLocation,
  credibility: filter
});
```

**Backend (API):**
```python
# api/main.py
@app.get("/api/articles")
def get_articles(
    source: Optional[str] = None,      # Uusi!
    location: Optional[str] = None,    # Uusi!
    credibility: Optional[str] = None
):
    query = "SELECT * FROM articles WHERE 1=1"
    
    if source:
        query += " AND source_name = :source"
    if location:
        query += " AND location_name = :location"
    ...
```

**Uudet API-endpointit:**
```python
# Hae kaikki uniikit lähteet
@app.get("/api/sources")
def get_sources():
    return ["YLE", "Helsingin Sanomat", "MTV Uutiset"]

# Hae kaikki uniikit sijainnit
@app.get("/api/locations")
def get_locations():
    return ["Helsinki", "Tampere", "Oulu", "Lappi"]
```

---

### Vaihe 2: **Karttanäkymä** 📅 2-3 viikkoa

**Lisää uusi sivu:** `/map`

```tsx
// MapPage.tsx
import { MapContainer, TileLayer, Marker } from 'react-leaflet';

function MapPage() {
  const [locations, setLocations] = useState([
    { name: "Helsinki", lat: 60.1699, lng: 24.9384, articles: 42 },
    { name: "Tampere", lat: 61.4978, lng: 23.7610, articles: 18 },
    ...
  ]);

  return (
    <MapContainer center={[64.5, 26.5]} zoom={5}>
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {locations.map(loc => (
        <Marker 
          position={[loc.lat, loc.lng]}
          onClick={() => filterArticlesByLocation(loc.name)}
        >
          <Popup>{loc.name}: {loc.articles} artikkelia</Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
```

---

### Vaihe 3: **Käyttäjäprofiili** 📅 3-4 viikkoa

**Uudet taulut:**
```sql
-- Käyttäjäprofiili
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Käyttäjän asetukset
CREATE TABLE user_preferences (
    preference_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    preferred_sources TEXT[], -- ['YLE', 'HS']
    preferred_locations TEXT[], -- ['Helsinki', 'Tampere']
    notification_enabled BOOLEAN DEFAULT FALSE
);
```

**Authentication:**
- JWT-tokenit tai OAuth2
- Sessioiden hallinta Redisillä

---

## 📐 UI-mockup: Dropdown-suodattimet (Vaihe 1)

```tsx
<div className="flex space-x-4 mb-6">
  {/* Sijaintisuodatin */}
  <div className="flex-1">
    <label className="block text-sm font-medium text-gray-700 mb-2">
      📍 Sijainti
    </label>
    <select 
      value={selectedLocation || ''} 
      onChange={(e) => setSelectedLocation(e.target.value || null)}
      className="w-full border rounded-lg px-4 py-2"
    >
      <option value="">Kaikki alueet</option>
      <option value="Helsinki">Helsinki ({helsinkiCount})</option>
      <option value="Tampere">Tampere ({tampereCount})</option>
      <option value="Oulu">Oulu ({ouluCount})</option>
      <option value="Lappi">Lappi ({lappiCount})</option>
    </select>
  </div>

  {/* Lähdesuodatin */}
  <div className="flex-1">
    <label className="block text-sm font-medium text-gray-700 mb-2">
      📰 Uutislähde
    </label>
    <select 
      value={selectedSource || ''} 
      onChange={(e) => setSelectedSource(e.target.value || null)}
      className="w-full border rounded-lg px-4 py-2"
    >
      <option value="">Kaikki lähteet</option>
      <option value="YLE">YLE ({yleCount})</option>
      <option value="Helsingin Sanomat">Helsingin Sanomat ({hsCount})</option>
      <option value="MTV Uutiset">MTV Uutiset ({mtvCount})</option>
    </select>
  </div>

  {/* Luotettavuus (olemassa oleva) */}
  <div className="flex-1">
    <label className="block text-sm font-medium text-gray-700 mb-2">
      ✅ Luotettavuus
    </label>
    <select 
      value={credibilityFilter} 
      onChange={(e) => setCredibilityFilter(e.target.value)}
      className="w-full border rounded-lg px-4 py-2"
    >
      <option value="ALL">Kaikki</option>
      <option value="HIGH">Korkea</option>
      <option value="MEDIUM">Keskitaso</option>
      <option value="LOW">Matala</option>
    </select>
  </div>
</div>

{/* Valitut suodattimet näkyvissä */}
<div className="flex space-x-2 mb-4">
  {selectedLocation && (
    <span className="inline-flex items-center px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
      📍 {selectedLocation}
      <button onClick={() => setSelectedLocation(null)} className="ml-2">✕</button>
    </span>
  )}
  {selectedSource && (
    <span className="inline-flex items-center px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">
      📰 {selectedSource}
      <button onClick={() => setSelectedSource(null)} className="ml-2">✕</button>
    </span>
  )}
</div>
```

---

## 🔮 Tulevaisuuden visio: AI-personointi

**"Suosittelu-algoritmi":**
```
Käyttäjä lukee paljon Helsingin ilmastouutisia
  ↓
Järjestelmä oppii
  ↓
Etusivulle nostetaan automaattisesti:
  - Helsinki-uutiset
  - Samankaltaiset aiheet (esim. joukkoliikenne, energiatehokkuus)
  - Lähialueet (Espoo, Vantaa)
```

---

## ✅ Action Items

### Nyt heti:
1. ☑️ **Lisää dropdown-suodattimet** frontendiin (2h työtä)
2. ☑️ **Päivitä API** ottamaan vastaan `source` ja `location` (1h työtä)
3. ☑️ **Lisää `/api/sources` ja `/api/locations` endpointit** (30min)
4. ☑️ **Testaa suodattimien toiminta** (30min)

### Seuraavaksi (jos aikaa):
5. ⬜ Karttanäkymä Leafletillä
6. ⬜ Artikkelimäärien näyttäminen suodattimissa
7. ⬜ URL-parametrit suodattimille (jakaminen linkkinä)

### Myöhemmin:
8. ⬜ Käyttäjähallinta ja profiili
9. ⬜ Tallennetut suodattimet
10. ⬜ Sähköposti-ilmoitukset valituilta alueilta

---

## 📝 Yhteenveto

**Ongelma:**
> "Käyttäjä ei voi valita haluamaansa uutiskanavaa tai maantieteellistä aluetta"

**Ratkaisu (MVP):**
> Lisätään 2 yksinkertaista dropdown-suodatinta etusivulle + päivitetään API

**Työmäärä:**
> ~3-4 tuntia kehitystyötä

**Vaikutus:**
> ⭐⭐⭐⭐⭐ Kriittinen käyttäjäkokemuksen parannus

