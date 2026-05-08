import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import type { Article } from '@/types'

// Mock next/link
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: any) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

// Mock child components that need special handling
vi.mock('@/components/TrendingTopics', () => ({
  default: ({ onTopicClick, activeTag }: any) => (
    <div data-testid="trending-topics">TrendingTopics</div>
  ),
}))

vi.mock('@/components/CountrySelector', () => ({
  default: ({ value, onChange }: any) => (
    <select data-testid="country-selector" value={value || ''} onChange={(e) => onChange(e.target.value || null)}>
      <option value="">All Countries</option>
      <option value="FI">Finland</option>
    </select>
  ),
}))

vi.mock('@/components/BookmarkButton', () => ({
  default: () => <button>Bookmark</button>,
}))

vi.mock('@/components/ArticleCard', () => ({
  default: ({ article }: any) => (
    <div data-testid={`article-${article.article_id}`}>{article.title}</div>
  ),
}))

vi.mock('@/components/SkeletonCard', () => ({
  default: () => <div data-testid="skeleton-card">Loading...</div>,
}))

// Mock the api module — factory must not reference outer variables
const mockGetArticles = vi.fn()
const mockGetTagStats = vi.fn()

vi.mock('@/lib/api', () => ({
  api: {
    getArticles: (...args: any[]) => mockGetArticles(...args),
    getTagStats: (...args: any[]) => mockGetTagStats(...args),
    getSearchSuggestions: vi.fn().mockResolvedValue([]),
  },
}))

// Import after mocks
import Home from '@/app/page'

const mockArticles: Article[] = [
  {
    article_id: 'a1',
    title: 'Climate Report 2026',
    url: 'https://example.com/1',
    source_name: 'Reuters',
    source_credibility_score: 90,
    published_date: '2026-03-01T00:00:00Z',
    overall_credibility: 'HIGH',
    reliability_score: 90,
    tags: ['climate'],
    excerpt: 'Latest climate findings.',
    claim_count: 5,
    verified_claim_count: 4,
    created_at: '2026-03-01T00:00:00Z',
  },
  {
    article_id: 'a2',
    title: 'Green Energy Transition',
    url: 'https://example.com/2',
    source_name: 'BBC',
    source_credibility_score: 85,
    overall_credibility: 'MEDIUM',
    tags: ['energy'],
    claim_count: 2,
    verified_claim_count: 1,
    created_at: '2026-03-02T00:00:00Z',
  },
]

describe('HomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetArticles.mockResolvedValue(mockArticles)
    mockGetTagStats.mockResolvedValue([])
  })

  it('renders the CliLens.AI brand', async () => {
    render(<Home />)
    await waitFor(() => {
      expect(screen.getAllByText('CliLens.AI').length).toBeGreaterThan(0)
    })
  })

  it('renders hero section', async () => {
    render(<Home />)
    expect(screen.getByText(/Climate Truth/)).toBeInTheDocument()
  })

  it('renders navigation links', async () => {
    render(<Home />)
    // Current GlobalNav.tsx ships these primary items; "About"/"Methodology"
    // were removed in favour of the in-product Methodology drawer.
    expect(screen.getAllByText('News').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Map').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Search').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Deep Search').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Sources').length).toBeGreaterThan(0)
  })

  it('renders articles after loading', async () => {
    render(<Home />)
    await waitFor(() => {
      expect(screen.getAllByText('Climate Report 2026').length).toBeGreaterThan(0)
      expect(screen.getByText('Green Energy Transition')).toBeInTheDocument()
    })
  })

  it('renders credibility filter', () => {
    render(<Home />)
    const select = screen.getByDisplayValue('All Levels')
    expect(select).toBeInTheDocument()
  })

  it('renders footer', () => {
    render(<Home />)
    expect(screen.getByText(/Powered by Multi-Agent AI System/)).toBeInTheDocument()
  })
})
