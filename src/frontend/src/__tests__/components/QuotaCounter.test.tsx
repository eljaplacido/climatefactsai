import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import QuotaCounter from '@/components/QuotaCounter'

// Mock Next Link.
vi.mock('next/link', () => ({
  default: ({ children, href, ...rest }: any) =>
    React.createElement('a', { href, ...rest }, children),
}))

const _buildSummary = (overrides: any = {}) => ({
  tier: 'freemium',
  quotas: [
    {
      quota_key: 'deep_research',
      allowed: true,
      used: 0,
      limit: 2,
      period: 'monthly',
      reset_at: null,
      upgrade_url: '/dashboard/subscription',
      tier: 'freemium',
      label: 'deep research queries',
      ...overrides,
    },
  ],
})

beforeEach(() => {
  vi.restoreAllMocks()
})

function mockFetch(summary: any) {
  ;(global as any).fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => summary,
  })
}

describe('QuotaCounter — Phase 2A inline counter', () => {
  it('renders nothing while loading (no layout shift)', () => {
    ;(global as any).fetch = vi.fn(() => new Promise(() => {})) // never resolves
    const { container } = render(<QuotaCounter quotaKey="deep_research" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing for an unknown key', async () => {
    mockFetch(_buildSummary({ quota_key: 'deep_research' }))
    const { container } = render(<QuotaCounter quotaKey="saved_articles" />)
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    // saved_articles isn't in the summary
    expect(container).toBeEmptyDOMElement()
  })

  it('shows "Unlimited" for limit=-1 by default', async () => {
    mockFetch(_buildSummary({ limit: -1 }))
    render(<QuotaCounter quotaKey="deep_research" />)
    await waitFor(() =>
      expect(screen.getByTestId('quota-counter-deep_research')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('quota-counter-deep_research')).toHaveTextContent('Unlimited')
    expect(screen.getByTestId('quota-counter-deep_research')).toHaveAttribute(
      'data-quota-state',
      'unlimited',
    )
  })

  it('hides itself for unlimited when hideWhenUnlimited=true', async () => {
    mockFetch(_buildSummary({ limit: -1 }))
    const { container } = render(
      <QuotaCounter quotaKey="deep_research" hideWhenUnlimited />,
    )
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('shows OK state when more than half remaining', async () => {
    mockFetch(_buildSummary({ used: 0, limit: 2 }))
    render(<QuotaCounter quotaKey="deep_research" />)
    await waitFor(() =>
      expect(screen.getByTestId('quota-counter-deep_research')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('quota-counter-deep_research')).toHaveAttribute(
      'data-quota-state',
      'ok',
    )
  })

  it('shows LOW state when less than half remaining (warning amber)', async () => {
    mockFetch(_buildSummary({ used: 4, limit: 5 }))
    render(<QuotaCounter quotaKey="deep_research" />)
    await waitFor(() =>
      expect(screen.getByTestId('quota-counter-deep_research')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('quota-counter-deep_research')).toHaveAttribute(
      'data-quota-state',
      'low',
    )
  })

  it('shows EXHAUSTED state with inline Upgrade link when 0 remaining', async () => {
    mockFetch(_buildSummary({ used: 2, limit: 2 }))
    render(<QuotaCounter quotaKey="deep_research" />)
    await waitFor(() =>
      expect(screen.getByTestId('quota-counter-deep_research')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('quota-counter-deep_research')).toHaveAttribute(
      'data-quota-state',
      'exhausted',
    )
    const upgradeLink = screen.getByTestId('quota-counter-deep_research-upgrade')
    expect(upgradeLink).toHaveAttribute('href', '/dashboard/subscription')
    expect(upgradeLink).toHaveTextContent('Upgrade')
  })

  it('exposes remaining + limit as data attributes for downstream consumers', async () => {
    mockFetch(_buildSummary({ used: 1, limit: 3 }))
    render(<QuotaCounter quotaKey="deep_research" />)
    await waitFor(() =>
      expect(screen.getByTestId('quota-counter-deep_research')).toBeInTheDocument(),
    )
    const el = screen.getByTestId('quota-counter-deep_research')
    expect(el).toHaveAttribute('data-quota-remaining', '2')
    expect(el).toHaveAttribute('data-quota-limit', '3')
  })
})
