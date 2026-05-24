import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: any) =>
    React.createElement('a', { href, ...props }, children),
}))

// useAuth mock — controllable per-test via a ref so we can flip
// isLoggedIn between cases.
const authMock = {
  isLoggedIn: true,
  token: 'tok-test',
}
vi.mock('@/lib/auth', () => ({
  useAuth: () => authMock,
}))

import AOIManagementPage from '@/app/dashboard/aoi/page'

const FIXTURE_SUBS = [
  {
    subscription_id: 'sub-1',
    country_code: 'DE',
    variable: 'renewable_share_pct',
    comparison: 'gte',
    threshold: 50,
    delivery_channel: 'email',
    active: true,
    last_fired_at: '2026-05-23T10:00:00Z',
    last_observed_value: 52.5,
    fire_count: 3,
    label: 'Germany renewables milestone',
    created_at: '2026-05-20T00:00:00Z',
  },
  {
    subscription_id: 'sub-2',
    country_code: 'BR',
    variable: 'co2_emissions_per_capita',
    comparison: 'gt',
    threshold: 5,
    delivery_channel: 'email',
    active: true,
    last_fired_at: null,
    last_observed_value: null,
    fire_count: 0,
    label: null,
    created_at: '2026-05-22T00:00:00Z',
  },
]

beforeEach(() => {
  vi.restoreAllMocks()
  authMock.isLoggedIn = true
  authMock.token = 'tok-test'
})

function mockFetch(impl: (url: string, init?: any) => Promise<any>) {
  ;(global as any).fetch = vi.fn(impl)
}

describe('AOI management page — Phase 5A', () => {
  it('shows sign-in prompt when not logged in', () => {
    authMock.isLoggedIn = false
    authMock.token = null as any
    render(<AOIManagementPage />)
    expect(screen.getByText(/Sign in to manage/i)).toBeInTheDocument()
  })

  it('shows loading spinner while fetching', () => {
    mockFetch(() => new Promise(() => {})) // never resolves
    render(<AOIManagementPage />)
    expect(screen.getByTestId('aoi-management-loading')).toBeInTheDocument()
  })

  it('shows empty state when API returns no subscriptions', async () => {
    mockFetch(async () => ({
      ok: true,
      status: 200,
      json: async () => [],
    }))
    render(<AOIManagementPage />)
    await waitFor(() =>
      expect(screen.getByTestId('aoi-management-empty')).toBeInTheDocument(),
    )
    expect(screen.getByText(/No active alerts yet/i)).toBeInTheDocument()
  })

  it('renders each subscription with rule + last-fired + fire-count', async () => {
    mockFetch(async () => ({
      ok: true,
      status: 200,
      json: async () => FIXTURE_SUBS,
    }))
    render(<AOIManagementPage />)
    await waitFor(() => {
      expect(screen.getAllByTestId('aoi-management-row')).toHaveLength(2)
    })
    // Row 1 — Germany renewables
    const row1 = screen.getByText('Germany renewables milestone').closest(
      '[data-testid="aoi-management-row"]',
    )
    expect(row1).toBeInTheDocument()
    expect(row1!.textContent).toContain('DE')
    expect(row1!.textContent).toContain('Renewable share')
    expect(row1!.textContent).toContain('50')
    // fire_count surfaced
    expect(row1!.textContent).toMatch(/Fires:.*3/i)
    // last_observed_value surfaced
    expect(row1!.textContent).toMatch(/Last value:.*52\.5/i)
  })

  it('row links to /country/{code}', async () => {
    mockFetch(async () => ({ ok: true, status: 200, json: async () => FIXTURE_SUBS }))
    render(<AOIManagementPage />)
    await waitFor(() => expect(screen.getAllByTestId('aoi-management-row')).toHaveLength(2))
    // Find the DE link
    const links = screen.getAllByRole('link')
    const deLink = links.find((l) => l.getAttribute('href') === '/country/DE')
    expect(deLink).toBeDefined()
  })

  it('renders "—" for never-fired subscription', async () => {
    mockFetch(async () => ({ ok: true, status: 200, json: async () => [FIXTURE_SUBS[1]] }))
    render(<AOIManagementPage />)
    await waitFor(() => expect(screen.getByTestId('aoi-management-row')).toBeInTheDocument())
    const row = screen.getByTestId('aoi-management-row')
    expect(row.textContent).toContain('—')
    expect(row.textContent).toMatch(/Fires:.*0/i)
  })

  it('delete button fires DELETE and removes the row optimistically', async () => {
    const deleteCall = vi.fn().mockResolvedValue({ ok: true, status: 204 })
    mockFetch(async (url, init) => {
      if (init?.method === 'DELETE') return deleteCall(url, init)
      return { ok: true, status: 200, json: async () => FIXTURE_SUBS }
    })
    const user = userEvent.setup()
    render(<AOIManagementPage />)
    await waitFor(() => expect(screen.getAllByTestId('aoi-management-row')).toHaveLength(2))
    // Click the first delete button
    const deleteButtons = screen.getAllByTestId('aoi-management-delete')
    await user.click(deleteButtons[0])
    await waitFor(() => expect(deleteCall).toHaveBeenCalled())
    const [url, init] = deleteCall.mock.calls[0]
    expect(url).toContain('/api/aoi-subscriptions/sub-1')
    expect(init.method).toBe('DELETE')
    // Optimistic removal
    await waitFor(() => {
      expect(screen.getAllByTestId('aoi-management-row')).toHaveLength(1)
    })
  })

  it('shows error banner when DELETE fails', async () => {
    mockFetch(async (url, init) => {
      if (init?.method === 'DELETE') {
        return { ok: false, status: 500 }
      }
      return { ok: true, status: 200, json: async () => FIXTURE_SUBS }
    })
    const user = userEvent.setup()
    render(<AOIManagementPage />)
    await waitFor(() => expect(screen.getAllByTestId('aoi-management-row')).toHaveLength(2))
    await user.click(screen.getAllByTestId('aoi-management-delete')[0])
    await waitFor(() => {
      expect(screen.getByTestId('aoi-management-error')).toBeInTheDocument()
    })
    // Row NOT removed when delete failed
    expect(screen.getAllByTestId('aoi-management-row')).toHaveLength(2)
  })

  it('shows error banner when initial fetch fails', async () => {
    mockFetch(async () => ({ ok: false, status: 500 }))
    render(<AOIManagementPage />)
    await waitFor(() => {
      expect(screen.getByTestId('aoi-management-error')).toBeInTheDocument()
    })
  })

  it('aria-label on delete button is descriptive', async () => {
    mockFetch(async () => ({ ok: true, status: 200, json: async () => FIXTURE_SUBS }))
    render(<AOIManagementPage />)
    await waitFor(() => expect(screen.getAllByTestId('aoi-management-row')).toHaveLength(2))
    const deletes = screen.getAllByTestId('aoi-management-delete')
    expect(deletes[0]).toHaveAttribute(
      'aria-label',
      expect.stringContaining('Delete alert for DE renewable_share_pct'),
    )
  })
})
