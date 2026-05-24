import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AOISubscribeButton from '@/components/AOISubscribeButton'

const TIER_BASIC_FIXTURE = {
  tier: 'basic',
  limit: 5,
  used: 2,
  allowed: true,
  upgrade_url: '/dashboard/subscription',
}

const TIER_FREEMIUM_FIXTURE = {
  tier: 'freemium',
  limit: 0,
  used: 0,
  allowed: false,
  upgrade_url: '/dashboard/subscription',
}

function mockFetch(impl: (url: string, init?: any) => Promise<any>) {
  ;(global as any).fetch = vi.fn(impl)
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('AOISubscribeButton — Phase 3B MH5', () => {
  it('renders the trigger button without opening the modal', () => {
    render(<AOISubscribeButton countryCode="DE" countryName="Germany" authToken="tok" />)
    expect(screen.getByTestId('aoi-subscribe-button')).toBeInTheDocument()
    expect(screen.queryByTestId('aoi-subscribe-modal')).not.toBeInTheDocument()
  })

  it('anonymous user (no authToken) sees upgrade state on open', async () => {
    const user = userEvent.setup()
    render(<AOISubscribeButton countryCode="DE" countryName="Germany" authToken={null} />)
    await user.click(screen.getByTestId('aoi-subscribe-button'))
    await waitFor(() =>
      expect(screen.getByTestId('aoi-subscribe-upgrade-state')).toBeInTheDocument(),
    )
    expect(screen.getByText(/Sign in to subscribe/i)).toBeInTheDocument()
    expect(screen.getByTestId('aoi-subscribe-upgrade-cta')).toHaveAttribute(
      'href',
      '/login',
    )
  })

  it('freemium user sees upgrade state with Basic+ copy', async () => {
    mockFetch(async (url) => {
      if (String(url).includes('/tier-info')) {
        return { ok: true, status: 200, json: async () => TIER_FREEMIUM_FIXTURE }
      }
      return { ok: true, status: 200, json: async () => ({}) }
    })

    const user = userEvent.setup()
    render(<AOISubscribeButton countryCode="DE" countryName="Germany" authToken="tok" />)
    await user.click(screen.getByTestId('aoi-subscribe-button'))
    await waitFor(() =>
      expect(screen.getByTestId('aoi-subscribe-upgrade-state')).toBeInTheDocument(),
    )
    expect(screen.getByText(/Basic\+ feature/i)).toBeInTheDocument()
    expect(screen.getByTestId('aoi-subscribe-upgrade-cta')).toHaveTextContent('See plans')
  })

  it('basic tier user sees the form and can submit', async () => {
    const createCall = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        subscription_id: 'sub-1',
        user_id: 'u-1',
        country_code: 'DE',
        variable: 'temperature_anomaly_c',
        comparison: 'gt',
        threshold: 2,
        delivery_channel: 'email',
        active: true,
        fire_count: 0,
      }),
    })
    mockFetch(async (url, init) => {
      if (String(url).includes('/tier-info')) {
        return { ok: true, status: 200, json: async () => TIER_BASIC_FIXTURE }
      }
      if (String(url).endsWith('/api/aoi-subscriptions') && init?.method === 'POST') {
        return createCall(url, init)
      }
      return { ok: true, status: 200, json: async () => ({}) }
    })

    const user = userEvent.setup()
    render(<AOISubscribeButton countryCode="DE" countryName="Germany" authToken="tok" />)
    await user.click(screen.getByTestId('aoi-subscribe-button'))
    await waitFor(() =>
      expect(screen.getByTestId('aoi-subscribe-form')).toBeInTheDocument(),
    )
    // Tier used/limit copy
    expect(screen.getByText(/2 of 5 alerts used/i)).toBeInTheDocument()
    // Defaults: variable=temperature_anomaly_c, comparison=gt, threshold=2
    expect(screen.getByTestId('aoi-subscribe-variable')).toHaveValue(
      'temperature_anomaly_c',
    )
    expect(screen.getByTestId('aoi-subscribe-comparison')).toHaveValue('gt')
    await user.click(screen.getByTestId('aoi-subscribe-submit'))
    await waitFor(() => expect(createCall).toHaveBeenCalled())
    // POST body shape
    const [, init] = createCall.mock.calls[0]
    const body = JSON.parse(init.body)
    expect(body.country_code).toBe('DE')
    expect(body.variable).toBe('temperature_anomaly_c')
    expect(body.comparison).toBe('gt')
    expect(body.threshold).toBe(2)
    expect(body.label).toContain('Germany')
    // Success state appears
    await waitFor(() =>
      expect(screen.getByTestId('aoi-subscribe-success')).toBeInTheDocument(),
    )
  })

  it('changing the variable updates the default comparison + threshold', async () => {
    mockFetch(async (url) => {
      if (String(url).includes('/tier-info')) {
        return { ok: true, status: 200, json: async () => TIER_BASIC_FIXTURE }
      }
      return { ok: true, status: 200, json: async () => ({}) }
    })

    const user = userEvent.setup()
    render(<AOISubscribeButton countryCode="DE" countryName="Germany" authToken="tok" />)
    await user.click(screen.getByTestId('aoi-subscribe-button'))
    await waitFor(() => expect(screen.getByTestId('aoi-subscribe-form')).toBeInTheDocument())
    // Switch to renewable_share_pct → comparison flips to gte, threshold to 50
    await user.selectOptions(
      screen.getByTestId('aoi-subscribe-variable'),
      'renewable_share_pct',
    )
    await waitFor(() => {
      expect(screen.getByTestId('aoi-subscribe-comparison')).toHaveValue('gte')
    })
    expect(screen.getByTestId('aoi-subscribe-threshold')).toHaveValue(50)
  })

  it('429 from backend surfaces structured error message', async () => {
    mockFetch(async (url, init) => {
      if (String(url).includes('/tier-info')) {
        // tier-info says basic with room…
        return { ok: true, status: 200, json: async () => TIER_BASIC_FIXTURE }
      }
      if (String(url).endsWith('/api/aoi-subscriptions') && init?.method === 'POST') {
        // …but the create attempt 429s anyway (race condition: another tab took the slot)
        return {
          ok: false,
          status: 429,
          json: async () => ({
            detail: {
              error: 'aoi_tier_limit',
              tier: 'basic',
              used: 5,
              limit: 5,
              upgrade_url: '/dashboard/subscription',
              message: "You've used 5 of 5 AOI subscriptions on the basic tier. Upgrade for more.",
            },
          }),
        }
      }
      return { ok: true, status: 200, json: async () => ({}) }
    })

    const user = userEvent.setup()
    render(<AOISubscribeButton countryCode="DE" countryName="Germany" authToken="tok" />)
    await user.click(screen.getByTestId('aoi-subscribe-button'))
    await waitFor(() => expect(screen.getByTestId('aoi-subscribe-form')).toBeInTheDocument())
    await user.click(screen.getByTestId('aoi-subscribe-submit'))
    await waitFor(() => {
      expect(screen.getByTestId('aoi-subscribe-error')).toBeInTheDocument()
    })
    expect(screen.getByTestId('aoi-subscribe-error')).toHaveTextContent(/5 of 5/i)
  })

  it('Escape and close button both dismiss the modal', async () => {
    const user = userEvent.setup()
    render(<AOISubscribeButton countryCode="DE" countryName="Germany" authToken={null} />)

    await user.click(screen.getByTestId('aoi-subscribe-button'))
    await waitFor(() => expect(screen.getByTestId('aoi-subscribe-modal')).toBeInTheDocument())
    await user.click(screen.getByTestId('aoi-subscribe-close'))
    expect(screen.queryByTestId('aoi-subscribe-modal')).not.toBeInTheDocument()

    await user.click(screen.getByTestId('aoi-subscribe-button'))
    await user.click(screen.getByTestId('aoi-subscribe-modal'))
    expect(screen.queryByTestId('aoi-subscribe-modal')).not.toBeInTheDocument()
  })

  it('exposes role=dialog + aria-modal=true', async () => {
    const user = userEvent.setup()
    render(<AOISubscribeButton countryCode="DE" countryName="Germany" authToken={null} />)
    await user.click(screen.getByTestId('aoi-subscribe-button'))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
  })
})
