import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Phase 8 MH4 (2026-05-24) — Projections panel tests.
// Pins the three-scenario / three-horizon contract on the Country Passport.

import ProjectionsPanel from '@/components/ProjectionsPanel'

const PAYLOAD = {
  country_code: 'DE',
  available: true,
  methodology_version: 'ipcc_ar6_atlas_v1',
  citation_url: 'https://interactive-atlas.ipcc.ch/regional-information',
  baseline_note: 'Warming relative to 1850-1900 pre-industrial baseline.',
  scenarios: {
    'SSP1-2.6': [
      { horizon_year: 2030, temp_anomaly_c: 1.5 },
      { horizon_year: 2050, temp_anomaly_c: 1.9 },
      { horizon_year: 2100, temp_anomaly_c: 2.1 },
    ],
    'SSP2-4.5': [
      { horizon_year: 2030, temp_anomaly_c: 1.6 },
      { horizon_year: 2050, temp_anomaly_c: 2.6 },
      { horizon_year: 2100, temp_anomaly_c: 3.6 },
    ],
    'SSP3-7.0': [
      { horizon_year: 2030, temp_anomaly_c: 1.7 },
      { horizon_year: 2050, temp_anomaly_c: 3.1 },
      { horizon_year: 2100, temp_anomaly_c: 5.3 },
    ],
  },
}

const UNAVAILABLE_PAYLOAD = {
  country_code: 'XX',
  available: false,
  methodology_version: null,
  citation_url: null,
  baseline_note: '',
  scenarios: {},
}

beforeEach(() => {
  vi.restoreAllMocks()
})

function mockFetch(payload: any) {
  ;(global as any).fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: async () => payload }),
  )
}

describe('ProjectionsPanel — Phase 8 MH4', () => {
  it('shows a loading state while fetching', () => {
    ;(global as any).fetch = vi.fn(() => new Promise(() => {})) // never resolves
    render(<ProjectionsPanel countryCode="DE" countryName="Germany" />)
    expect(screen.getByTestId('projections-loading')).toBeInTheDocument()
  })

  it('shows an unavailable state when scenarios are empty', async () => {
    mockFetch(UNAVAILABLE_PAYLOAD)
    render(<ProjectionsPanel countryCode="XX" countryName="Unseededland" />)
    await waitFor(() =>
      expect(screen.getByTestId('projections-unavailable')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('projections-unavailable').textContent).toMatch(
      /Unseededland/,
    )
  })

  it('renders three scenario tabs in the canonical order', async () => {
    mockFetch(PAYLOAD)
    render(<ProjectionsPanel countryCode="DE" countryName="Germany" />)
    await waitFor(() =>
      expect(screen.getByTestId('projections-scenario-tabs')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('projections-scenario-SSP1-2.6')).toBeInTheDocument()
    expect(screen.getByTestId('projections-scenario-SSP2-4.5')).toBeInTheDocument()
    expect(screen.getByTestId('projections-scenario-SSP3-7.0')).toBeInTheDocument()
  })

  it('defaults to the SSP2-4.5 middle-path scenario', async () => {
    mockFetch(PAYLOAD)
    render(<ProjectionsPanel countryCode="DE" countryName="Germany" />)
    await waitFor(() =>
      expect(screen.getByTestId('projections-scenario-SSP2-4.5')).toHaveAttribute(
        'aria-selected',
        'true',
      ),
    )
    // The middle-of-the-road values should be visible
    expect(screen.getByTestId('projections-horizon-2030').textContent).toContain(
      '+1.6°C',
    )
    expect(screen.getByTestId('projections-horizon-2050').textContent).toContain(
      '+2.6°C',
    )
    expect(screen.getByTestId('projections-horizon-2100').textContent).toContain(
      '+3.6°C',
    )
  })

  it('clicking a scenario tab swaps the displayed horizons', async () => {
    mockFetch(PAYLOAD)
    const user = userEvent.setup()
    render(<ProjectionsPanel countryCode="DE" countryName="Germany" />)
    await waitFor(() =>
      expect(screen.getByTestId('projections-scenario-tabs')).toBeInTheDocument(),
    )
    // Click the high-emissions scenario
    await user.click(screen.getByTestId('projections-scenario-SSP3-7.0'))
    await waitFor(() =>
      expect(screen.getByTestId('projections-scenario-SSP3-7.0')).toHaveAttribute(
        'aria-selected',
        'true',
      ),
    )
    // SSP3-7.0 high-emissions values for Germany
    expect(screen.getByTestId('projections-horizon-2100').textContent).toContain(
      '+5.3°C',
    )
  })

  it('clicking sustainability scenario shows the lowest values', async () => {
    mockFetch(PAYLOAD)
    const user = userEvent.setup()
    render(<ProjectionsPanel countryCode="DE" countryName="Germany" />)
    await waitFor(() =>
      expect(screen.getByTestId('projections-scenario-tabs')).toBeInTheDocument(),
    )
    await user.click(screen.getByTestId('projections-scenario-SSP1-2.6'))
    await waitFor(() =>
      expect(screen.getByTestId('projections-horizon-2100').textContent).toContain(
        '+2.1°C',
      ),
    )
  })

  it('renders the IPCC AR6 citation link', async () => {
    mockFetch(PAYLOAD)
    render(<ProjectionsPanel countryCode="DE" countryName="Germany" />)
    await waitFor(() => {
      const link = screen.getByText(/IPCC AR6 Interactive Atlas/i)
      expect(link.closest('a')).toHaveAttribute(
        'href',
        'https://interactive-atlas.ipcc.ch/regional-information',
      )
    })
  })

  it('exposes role=tablist for the scenario selector', async () => {
    mockFetch(PAYLOAD)
    render(<ProjectionsPanel countryCode="DE" countryName="Germany" />)
    const tablist = await screen.findByRole('tablist', { name: /Scenario selector/i })
    expect(tablist).toBeInTheDocument()
    // Three tabs with role=tab
    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(3)
  })

  it('exposes the pre-industrial baseline caveat', async () => {
    mockFetch(PAYLOAD)
    render(<ProjectionsPanel countryCode="DE" countryName="Germany" />)
    await waitFor(() =>
      expect(
        screen.getByText(/1850-1900 pre-industrial baseline/),
      ).toBeInTheDocument(),
    )
  })
})
