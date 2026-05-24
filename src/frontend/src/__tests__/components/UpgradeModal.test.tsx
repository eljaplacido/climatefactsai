import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import UpgradeModal, { type UpgradeModalQuotaEnvelope } from '@/components/UpgradeModal'

// Stub Next.js Link so the tests run without a router.
vi.mock('next/link', () => ({
  default: ({ children, href, ...rest }: any) =>
    React.createElement('a', { href, ...rest }, children),
}))

const MONTHLY_QUOTA: UpgradeModalQuotaEnvelope = {
  quota_key: 'deep_research',
  used: 2,
  limit: 2,
  period: 'monthly',
  reset_at: '2026-06-01T00:00:00+00:00',
  upgrade_url: '/dashboard/subscription',
  tier: 'freemium',
  label: 'deep research queries',
}

const LIFETIME_QUOTA: UpgradeModalQuotaEnvelope = {
  quota_key: 'saved_articles',
  used: 3,
  limit: 3,
  period: 'lifetime',
  reset_at: null,
  upgrade_url: '/dashboard/subscription',
  tier: 'freemium',
  label: 'saved articles',
}

describe('UpgradeModal — Phase 2A 429 surface', () => {
  it('renders nothing when quota is null (closed state)', () => {
    const { container } = render(
      <UpgradeModal quota={null} onClose={vi.fn()} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the quota key label in the title', () => {
    render(<UpgradeModal quota={MONTHLY_QUOTA} onClose={vi.fn()} />)
    expect(screen.getByText(/You've reached your deep research queries limit/)).toBeInTheDocument()
  })

  it('shows the tier under the title', () => {
    render(<UpgradeModal quota={MONTHLY_QUOTA} onClose={vi.fn()} />)
    expect(screen.getByTestId('upgrade-modal-tier')).toHaveTextContent('freemium')
  })

  it('renders used/limit as "X / Y"', () => {
    render(<UpgradeModal quota={MONTHLY_QUOTA} onClose={vi.fn()} />)
    expect(screen.getByTestId('upgrade-modal-used')).toHaveTextContent('2 / 2')
  })

  it('renders the reset date for monthly quotas', () => {
    render(<UpgradeModal quota={MONTHLY_QUOTA} onClose={vi.fn()} />)
    const reset = screen.getByTestId('upgrade-modal-reset')
    expect(reset.textContent).toMatch(/Resets on/)
    // Date is formatted via toLocaleDateString — just assert "June" appears
    expect(reset.textContent).toMatch(/June|Jun/)
  })

  it('renders "Lifetime cap" copy for lifetime quotas', () => {
    render(<UpgradeModal quota={LIFETIME_QUOTA} onClose={vi.fn()} />)
    expect(screen.getByTestId('upgrade-modal-reset')).toHaveTextContent('Lifetime cap on the free tier')
  })

  it('renders the optional backend message when provided', () => {
    render(
      <UpgradeModal
        quota={MONTHLY_QUOTA}
        message="You've used 2 of 2 deep research queries this month. Upgrade for more."
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByText(/Upgrade for more/)).toBeInTheDocument()
  })

  it('upgrade CTA links to quota.upgrade_url', () => {
    render(<UpgradeModal quota={MONTHLY_QUOTA} onClose={vi.fn()} />)
    const cta = screen.getByTestId('upgrade-modal-upgrade-cta')
    expect(cta).toHaveAttribute('href', '/dashboard/subscription')
    expect(cta).toHaveTextContent('See plans')
  })

  it('invokes onClose when "Got it" is clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<UpgradeModal quota={MONTHLY_QUOTA} onClose={onClose} />)
    await user.click(screen.getByTestId('upgrade-modal-dismiss'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('invokes onClose when X-close is clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<UpgradeModal quota={MONTHLY_QUOTA} onClose={onClose} />)
    await user.click(screen.getByTestId('upgrade-modal-close'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('invokes onClose when Escape is pressed', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<UpgradeModal quota={MONTHLY_QUOTA} onClose={onClose} />)
    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
  })

  it('invokes onClose when backdrop is clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<UpgradeModal quota={MONTHLY_QUOTA} onClose={onClose} />)
    await user.click(screen.getByTestId('upgrade-modal'))
    expect(onClose).toHaveBeenCalled()
  })

  it('does NOT close when clicking inside the dialog body', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<UpgradeModal quota={MONTHLY_QUOTA} onClose={onClose} />)
    await user.click(screen.getByTestId('upgrade-modal-used'))
    expect(onClose).not.toHaveBeenCalled()
  })

  it('focuses the dismiss button on open for keyboard a11y', async () => {
    render(<UpgradeModal quota={MONTHLY_QUOTA} onClose={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByTestId('upgrade-modal-dismiss')).toHaveFocus()
    })
  })

  it('upgrade CTA also closes the modal on click (so the user sees the plans page)', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<UpgradeModal quota={MONTHLY_QUOTA} onClose={onClose} />)
    await user.click(screen.getByTestId('upgrade-modal-upgrade-cta'))
    expect(onClose).toHaveBeenCalled()
  })

  it('exposes role=dialog + aria-modal=true', () => {
    render(<UpgradeModal quota={MONTHLY_QUOTA} onClose={vi.fn()} />)
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
  })
})
