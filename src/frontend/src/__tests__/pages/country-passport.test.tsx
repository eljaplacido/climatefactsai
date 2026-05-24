import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Track URL state so the useUrlState hook works in the test harness.
let currentSearch = ''
const replaceMock = vi.fn((url: string) => {
  const qIdx = url.indexOf('?')
  currentSearch = qIdx >= 0 ? url.slice(qIdx + 1) : ''
})

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock }),
  usePathname: () => '/country/DE',
  useSearchParams: () => new URLSearchParams(currentSearch),
  useParams: () => ({ code: 'DE' }),
}))

vi.mock('next/link', () => ({
  default: ({ children, href, ...rest }: any) =>
    React.createElement('a', { href, ...rest }, children),
}))

const DETAIL_FIXTURE = {
  country_code: 'DE',
  country_name: 'Germany',
  flag: '🇩🇪',
  continent: 'Europe',
  article_count: 142,
  avg_credibility: 78,
  climate_risk_score: 32,
  category_breakdown: {
    climate_science: 45,
    policy: 67,
    green_transition: 30,
  },
  weather: {
    temperature_c: 12.3,
    temperature_anomaly_c: 1.4,
  },
  sources: [
    { source_name: 'Tagesschau', article_count: 50, avg_credibility: 80 },
    { source_name: 'Spiegel', article_count: 30, avg_credibility: 72 },
  ],
  recent_articles: [
    {
      article_id: 'a-1',
      title: 'Germany hits 50% renewable share milestone',
      source_name: 'Tagesschau',
      published_date: '2026-05-20T10:00:00Z',
      credibility: 'HIGH',
    },
  ],
}

const CLIMATE_FIXTURE = {
  country_code: 'DE',
  current_month: { period: '2026-05', temperature_avg_c: 14.2, precipitation_avg_mm: 2.1 },
  last_year_same_month: { period: '2025-05', temperature_avg_c: 12.8, precipitation_avg_mm: 3.0 },
  five_years_ago_same_month: { period: '2021-05', temperature_avg_c: 11.9, precipitation_avg_mm: 2.7 },
  temperature_trend: 'rising' as const,
  precipitation_comparison: 'similar to last year',
}

const CLAIMS_FIXTURE = [
  {
    claim_id: 'c-1',
    claim_text: 'Germany reduced emissions by 40% from 1990 baseline.',
    verification_status: 'VERIFIED',
    confidence_score: 0.92,
    article_id: 'a-1',
  },
  {
    claim_id: 'c-2',
    claim_text: 'Coal phase-out target moved to 2030.',
    verification_status: 'DISPUTED',
    confidence_score: 0.55,
  },
]

beforeEach(() => {
  vi.restoreAllMocks()
  currentSearch = ''
  replaceMock.mockClear()
  ;(global as any).fetch = vi.fn((url: string) => {
    if (url.includes('/climate-data')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => CLIMATE_FIXTURE })
    }
    if (url.includes('/claim-ledger')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => CLAIMS_FIXTURE })
    }
    if (url.includes('/detail')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => DETAIL_FIXTURE })
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => ({}) })
  })
})

import CountryPassportPage from '@/app/country/[code]/page'

describe('Country Climate Passport (Phase 2B / MH3)', () => {
  it('renders the country name and KPIs after loading detail', async () => {
    render(<CountryPassportPage />)
    await waitFor(() =>
      expect(screen.getByTestId('country-passport-title')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('country-passport-title')).toHaveTextContent('Germany')
    expect(screen.getByTestId('kpi-articles')).toHaveTextContent('142')
    expect(screen.getByTestId('kpi-credibility')).toHaveTextContent('78/100')
    expect(screen.getByTestId('kpi-anomaly')).toHaveTextContent('+1.4°C')
  })

  it('renders all 5 tabs and starts on overview by default', async () => {
    render(<CountryPassportPage />)
    await waitFor(() =>
      expect(screen.getByTestId('passport-tab-overview')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('passport-tab-news')).toBeInTheDocument()
    expect(screen.getByTestId('passport-tab-climate')).toBeInTheDocument()
    expect(screen.getByTestId('passport-tab-sources')).toBeInTheDocument()
    expect(screen.getByTestId('passport-tab-claims')).toBeInTheDocument()
    // Default = overview
    expect(screen.getByTestId('passport-tab-overview')).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('passport-panel-overview')).toBeInTheDocument()
  })

  it('switching tabs updates the active panel and the URL', async () => {
    const user = userEvent.setup()
    render(<CountryPassportPage />)
    await waitFor(() =>
      expect(screen.getByTestId('passport-tab-news')).toBeInTheDocument(),
    )
    await user.click(screen.getByTestId('passport-tab-news'))
    expect(screen.getByTestId('passport-tab-news')).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('passport-panel-news')).toBeInTheDocument()
    // URL gets ?tab=news (overview is the default → drops the param)
    await waitFor(() => expect(replaceMock).toHaveBeenCalled())
    const lastUrl = replaceMock.mock.calls[replaceMock.mock.calls.length - 1][0]
    expect(lastUrl).toContain('tab=news')
  })

  it('hydrates from ?tab=climate on initial load and fetches climate data', async () => {
    currentSearch = 'tab=climate'
    render(<CountryPassportPage />)
    await waitFor(() =>
      expect(screen.getByTestId('passport-tab-climate')).toHaveAttribute('aria-selected', 'true'),
    )
    expect(screen.getByTestId('passport-panel-climate')).toBeInTheDocument()
    await waitFor(() => {
      const climateFetchCall = (global.fetch as any).mock.calls.find((c: any[]) =>
        String(c[0]).includes('/climate-data'),
      )
      expect(climateFetchCall).toBeDefined()
    })
  })

  it('news tab renders the recent_articles list with credibility chips', async () => {
    const user = userEvent.setup()
    render(<CountryPassportPage />)
    await waitFor(() =>
      expect(screen.getByTestId('passport-tab-news')).toBeInTheDocument(),
    )
    await user.click(screen.getByTestId('passport-tab-news'))
    expect(
      screen.getByText('Germany hits 50% renewable share milestone'),
    ).toBeInTheDocument()
    expect(screen.getByText('HIGH')).toBeInTheDocument()
  })

  it('sources tab renders the source table with article counts', async () => {
    const user = userEvent.setup()
    render(<CountryPassportPage />)
    await waitFor(() =>
      expect(screen.getByTestId('passport-tab-sources')).toBeInTheDocument(),
    )
    await user.click(screen.getByTestId('passport-tab-sources'))
    expect(screen.getByText('Tagesschau')).toBeInTheDocument()
    expect(screen.getByText('Spiegel')).toBeInTheDocument()
    // article_count formatted
    expect(screen.getByText('50')).toBeInTheDocument()
  })

  it('claims tab lazy-loads /claim-ledger and renders verdict chips', async () => {
    const user = userEvent.setup()
    render(<CountryPassportPage />)
    await waitFor(() =>
      expect(screen.getByTestId('passport-tab-claims')).toBeInTheDocument(),
    )
    await user.click(screen.getByTestId('passport-tab-claims'))
    await waitFor(() => {
      const claimsFetchCall = (global.fetch as any).mock.calls.find((c: any[]) =>
        String(c[0]).includes('/claim-ledger'),
      )
      expect(claimsFetchCall).toBeDefined()
    })
    await waitFor(() => {
      expect(
        screen.getByText('Germany reduced emissions by 40% from 1990 baseline.'),
      ).toBeInTheDocument()
    })
    expect(screen.getByText('VERIFIED')).toBeInTheDocument()
    expect(screen.getByText('DISPUTED')).toBeInTheDocument()
  })

  it('uses role=tablist and role=tab for accessibility', async () => {
    render(<CountryPassportPage />)
    await waitFor(() =>
      expect(screen.getByRole('tablist')).toBeInTheDocument(),
    )
    const tabs = screen.getAllByRole('tab')
    // Phase 8 MH4 (2026-05-24): bumped to 6 with the new Projections tab.
    expect(tabs).toHaveLength(6)
    for (const t of tabs) {
      expect(t).toHaveAttribute('aria-controls')
    }
  })

  it('view-on-map deeplink targets /map?country=DE', async () => {
    render(<CountryPassportPage />)
    await waitFor(() =>
      expect(screen.getByRole('link', { name: /View on map/i })).toBeInTheDocument(),
    )
    expect(screen.getByRole('link', { name: /View on map/i })).toHaveAttribute(
      'href',
      '/map?country=DE',
    )
  })
})
