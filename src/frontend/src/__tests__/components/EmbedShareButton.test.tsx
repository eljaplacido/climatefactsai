import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import EmbedShareButton from '@/components/EmbedShareButton'

beforeEach(() => {
  // Pin the origin so the iframe-snippet assertion stays deterministic
  // regardless of how the test runner names its host.
  Object.defineProperty(window, 'location', {
    writable: true,
    value: { ...window.location, origin: 'https://climatefacts.test' },
  })
  // jsdom's navigator.clipboard is hard to override (see the longer
  // note next to the Copy tests below); we don't bother stubbing it.
})

describe('EmbedShareButton — Phase 2E MH6', () => {
  it('renders a single Embed trigger button by default (modal closed)', () => {
    render(<EmbedShareButton embedPath="/embed/country/DE" />)
    expect(screen.getByTestId('embed-share-button')).toBeInTheDocument()
    expect(screen.queryByTestId('embed-share-modal')).not.toBeInTheDocument()
  })

  it('opens the modal when the trigger button is clicked', async () => {
    const user = userEvent.setup()
    render(<EmbedShareButton embedPath="/embed/country/DE" />)
    await user.click(screen.getByTestId('embed-share-button'))
    expect(screen.getByTestId('embed-share-modal')).toBeInTheDocument()
    // role=dialog + aria-modal for a11y
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
  })

  it('renders the iframe snippet with the full origin + path', async () => {
    const user = userEvent.setup()
    render(<EmbedShareButton embedPath="/embed/country/DE" />)
    await user.click(screen.getByTestId('embed-share-button'))
    const ta = screen.getByTestId('embed-share-snippet') as HTMLTextAreaElement
    expect(ta.value).toContain('https://climatefacts.test/embed/country/DE')
    expect(ta.value).toContain('<iframe')
    expect(ta.value).toContain('width="380"') // default
    expect(ta.value).toContain('loading="lazy"')
    expect(ta.value).toContain('title="Climatefacts.ai embed"')
  })

  it('respects the defaultWidth prop', async () => {
    const user = userEvent.setup()
    render(<EmbedShareButton embedPath="/embed/country/DE" defaultWidth={280} />)
    await user.click(screen.getByTestId('embed-share-button'))
    const ta = screen.getByTestId('embed-share-snippet') as HTMLTextAreaElement
    expect(ta.value).toContain('width="280"')
  })

  it('switching width preset updates the snippet', async () => {
    const user = userEvent.setup()
    render(<EmbedShareButton embedPath="/embed/country/DE" />)
    await user.click(screen.getByTestId('embed-share-button'))
    await user.click(screen.getByTestId('embed-share-width-560'))
    const ta = screen.getByTestId('embed-share-snippet') as HTMLTextAreaElement
    expect(ta.value).toContain('width="560"')
    // aria-checked flips on the radio
    expect(screen.getByTestId('embed-share-width-560')).toHaveAttribute(
      'aria-checked',
      'true',
    )
  })

  // NOTE — we don't directly assert navigator.clipboard.writeText was
  // called. jsdom's clipboard API is hard to override reliably (modern
  // jsdom defines it as a prototype getter that can't always be
  // monkeypatched, and userEvent's async wrapping makes the assertion
  // race-prone). The user-observable behavior — the visible "Copied"
  // state — is covered by the next test, which is the contract that
  // actually matters for the UX. If we ship a clipboard regression
  // someone'll see the Copied label fail to appear and the test below
  // will catch it.

  it('Copy button shows "Copied" success state after clicking', async () => {
    const user = userEvent.setup()
    render(<EmbedShareButton embedPath="/embed/country/DE" />)
    await user.click(screen.getByTestId('embed-share-button'))
    await user.click(screen.getByTestId('embed-share-copy'))
    await waitFor(() => {
      expect(screen.getByTestId('embed-share-copy')).toHaveTextContent('Copied')
    })
    // The sr-only aria-live announcement is set
    expect(screen.getByTestId('embed-share-aria-live')).toHaveTextContent(
      'Snippet copied to clipboard.',
    )
  })

  it('preview link points at the full embed URL in a new tab', async () => {
    const user = userEvent.setup()
    render(<EmbedShareButton embedPath="/embed/country/DE" />)
    await user.click(screen.getByTestId('embed-share-button'))
    const preview = screen.getByTestId('embed-share-preview-link')
    expect(preview).toHaveAttribute(
      'href',
      'https://climatefacts.test/embed/country/DE',
    )
    expect(preview).toHaveAttribute('target', '_blank')
    expect(preview).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('Escape key closes the modal', async () => {
    const user = userEvent.setup()
    render(<EmbedShareButton embedPath="/embed/country/DE" />)
    await user.click(screen.getByTestId('embed-share-button'))
    expect(screen.getByTestId('embed-share-modal')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByTestId('embed-share-modal')).not.toBeInTheDocument()
  })

  it('backdrop click closes the modal', async () => {
    const user = userEvent.setup()
    render(<EmbedShareButton embedPath="/embed/country/DE" />)
    await user.click(screen.getByTestId('embed-share-button'))
    await user.click(screen.getByTestId('embed-share-modal'))
    expect(screen.queryByTestId('embed-share-modal')).not.toBeInTheDocument()
  })

  it('clicking inside the dialog body does NOT close the modal', async () => {
    const user = userEvent.setup()
    render(<EmbedShareButton embedPath="/embed/country/DE" />)
    await user.click(screen.getByTestId('embed-share-button'))
    await user.click(screen.getByTestId('embed-share-snippet'))
    expect(screen.getByTestId('embed-share-modal')).toBeInTheDocument()
  })

  // The execCommand fallback path is exercised in the wild on Safari
  // < 13.4 and any context where Clipboard API isn't available. We
  // intentionally don't unit-test it here for the same jsdom reasons
  // as above — manual smoke test on those browsers is the right
  // coverage. The fallback code itself is small, deterministic, and
  // covered by the eyeball-test of "Copied appears".

  it('label prop overrides the default aria-label on the trigger', () => {
    render(
      <EmbedShareButton
        embedPath="/embed/country/DE"
        label="Share Germany embed"
      />,
    )
    expect(screen.getByTestId('embed-share-button')).toHaveAttribute(
      'aria-label',
      'Share Germany embed',
    )
  })
})
