import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import MapAgenticChat from '@/components/map/MapAgenticChat'

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

function mockMapQueryOnce(payload: Record<string, any>, ok = true) {
  const fn = vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    json: () => Promise.resolve(payload),
  } as Response)
  vi.spyOn(global, 'fetch').mockImplementation(fn as any)
  return fn
}

function expand() {
  // Header button toggles the chat open
  fireEvent.click(screen.getByText('Climate Intelligence Chat'))
}

function submit(text: string) {
  const input = screen.getByPlaceholderText('Ask about climate news...') as HTMLInputElement
  fireEvent.change(input, { target: { value: text } })
  // The form contains a submit button as the last button
  const form = input.closest('form')!
  fireEvent.submit(form)
}

describe('MapAgenticChat — props plumbing', () => {
  it('includes view_context.country and countries: [selectedCountry] when one country is selected', async () => {
    const fetchMock = mockMapQueryOnce({
      answer: 'Finland summary',
      country_highlights: [{ country_code: 'FI' }],
      matching_articles_detail: [],
      session_id: 's-1',
    })

    const onHighlight = vi.fn()
    render(
      <MapAgenticChat
        onHighlightCountries={onHighlight}
        selectedCountry="FI"
      />
    )
    expand()
    submit('What is happening in Finland?')

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toMatch(/\/api\/map\/query$/)
    const body = JSON.parse((init as RequestInit).body as string)
    expect(body.query).toBe('What is happening in Finland?')
    expect(body.countries).toEqual(['FI'])
    expect(body.view_context).toBeDefined()
    expect(body.view_context.country).toBe('FI')
    expect(body.view_context.route).toBe('/map')
  })

  it('includes view_context.compare_countries when compareCountries is provided', async () => {
    const fetchMock = mockMapQueryOnce({
      answer: 'Comparing FI vs SE',
      country_highlights: [
        { country_code: 'FI' },
        { country_code: 'SE' },
      ],
      matching_articles_detail: [],
      session_id: 's-2',
    })

    render(
      <MapAgenticChat
        onHighlightCountries={vi.fn()}
        compareCountries={['FI', 'SE']}
      />
    )
    expand()
    submit('Compare these')

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)
    expect(body.view_context.compare_countries).toEqual(['FI', 'SE'])
    // No country/countries field expected when no single selectedCountry
    expect(body.countries).toBeUndefined()
    expect(body.view_context.country).toBeUndefined()
  })

  it('omits view_context.compare_countries when prop is empty', async () => {
    const fetchMock = mockMapQueryOnce({
      answer: 'no compare',
      country_highlights: [],
      matching_articles_detail: [],
    })
    render(
      <MapAgenticChat
        onHighlightCountries={vi.fn()}
        compareCountries={[]}
      />
    )
    expand()
    submit('Generic question')

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)
    expect(body.view_context.compare_countries).toBeUndefined()
  })

  it('forwards highlighted country codes to onHighlightCountries callback', async () => {
    mockMapQueryOnce({
      answer: 'highlighted',
      country_highlights: [
        { country_code: 'FI' },
        { country_code: 'SE' },
      ],
      matching_articles_detail: [],
    })
    const onHighlight = vi.fn()
    render(
      <MapAgenticChat
        onHighlightCountries={onHighlight}
        selectedCountry="FI"
      />
    )
    expand()
    submit('Show highlights')

    await waitFor(() => expect(onHighlight).toHaveBeenCalledWith(['FI', 'SE']))
  })
})
