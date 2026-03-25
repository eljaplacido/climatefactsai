# CliLens.AI Frontend

## Overview
The CliLens.AI frontend is a modern, responsive web application built with Next.js 15+ that provides users with access to fact-checked climate news articles. The application emphasizes transparency, interactivity, and user engagement.

## Technology Stack
- **Framework**: Next.js 15+ (React 19)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State Management**: React Context API + Server Components
- **API Client**: Native Fetch with Server Actions
- **Deployment**: Vercel / AWS Amplify

## Key Features

### 1. Article Discovery
- Browse latest fact-checked climate articles
- Filter by location, topic, credibility score
- Search functionality
- Infinite scroll / pagination

### 2. Interactive Fact-Checking
- Hover over claims to see verification sources
- Click claims to view detailed verification data
- Visual confidence indicators
- Source attribution with links

### 3. Responsive Design
- Mobile-first approach
- Optimized for desktop, tablet, mobile
- Fast loading times
- Progressive Web App (PWA) support

### 4. Future Features (Roadmap)
- Video player integration (Phase 2)
- User accounts and preferences
- Personalized content feed
- Social sharing
- Multi-language support

## Project Structure

```
src/frontend/
├── src/
│   ├── app/                    # Next.js 15 App Router
│   │   ├── layout.tsx         # Root layout
│   │   ├── page.tsx           # Homepage
│   │   ├── articles/          # Article routes
│   │   │   ├── [id]/         # Individual article page
│   │   │   └── page.tsx      # Article list page
│   │   └── api/              # API routes (if needed)
│   │
│   ├── components/            # React components
│   │   ├── ArticleCard.tsx
│   │   ├── FactCheckPopover.tsx
│   │   ├── FilterBar.tsx
│   │   ├── Header.tsx
│   │   └── ...
│   │
│   ├── hooks/                 # Custom React hooks
│   │   ├── useArticles.ts
│   │   ├── useFactCheck.ts
│   │   └── ...
│   │
│   └── pages/                 # Legacy pages (if migrating from Pages Router)
│
├── public/                    # Static assets
│   ├── images/
│   ├── icons/
│   └── ...
│
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── next.config.js
```

## Component Architecture

### Core Components

#### `ArticleCard`
Displays article summary with metadata:
- Title
- Summary
- Published date
- Source credibility score
- Number of verified claims
- Tags

#### `FactCheckPopover`
Interactive fact-check display:
- Claim text
- Verification status badge
- Confidence score (visual indicator)
- Source links
- Detailed verification data (expandable)

#### `FilterBar`
Article filtering controls:
- Location dropdown
- Topic/category chips
- Credibility score slider
- Date range picker

#### `ArticleReader`
Full article view:
- Highlighted fact-check elements
- Interactive source attribution
- Share buttons
- Related articles
- "Generate Video" button (Phase 2)

## Data Flow

### Server Components (Next.js 15)
```typescript
// app/articles/page.tsx
export default async function ArticlesPage() {
  // Direct database query or API call
  const articles = await fetchArticles();

  return (
    <div>
      {articles.map(article => (
        <ArticleCard key={article.id} article={article} />
      ))}
    </div>
  );
}
```

### Client Components
```typescript
'use client';

export function FactCheckPopover({ claim }: Props) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <span
      onClick={() => setIsOpen(!isOpen)}
      className="underline cursor-pointer"
    >
      {claim.text}
      {isOpen && (
        <VerificationModal claim={claim} />
      )}
    </span>
  );
}
```

### Server Actions
```typescript
// app/actions/articles.ts
'use server';

export async function filterArticles(filters: Filters) {
  const articles = await db.articles.findMany({
    where: {
      location: filters.location,
      credibilityScore: { gte: filters.minCredibility }
    }
  });

  return articles;
}
```

## API Integration

### Backend API Endpoints
```
GET  /api/articles              # List articles
GET  /api/articles/:id          # Get article detail
GET  /api/claims/:id            # Get claim verification
POST /api/articles/:id/video    # Generate video (Phase 2)
GET  /api/filters               # Get filter options
```

### Example: Fetch Article
```typescript
async function getArticle(id: string) {
  const res = await fetch(`${API_URL}/articles/${id}`);
  const article = await res.json();
  return article;
}
```

## Styling Guidelines

### Tailwind CSS Conventions
```typescript
// Consistent spacing and typography
<article className="
  p-6
  bg-white
  rounded-lg
  shadow-md
  hover:shadow-lg
  transition-shadow
">
  <h2 className="text-2xl font-bold mb-4">
    {title}
  </h2>
  <p className="text-gray-600 leading-relaxed">
    {summary}
  </p>
</article>
```

### Color Palette
```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        'clilens-primary': '#2E7D32',     // Green
        'clilens-secondary': '#1976D2',   // Blue
        'clilens-verified': '#4CAF50',    // Verified badge
        'clilens-unverified': '#FF9800',  // Low confidence
      }
    }
  }
}
```

## State Management

### Context API Pattern
```typescript
// context/ArticleContext.tsx
'use client';

const ArticleContext = createContext<ArticleContextType>(null);

export function ArticleProvider({ children }: Props) {
  const [filters, setFilters] = useState<Filters>({});
  const [articles, setArticles] = useState<Article[]>([]);

  return (
    <ArticleContext.Provider value={{ filters, setFilters, articles }}>
      {children}
    </ArticleContext.Provider>
  );
}
```

## Performance Optimization

### Next.js 15 Features
- Server Components for zero client JS
- Streaming with Suspense
- Partial Pre-rendering (PPR)
- Image optimization with next/image
- Font optimization with next/font

### Code Splitting
```typescript
// Lazy load heavy components
const VideoPlayer = dynamic(() => import('./VideoPlayer'), {
  ssr: false,
  loading: () => <Spinner />
});
```

## Development

### Setup
```bash
cd src/frontend
npm install
npm run dev
```

### Build
```bash
npm run build
npm run start
```

### Testing
```bash
npm run test          # Jest + React Testing Library
npm run test:e2e      # Playwright E2E tests
```

## Environment Variables
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_CDN_URL=https://cdn.clilens.ai
NEXT_PUBLIC_ENABLE_VIDEO=false
```

## Deployment

### Vercel (Recommended)
```bash
vercel deploy
```

### Docker
```bash
docker build -t clilens-frontend .
docker run -p 3000:3000 clilens-frontend
```

## Accessibility
- Semantic HTML5
- ARIA labels for interactive elements
- Keyboard navigation support
- Screen reader optimized
- WCAG 2.1 AA compliance

## Future Enhancements
- Real-time article updates (WebSockets)
- Progressive Web App (PWA) with offline support
- Dark mode
- User authentication
- Personalized recommendations
- Social features (comments, discussions)
- Newsletter subscription
- Mobile app (React Native)
