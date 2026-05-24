import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Phase 7 B3 (2026-05-24) — company detail business view.
// Pins the business-decision-maker surface that was added on top of the
// existing /companies/[ticker] page. The toggle is URL-persistent and the
// disclosure cards stamp compliance-framework chips, mirroring the Country
// Passport pattern from Phase 6.

let currentSearch = ''
const replaceMock = vi.fn((url: string) => {
  const qIdx = url.indexOf('?')
  currentSearch = qIdx >= 0 ? url.slice(qIdx + 1) : ''
})

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock }),
  usePathname: () => '/companies/MSFT',
  useSearchParams: () => new URLSearchParams(currentSearch),
  useParams: () => ({ ticker: 'MSFT' }),
}))

vi.mock('next/link', () => ({
  default: ({ children, href, ...rest }: any) =>
    React.createElement('a', { href, ...rest }, children),
}))

const COMPANY_FIXTURE = {
  company: {
    company_id: 'co-1',
    name: 'Microsoft Corporation',
    ticker: 'MSFT',
    country_code: 'US',
    sector_nace: '62.01',
    disclosure_count: 1,
    latest_disclosure_year: 2024,
    sbti_validated: true,
    net_zero_target_year: 2030,
  },
  disclosures: [
    {
      disclosure_id: 'd-1',
      source: 'cdp',
      reporting_year: 2024,
      scope1_tco2e: 144000,
      scope2_tco2e_market: 0,
      scope2_tco2e_location: 800000,
      scope3_tco2e: 16300000,
      scope1_2_verified: true,
      sbti_validated: true,
      target_year: 2030,
      baseline_year: 2020,
      target_pct_reduction: 50,
      net_zero_target_year: 2030,
      assurance_level: 'reasonable',
    },
  ],
  claims: [],
}

const UNVALIDATED_FIXTURE = {
  company: {
    company_id: 'co-2',
    name: 'ExxonMobil Corporation',
    ticker: 'XOM',
    country_code: 'US',
    sector_nace: '06.10',
    disclosure_count: 1,
    latest_disclosure_year: 2024,
    sbti_validated: false,
    net_zero_target_year: 2050,
  },
  disclosures: [
    {
      disclosure_id: 'd-x',
      source: 'cdp',
      reporting_year: 2024,
      scope1_tco2e: 109000000,
      scope2_tco2e_market: 2700000,
      scope2_tco2e_location: null,
      scope3_tco2e: 580000000,
      scope1_2_verified: true,
      sbti_validated: false,
      target_year: null,
      baseline_year: 2016,
      target_pct_reduction: null,
      net_zero_target_year: 2050,
      offset_based_claims:
        'Significant reliance on offsets and CCS for residual emissions',
      assurance_level: 'limited',
    },
  ],
  claims: [],
}

beforeEach(() => {
  vi.restoreAllMocks()
  currentSearch = ''
  replaceMock.mockClear()
})

function mockFetch(payload: any) {
  ;(global as any).fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: async () => payload }),
  )
}

// Lazy import so the next/navigation mock above is in effect.
import CompanyDetailPage from '@/app/companies/[ticker]/page'

describe('CompanyDetailPage — Phase 7 B3 business view', () => {
  it('renders the view-mode toggle with Public selected by default', async () => {
    mockFetch(COMPANY_FIXTURE)
    render(<CompanyDetailPage />)
    await waitFor(() =>
      expect(screen.getByTestId('company-view-mode-toggle')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('company-view-public')).toHaveAttribute(
      'aria-checked',
      'true',
    )
    expect(screen.getByTestId('company-view-business')).toHaveAttribute(
      'aria-checked',
      'false',
    )
  })

  it('Public view shows the original SBTi line, no business framing', async () => {
    mockFetch(COMPANY_FIXTURE)
    render(<CompanyDetailPage />)
    await waitFor(() =>
      expect(screen.getByText(/SBTi: Validated/)).toBeInTheDocument(),
    )
    expect(
      screen.queryByTestId('company-business-context'),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByTestId('disclosure-business-footer'),
    ).not.toBeInTheDocument()
  })

  it('Business view: clicking toggle swaps in the business framing', async () => {
    mockFetch(COMPANY_FIXTURE)
    const user = userEvent.setup()
    render(<CompanyDetailPage />)
    await waitFor(() =>
      expect(screen.getByTestId('company-view-mode-toggle')).toBeInTheDocument(),
    )
    await user.click(screen.getByTestId('company-view-business'))
    // Business framing for SBTi
    await waitFor(() =>
      expect(screen.getByTestId('company-sbti-business')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('company-sbti-business').textContent).toMatch(
      /ECGT-compliant/i,
    )
    // Business explainer paragraph
    expect(screen.getByTestId('company-business-context')).toBeInTheDocument()
    expect(
      screen.getByTestId('company-business-context').textContent,
    ).toMatch(/ECGT Article 4/)
  })

  it('Business view: SBTi-unvalidated company reads as ECGT audit risk', async () => {
    mockFetch(UNVALIDATED_FIXTURE)
    const user = userEvent.setup()
    render(<CompanyDetailPage />)
    await waitFor(() =>
      expect(screen.getByTestId('company-view-mode-toggle')).toBeInTheDocument(),
    )
    await user.click(screen.getByTestId('company-view-business'))
    await waitFor(() =>
      expect(screen.getByTestId('company-sbti-business')).toBeInTheDocument(),
    )
    const text = screen.getByTestId('company-sbti-business').textContent || ''
    expect(text).toMatch(/Not SBTi-validated/i)
    expect(text).toMatch(/ECGT Article 4 audit risk/i)
  })

  it('Business view: each disclosure card carries compliance-framework chips', async () => {
    mockFetch(COMPANY_FIXTURE)
    const user = userEvent.setup()
    render(<CompanyDetailPage />)
    await waitFor(() =>
      expect(screen.getByTestId('company-view-mode-toggle')).toBeInTheDocument(),
    )
    await user.click(screen.getByTestId('company-view-business'))
    const chips = await screen.findByTestId('disclosure-compliance-chips')
    expect(chips).toBeInTheDocument()
    // CDP source + sbti_validated + scope1_2_verified → all three regimes
    expect(chips.textContent).toContain('CSRD')
    expect(chips.textContent).toContain('IFRS S2')
    expect(chips.textContent).toContain('TCFD')
  })

  it('Business view: offset_based_claims surfaces an ECGT Article 4 warning', async () => {
    mockFetch(UNVALIDATED_FIXTURE)
    const user = userEvent.setup()
    render(<CompanyDetailPage />)
    await waitFor(() =>
      expect(screen.getByTestId('company-view-mode-toggle')).toBeInTheDocument(),
    )
    await user.click(screen.getByTestId('company-view-business'))
    const warning = await screen.findByTestId('disclosure-offset-warning')
    expect(warning).toBeInTheDocument()
    expect(warning.textContent).toMatch(/ECGT Article 4 risk/)
    expect(warning.textContent).toMatch(/offsets/)
  })

  it('Public view: compliance chips and offset warning are absent', async () => {
    mockFetch(UNVALIDATED_FIXTURE)
    render(<CompanyDetailPage />)
    await waitFor(() =>
      expect(screen.getByTestId('company-view-mode-toggle')).toBeInTheDocument(),
    )
    expect(
      screen.queryByTestId('disclosure-compliance-chips'),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByTestId('disclosure-offset-warning'),
    ).not.toBeInTheDocument()
  })

  it('Business view: ?view=business is written to the URL via router.replace', async () => {
    mockFetch(COMPANY_FIXTURE)
    const user = userEvent.setup()
    render(<CompanyDetailPage />)
    await waitFor(() =>
      expect(screen.getByTestId('company-view-mode-toggle')).toBeInTheDocument(),
    )
    await user.click(screen.getByTestId('company-view-business'))
    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalled()
    })
    const calls = replaceMock.mock.calls.map((c) => c[0] as string)
    expect(calls.some((u) => u.includes('view=business'))).toBe(true)
  })

  it('Hydration: ?view=business in the URL renders business view on first paint', async () => {
    currentSearch = 'view=business'
    mockFetch(COMPANY_FIXTURE)
    render(<CompanyDetailPage />)
    await waitFor(() =>
      expect(screen.getByTestId('company-business-context')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('company-view-business')).toHaveAttribute(
      'aria-checked',
      'true',
    )
  })
})
