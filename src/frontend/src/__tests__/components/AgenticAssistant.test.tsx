import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import AgenticAssistant from '@/components/AgenticAssistant'

// jsdom does not implement scrollIntoView; stub it to avoid noisy errors.
beforeEach(() => {
  if (!('scrollIntoView' in HTMLElement.prototype)) {
    // @ts-expect-error - augment for jsdom
    HTMLElement.prototype.scrollIntoView = vi.fn()
  } else {
    HTMLElement.prototype.scrollIntoView = vi.fn() as any
  }
})

afterEach(() => {
  vi.restoreAllMocks()
})

function mockFetchOnce(payload: Record<string, any>, ok = true, status = 200) {
  const fn = vi.fn().mockResolvedValue({
    ok,
    status,
    json: () => Promise.resolve(payload),
  } as Response)
  vi.spyOn(global, 'fetch').mockImplementation(fn as any)
  return fn
}

function expand() {
  // Click the collapsed bar to expand. Slice 3 (2026-05-27) replaced
  // the static hint "Ask about climate news, data, or trends..." with
  // a rotating page-aware example, so target by testid instead.
  const collapsedHint = screen.getByTestId('chat-rotating-example')
  fireEvent.click(collapsedHint)
}

function typeAndSend(text: string) {
  const input = screen.getByPlaceholderText(
    'Ask about climate news, data, or trends...'
  ) as HTMLInputElement
  fireEvent.change(input, { target: { value: text } })
  // Trigger via Enter key — the component's onKeyDown invokes handleSend() with
  // no arguments. Clicking the actual send button passes a SyntheticEvent that
  // the component's `(overrideText ?? input)` ?? short-circuits unsafely.
  fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' })
}

describe('AgenticAssistant', () => {
  it('renders the collapsed bar by default', () => {
    const { container } = render(<AgenticAssistant />)
    // Slice 3 (2026-05-27): the collapsed bar now shows a rotating
    // page-aware example via the chat-rotating-example testid (replaces
    // the old static "Ask about climate news..." hint).
    expect(screen.getByTestId('chat-rotating-example')).toBeInTheDocument()
    // The expanded panel wrapper has opacity-0 + max-h-0 by default
    const expandedWrapper = container.querySelector('.max-h-0.opacity-0')
    expect(expandedWrapper).toBeInTheDocument()
    // The collapsed bar wrapper is "block" (visible), not "hidden"
    const collapsedBar = container.querySelector('.cursor-pointer')
    expect(collapsedBar).toBeInTheDocument()
  })

  it('shows example chips matching currentPage when expanded', () => {
    render(<AgenticAssistant currentPage="map" />)
    expand()
    // Slice 3 (2026-05-27) — the rotating-example label in the collapsed
    // bar contains the SAME text as one of the expanded chips, so
    // getByText finds multiples. Asserting at least one rendered button
    // chip with each expected query.
    expect(
      screen.getAllByText('Biggest climate risks in Southeast Asia?').length
    ).toBeGreaterThan(0)
    expect(
      screen.getAllByText('Compare renewable energy: Europe vs Asia').length
    ).toBeGreaterThan(0)
  })

  it('shows different chips for the articles page', () => {
    render(<AgenticAssistant currentPage="articles" />)
    expand()
    // Slice 3 / chat-as-heart (2026-05-27) — articles-page chips were
    // expanded to nudge users toward the newly-wired skills
    // (explain_connection / flag_off_topic / promote_golden_example).
    expect(
      screen.getAllByText('What are the key scientific claims here?').length
    ).toBeGreaterThan(0)
  })

  it('POSTs to /api/chat with view_context including article_id / country / analysis_id (research mode)', async () => {
    const fetchMock = mockFetchOnce({
      answer: 'Hello world',
      session_id: 's-1',
      sources: [],
    })

    render(
      <AgenticAssistant
        currentPage="deep-search"
        currentAnalysisId="analysis-99"
        currentDeepSearchQuery="arctic ice"
      />
    )
    expand()
    typeAndSend('Tell me more')

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toMatch(/\/api\/chat$/)
    const body = JSON.parse((init as RequestInit).body as string)
    expect(body.question).toBe('Tell me more')
    expect(body.mode).toBe('research_analysis')
    expect(body.view_context).toBeDefined()
    expect(body.view_context.analysis_id).toBe('analysis-99')
    expect(body.view_context.deep_search_query).toBe('arctic ice')
    expect(body.view_context.route).toBe('/deep-search')
  })

  it('POSTs to /api/articles/{id}/ask when currentArticleId is set', async () => {
    const fetchMock = mockFetchOnce({
      answer: 'Article-specific answer',
      session_id: 's-2',
      sources: [],
    })

    render(
      <AgenticAssistant
        currentPage="articles"
        currentArticleId="art-42"
      />
    )
    expand()
    typeAndSend('Is this credible?')

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toMatch(/\/api\/articles\/art-42\/ask$/)
    const body = JSON.parse((init as RequestInit).body as string)
    expect(body.question).toBe('Is this credible?')
    // view_context still flows through with article_id
    expect(body.view_context.article_id).toBe('art-42')
  })

  it('POSTs to /api/map/query with countries [currentCountry] when on map page', async () => {
    const fetchMock = mockFetchOnce({
      answer: 'Finland answer',
      session_id: 's-3',
      sources: [],
    })

    render(
      <AgenticAssistant
        currentPage="map"
        currentCountry="FI"
      />
    )
    expand()
    typeAndSend('How is Finland doing?')

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toMatch(/\/api\/map\/query$/)
    const body = JSON.parse((init as RequestInit).body as string)
    expect(body.query).toBe('How is Finland doing?')
    expect(body.countries).toEqual(['FI'])
    expect(body.view_context).toBeDefined()
    expect(body.view_context.country).toBe('FI')
  })

  it('renders cited articles and highlighted_countries chips from the response', async () => {
    mockFetchOnce({
      answer: 'See these countries.',
      session_id: 's-4',
      sources: [
        { article_id: 'a-1', title: 'Climate report A' },
        { article_id: 'a-2', title: 'Climate report B' },
      ],
      highlighted_countries: ['FI', 'SE'],
    })

    render(<AgenticAssistant currentPage="default" />)
    expand()
    typeAndSend('Show me trends')

    await waitFor(() => {
      expect(screen.getByText('Climate report A')).toBeInTheDocument()
    })
    expect(screen.getByText('Climate report B')).toBeInTheDocument()
    // Highlighted country chips
    expect(screen.getByText('FI')).toBeInTheDocument()
    expect(screen.getByText('SE')).toBeInTheDocument()

    // The cited links should point to the article detail pages
    const citedA = screen.getByText('Climate report A').closest('a')
    expect(citedA).toHaveAttribute('href', '/articles/a-1')
  })

  it('invokes onHighlightCountries callback when response includes highlighted_countries', async () => {
    const onHighlight = vi.fn()
    mockFetchOnce({
      answer: 'highlighted',
      session_id: 's-5',
      highlighted_countries: ['DE'],
    })

    render(
      <AgenticAssistant
        currentPage="default"
        onHighlightCountries={onHighlight}
      />
    )
    expand()
    typeAndSend('any question')

    await waitFor(() => {
      expect(onHighlight).toHaveBeenCalledWith(['DE'])
    })
  })
})
