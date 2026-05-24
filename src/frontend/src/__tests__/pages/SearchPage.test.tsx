import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SearchPage from '@/app/search/page'
import type { Article } from '@/types'

// Mock next/link
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: any) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

// Phase 2H (2026-05-23): SearchPage now uses useUrlState which depends
// on next/navigation. Stub the router + searchParams so the existing
// SearchPage tests keep working under the URL-persistent rollout.
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => '/search',
  useSearchParams: () => new URLSearchParams(),
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

vi.mock('@/components/LoginPrompt', () => ({
  default: () => <div data-testid="login-prompt">LoginPrompt</div>,
}))

vi.mock('@/lib/auth', () => ({
  useAuth: () => ({
    isLoggedIn: true,
  }),
}))

const mockArticles: Article[] = [
  {
    article_id: 's1',
    title: 'Nordic Climate Adaptation',
    url: 'https://example.com/s1',
    source_name: 'YLE',
    source_credibility_score: 88,
    overall_credibility: 'HIGH',
    reliability_score: 88,
    tags: ['adaptation'],
    excerpt: 'Nordic countries adapt to climate change.',
    claim_count: 3,
    verified_claim_count: 2,
    created_at: '2026-03-05T00:00:00Z',
  },
]

const mockGetArticles = vi.fn().mockResolvedValue(mockArticles)
const mockGetTagStats = vi.fn().mockResolvedValue([
  { tag: 'climate', article_count: 10 },
  { tag: 'energy', article_count: 5 },
])
const mockGetSearchSuggestions = vi.fn().mockResolvedValue([])

vi.mock('@/lib/api', () => ({
  api: {
    getArticles: (...args: any[]) => mockGetArticles(...args),
    getTagStats: (...args: any[]) => mockGetTagStats(...args),
    getSearchSuggestions: (...args: any[]) => mockGetSearchSuggestions(...args),
  },
}))

describe('SearchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetArticles.mockResolvedValue(mockArticles)
    mockGetTagStats.mockResolvedValue([
      { tag: 'climate', article_count: 10 },
      { tag: 'energy', article_count: 5 },
    ])
    mockGetSearchSuggestions.mockResolvedValue([])
  })

  it('renders search heading', async () => {
    render(<SearchPage />)
    await waitFor(() => {
      expect(screen.getByText('Search')).toBeInTheDocument()
    })
  })

  it('renders search input', async () => {
    render(<SearchPage />)
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Search topics/)).toBeInTheDocument()
    })
  })

  it('renders credibility filter', async () => {
    render(<SearchPage />)
    await waitFor(() => {
      expect(screen.getByDisplayValue('All')).toBeInTheDocument()
    })
  })

  it('displays articles from API', async () => {
    render(<SearchPage />)
    await waitFor(() => {
      expect(screen.getByText('Nordic Climate Adaptation')).toBeInTheDocument()
    })
  })

  it('displays tag stats as filter pills', async () => {
    render(<SearchPage />)
    await waitFor(() => {
      expect(screen.getByText('climate (10)')).toBeInTheDocument()
      expect(screen.getByText('energy (5)')).toBeInTheDocument()
    })
  })

  it('shows error when API fails', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockGetArticles.mockRejectedValueOnce(new Error('Network error'))
    render(<SearchPage />)
    await waitFor(() => {
      expect(screen.getByText(/Search unavailable/)).toBeInTheDocument()
    })
    consoleErrorSpy.mockRestore()
  })

  it('shows empty state when no results', async () => {
    mockGetArticles.mockResolvedValueOnce([])
    render(<SearchPage />)
    await waitFor(() => {
      expect(screen.getByText(/No results found/i)).toBeInTheDocument()
    })
  })
})
