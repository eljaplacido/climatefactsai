# Climate News - Frontend

Moderni React-pohjainen web-sovellus ilmastouutisten selaamiseen ja faktatarkistusten näyttämiseen.

## 🚀 Pikaopas

```bash
# Asenna riippuvuudet
npm install

# Käynnistä dev server
npm run dev

# Avautuu: http://localhost:3000
```

## 📦 Teknologiat

- **React 18** - UI-kirjasto
- **TypeScript** - Tyypitys
- **Vite** - Build tool & dev server
- **React Router 6** - Reititys
- **Tailwind CSS** - Tyylit
- **Axios** - HTTP-client
- **Lucide React** - Ikonit
- **date-fns** - Päivämäärien käsittely

## 📁 Projektirakenne

```
frontend/
├── src/
│   ├── components/          # UI-komponentit
│   │   ├── Layout.tsx       # Navigaatio & footer
│   │   ├── ArticleCard.tsx  # Artikkelikortit
│   │   ├── FactCheckBadge.tsx
│   │   ├── StatCard.tsx
│   │   └── LoadingSpinner.tsx
│   │
│   ├── pages/               # Sivut
│   │   ├── HomePage.tsx
│   │   ├── ArticleDetailPage.tsx
│   │   ├── AdminDashboard.tsx
│   │   └── AboutPage.tsx
│   │
│   ├── services/            # API-integraatiot
│   │   └── api.ts
│   │
│   ├── types/               # TypeScript-tyypit
│   │   └── index.ts
│   │
│   ├── App.tsx              # Pääkomponentti
│   ├── main.tsx             # Entry point
│   └── index.css            # Globaalit tyylit
│
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

## 🎨 Komponentit

### Layout
Koko sovelluksen wrapper - sisältää navigaation ja footerin.

### ArticleCard
Näyttää artikkelin esikatselun:
- Otsikko
- Lähde ja kirjoittaja
- Ote tekstistä
- Faktatarkistusstatistiikka
- Luotettavuusmerkki

### FactCheckBadge
Näyttää faktatarkistuksen tuloksen:
- ✅ Todennettu (vihreä)
- ❌ Ei todennettu (punainen)
- ⚠️ Osittain todennettu (keltainen)
- Confidence-prosentti

### StatCard
Dashboard-tilastokortti:
- Ikoni
- Otsikko
- Arvo
- Valinnainen trendi

## 📄 Sivut

### HomePage (`/`)
- Artikkelilista ruudukossa
- Suodattimet (Kaikki/Korkea/Keskitaso/Matala)
- Tilastokortit
- Hero-banneri

### ArticleDetailPage (`/articles/:id`)
- Artikkelin täysi teksti
- Kaikki faktatarkistukset yksityiskohtaisesti
- Luotettavuusyhteenveto
- Linkki alkuperäiseen

### AdminDashboard (`/admin`)
- Järjestelmän tilastot
- Workflow-käynnistin
- Workflow-historia
- Agenttistatukset

### AboutPage (`/about`)
- Tietoa järjestelmästä
- Teknologiapino
- Ominaisuudet

## 🔌 API-integraatio

Frontend kommunikoi backend API:n kanssa (`http://localhost:8000`):

```typescript
// services/api.ts
export const api = {
  getArticles(params?): Promise<Article[]>
  getArticleDetail(id): Promise<ArticleDetail>
  getStats(): Promise<DashboardStats>
  triggerWorkflow(): Promise<TriggerResponse>
  getWorkflows(): Promise<WorkflowStatus[]>
}
```

## 🎨 Tyylit

Tailwind CSS custom-konfiguraatio:

```javascript
// tailwind.config.js
theme: {
  extend: {
    colors: {
      'climate-green': { ... },
      'climate-blue': { ... }
    }
  }
}
```

## 🛠️ Kehitys

```bash
# Dev server hot-reloadilla
npm run dev

# Build tuotantoon
npm run build

# Preview production build
npm run preview

# Lint
npm run lint
```

## 🐳 Docker

```bash
# Build Docker image
docker build -t climatenews-frontend .

# Run container
docker run -p 3000:80 climatenews-frontend
```

## 🔧 Konfiguraatio

### Environment variables

Luo `.env` tiedosto:

```env
VITE_API_URL=http://localhost:8000
```

### Vite config

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

## 📱 Responsiivisuus

Sovellus on täysin responsiivinen:
- **Mobile:** 1 artikkelikortti per rivi
- **Tablet:** 1-2 korttia per rivi
- **Desktop:** 2 korttia per rivi

Tailwind breakpointit:
- `sm:` 640px
- `md:` 768px
- `lg:` 1024px
- `xl:` 1280px

## 🚀 Deployment

### Nginx (Production)

Frontend buildataan staattisiksi tiedostoiksi ja tarjoillaan Nginx:llä:

```nginx
server {
  listen 80;
  root /usr/share/nginx/html;
  
  location / {
    try_files $uri $uri/ /index.html;
  }
  
  location /api {
    proxy_pass http://api:8000;
  }
}
```

## 🧪 Testaus

```bash
# TODO: Lisää testit
npm run test
```

## 📝 Lisenssi

Katso projektin juuressa oleva LICENSE-tiedosto.

---

**Tekijä:** Climate News Team  
**Versio:** 1.0.0  
**Päivitetty:** 2024-10-15

