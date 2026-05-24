import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatActionConfirmModal from '@/components/ChatActionConfirmModal'
import type { ChatActionSpec } from '@/lib/chatActionDispatcher'

const BOOKMARK_ACTION: ChatActionSpec = {
  type: 'bookmark_article',
  params: { article_id: 'art-42' },
  label: 'Save article',
}

const ANALYZE_ACTION: ChatActionSpec = {
  type: 'analyze_url',
  params: { url: 'https://example.com/climate-story' },
  label: 'Analyse URL',
}

describe('ChatActionConfirmModal — Phase 1C destructive-action gate', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders nothing when action is null', () => {
    const { container } = render(
      <ChatActionConfirmModal action={null} onConfirm={vi.fn()} onCancel={vi.fn()} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing for auto-mode actions (defensive — they should never reach the modal)', () => {
    const navAction: ChatActionSpec = {
      type: 'navigate',
      params: { path: '/map' },
      label: 'Open map',
    }
    render(<ChatActionConfirmModal action={navAction} onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.queryByTestId('chat-action-confirm-modal')).not.toBeInTheDocument()
  })

  it('renders the title, message, and CTA for bookmark_article', () => {
    render(
      <ChatActionConfirmModal
        action={BOOKMARK_ACTION}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.getByTestId('chat-action-confirm-modal')).toBeInTheDocument()
    expect(screen.getByText('Save this article?')).toBeInTheDocument()
    expect(screen.getByText(/saved-articles quota/)).toBeInTheDocument()
    expect(screen.getByTestId('chat-action-confirm')).toHaveTextContent('Save article')
  })

  it('renders the analyze_url message with the URL interpolated', () => {
    render(
      <ChatActionConfirmModal
        action={ANALYZE_ACTION}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    // URL appears in BOTH the message paragraph and the technical-details
    // <pre> block — that's intentional. Use getAllByText since both
    // surfaces are part of the spec.
    const urlMatches = screen.getAllByText(/https:\/\/example\.com\/climate-story/)
    expect(urlMatches.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByTestId('chat-action-confirm')).toHaveTextContent('Analyse URL')
  })

  it('invokes onConfirm when the confirm button is clicked', async () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    const user = userEvent.setup()
    render(
      <ChatActionConfirmModal
        action={BOOKMARK_ACTION}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    )
    await user.click(screen.getByTestId('chat-action-confirm'))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onCancel).not.toHaveBeenCalled()
  })

  it('invokes onCancel when the cancel button is clicked', async () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    const user = userEvent.setup()
    render(
      <ChatActionConfirmModal
        action={BOOKMARK_ACTION}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    )
    await user.click(screen.getByTestId('chat-action-cancel'))
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('invokes onCancel when Escape is pressed', async () => {
    const onCancel = vi.fn()
    const user = userEvent.setup()
    render(
      <ChatActionConfirmModal
        action={BOOKMARK_ACTION}
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    )
    await user.keyboard('{Escape}')
    expect(onCancel).toHaveBeenCalled()
  })

  it('invokes onCancel when the X (close) button is clicked', async () => {
    const onCancel = vi.fn()
    const user = userEvent.setup()
    render(
      <ChatActionConfirmModal
        action={BOOKMARK_ACTION}
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    )
    // X-close button has aria-label="Close dialog" (distinct from the
    // text Cancel button so getByTestId disambiguates cleanly).
    await user.click(screen.getByTestId('chat-action-modal-close'))
    expect(onCancel).toHaveBeenCalled()
  })

  it('exposes role=dialog and aria-modal=true (a11y)', () => {
    render(
      <ChatActionConfirmModal
        action={BOOKMARK_ACTION}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAttribute('aria-labelledby', 'chat-action-confirm-title')
  })

  it('focuses the confirm button on open (keyboard users confirm with Enter)', async () => {
    render(
      <ChatActionConfirmModal
        action={BOOKMARK_ACTION}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    await waitFor(() => {
      expect(screen.getByTestId('chat-action-confirm')).toHaveFocus()
    })
  })

  it('exposes the raw action params under a collapsed details element', async () => {
    render(
      <ChatActionConfirmModal
        action={ANALYZE_ACTION}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    const summary = screen.getByText('Show technical details')
    expect(summary).toBeInTheDocument()
    // The <pre> JSON is inside the details — present in DOM even when collapsed
    expect(screen.getByText(/"type": "analyze_url"/)).toBeInTheDocument()
    expect(screen.getByText(/"url": "https:\/\/example\.com\/climate-story"/)).toBeInTheDocument()
  })

  it('invokes onCancel when the backdrop is clicked', async () => {
    const onCancel = vi.fn()
    const user = userEvent.setup()
    render(
      <ChatActionConfirmModal
        action={BOOKMARK_ACTION}
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    )
    // The modal root IS the backdrop (clicking it triggers onCancel)
    const modal = screen.getByTestId('chat-action-confirm-modal')
    await user.click(modal)
    expect(onCancel).toHaveBeenCalled()
  })

  it('does NOT cancel when clicking inside the dialog body', async () => {
    const onCancel = vi.fn()
    const user = userEvent.setup()
    render(
      <ChatActionConfirmModal
        action={BOOKMARK_ACTION}
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    )
    // Click the dialog title (which is inside the body) — must NOT cancel
    await user.click(screen.getByText('Save this article?'))
    expect(onCancel).not.toHaveBeenCalled()
  })
})
