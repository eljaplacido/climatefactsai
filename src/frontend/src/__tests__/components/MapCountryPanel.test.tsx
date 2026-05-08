import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import MapCountryPanel from '@/components/map/MapCountryPanel'

// Stub recharts ResponsiveContainer so the radar renders deterministically in jsdom.
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts')
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="recharts-responsive" style={{ width: 400, height: 230 }}>
        {children}
      </div>
    ),
  }
})

const detailPayload = {
  country_code: 'FI',
  country_name: 'Finland',
  article_count: 42,
  avg_credibility: 80,
  climate_risk_score: 35,
  category_breakdown: { climate_policy: 20, renewable_energy: 22 },
  sources: [
    { source_name: 'Reuters', article_count: 20, avg_credibility: 88 },
    { source_name: 'YLE', article_count: 22, avg_credibility: 78 },
  ],
}

const comparePayload = {
  country_a: {
    country_code: 'FI',
    article_count: 42,
    source_count: 3,
    avg_credibility: 80,
    climate_risk_score: 3.5,
    green_transition_score: 8.1,
    renewable_energy_score: 9.0,
    cleantech_score: 7.5,
    circular_economy_score: 6.8,
    resource_efficiency_score: 7.0,
    regenerative_score: 6.5,
    sustainability_score: 8.4,
  },
  country_b: {
    country_code: 'SE',
    article_count: 31,
    source_count: 2,
    avg_credibility: 76,
    climate_risk_score: 3.8,
    green_transition_score: 8.4,
    renewable_energy_score: 8.7,
    cleantech_score: 8.1,
    circular_economy_score: 7.2,
    resource_efficiency_score: 7.5,
    regenerative_score: 6.9,
    sustainability_score: 8.6,
  },
  comparison_summary: 'Both Finland and Sweden lead in green transition.',
}

function setupFetchRouter() {
  const calls: string[] = []
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    calls.push(url)
    if (url.includes('/api/map/country/') && url.endsWith('/detail')) {
      return {
        ok: true,
        status: 200,
        json: () => Promise.resolve(detailPayload),
      } as Response
    }
    if (url.includes('/api/map/compare')) {
      return {
        ok: true,
        status: 200,
        json: () => Promise.resolve(comparePayload),
      } as Response
    }
    if (url.includes('/api/articles')) {
      return {
        ok: true,
        status: 200,
        json: () => Promise.resolve([]),
      } as Response
    }
    return {
      ok: false,
      status: 404,
      json: () => Promise.resolve({}),
    } as Response
  })
  vi.spyOn(global, 'fetch').mockImplementation(fn as any)
  return { fn, calls }
}

beforeEach(() => {
  setupFetchRouter()
})

afterEach(() => {
  vi.restoreAllMocks()
})

async function openCompareTab() {
  // The compare tab button has the visible text "Compare"
  const compareTab = await screen.findByRole('button', { name: /Compare/i })
  fireEvent.click(compareTab)
  // Type a comparison country code and click the Compare submit button
  const codeInput = await screen.findByPlaceholderText(/Country code/i)
  fireEvent.change(codeInput, { target: { value: 'SE' } })
  // The submit button's accessible name is "Compare" — find within the form area
  // by looking for the button next to the input (last enabled "Compare" button).
  const buttons = screen.getAllByRole('button', { name: /Compare/i })
  // The last "Compare" button is the submit one (the first one is the tab).
  const submitBtn = buttons[buttons.length - 1]
  fireEvent.click(submitBtn)
}

describe('MapCountryPanel — Compare tab plumbing', () => {
  it('renders country detail using country_a / country_b from API response', async () => {
    render(
      <MapCountryPanel countryCode="FI" onClose={vi.fn()} />
    )

    await openCompareTab()

    // Country A panel uses country_a.article_count = 42
    await waitFor(() => {
      expect(screen.getByText(/Articles:\s*42/)).toBeInTheDocument()
    })
    // Country B panel uses country_b.article_count = 31
    expect(screen.getByText(/Articles:\s*31/)).toBeInTheDocument()
    // Avg credibility values
    expect(screen.getByText(/Credibility:\s*80/)).toBeInTheDocument()
    expect(screen.getByText(/Credibility:\s*76/)).toBeInTheDocument()
  })

  it('renders all 7 green-transition dimension labels when dimension scores are present', async () => {
    render(<MapCountryPanel countryCode="FI" onClose={vi.fn()} />)
    await openCompareTab()

    await waitFor(() => {
      expect(screen.getByText('Green Transition Dimensions')).toBeInTheDocument()
    })

    const expectedLabels = [
      'Green Transition',
      'Renewable Energy',
      'Cleantech',
      'Circular Economy',
      'Resource Efficiency',
      'Regenerative',
      'Sustainability',
    ]
    for (const label of expectedLabels) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('renders the 7-axis comparison radar when both country_a and country_b are present', async () => {
    render(<MapCountryPanel countryCode="FI" onClose={vi.fn()} />)
    await openCompareTab()

    // The radar section header is shown only when both country_a + country_b
    // are returned, and the ResponsiveContainer wrapper is mounted.
    // (recharts itself does not render axis text in jsdom, so we assert on
    // the wrapper + heading rather than the SVG text nodes.)
    await waitFor(() => {
      expect(screen.getByText('Comparison Radar')).toBeInTheDocument()
    })
    expect(screen.getByTestId('recharts-responsive')).toBeInTheDocument()
  })

  it('renders the comparison summary text when the API returns one', async () => {
    render(<MapCountryPanel countryCode="FI" onClose={vi.fn()} />)
    await openCompareTab()

    await waitFor(() => {
      expect(
        screen.getByText('Both Finland and Sweden lead in green transition.')
      ).toBeInTheDocument()
    })
  })
})
