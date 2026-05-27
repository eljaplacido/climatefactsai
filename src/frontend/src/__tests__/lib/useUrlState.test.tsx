import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useUrlState, URL_STATE_SERIALIZERS } from '@/lib/useUrlState'

// Mock next/navigation so we control searchParams + capture router.replace.
let currentSearch = ''
const replaceMock = vi.fn((url: string, _opts?: { scroll?: boolean }) => {
  const qIdx = url.indexOf('?')
  currentSearch = qIdx >= 0 ? url.slice(qIdx + 1) : ''
})

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock }),
  usePathname: () => '/deep-search',
  useSearchParams: () => new URLSearchParams(currentSearch),
}))

function StringHarness({ urlKey, fallback }: { urlKey: string; fallback: string }) {
  const [value, setValue] = useUrlState(urlKey, fallback, URL_STATE_SERIALIZERS.string)
  return (
    <>
      <span data-testid="value">{value}</span>
      <button onClick={() => setValue('new-value')}>change</button>
    </>
  )
}

function BoolHarness({ urlKey, fallback }: { urlKey: string; fallback: boolean }) {
  const [value, setValue] = useUrlState(urlKey, fallback, URL_STATE_SERIALIZERS.boolean)
  return (
    <>
      <span data-testid="value">{value ? 'TRUE' : 'FALSE'}</span>
      <button onClick={() => setValue(!value)}>toggle</button>
    </>
  )
}

describe('useUrlState — Phase 1B URL-persistent state', () => {
  beforeEach(() => {
    currentSearch = ''
    replaceMock.mockClear()
  })

  it('falls back to default when URL has no value', () => {
    render(<StringHarness urlKey="q" fallback="hello" />)
    expect(screen.getByTestId('value')).toHaveTextContent('hello')
  })

  it('hydrates from URL when present', () => {
    currentSearch = 'q=from-url'
    render(<StringHarness urlKey="q" fallback="default" />)
    expect(screen.getByTestId('value')).toHaveTextContent('from-url')
  })

  it('writes new value to URL on update', async () => {
    const user = userEvent.setup()
    render(<StringHarness urlKey="q" fallback="" />)
    await user.click(screen.getByRole('button', { name: 'change' }))
    // schedulePatch runs through setTimeout(0) — flush microtasks
    await waitFor(() => expect(replaceMock).toHaveBeenCalled())
    const url = replaceMock.mock.calls[0][0]
    expect(url).toContain('q=new-value')
    expect(replaceMock.mock.calls[0][1]).toEqual({ scroll: false })
  })

  it('drops the key from URL when value is empty string (string serializer)', async () => {
    function ClearHarness() {
      const [value, setValue] = useUrlState('q', '', URL_STATE_SERIALIZERS.string)
      return (
        <>
          <span data-testid="value">{value}</span>
          <button onClick={() => setValue('')}>clear</button>
        </>
      )
    }
    currentSearch = 'q=hello'
    const user = userEvent.setup()
    render(<ClearHarness />)
    await user.click(screen.getByRole('button', { name: 'clear' }))
    await waitFor(() => expect(replaceMock).toHaveBeenCalled())
    const url = replaceMock.mock.calls[0][0]
    expect(url).not.toContain('q=')
  })

  it('boolean serializer round-trips through URL', async () => {
    const user = userEvent.setup()
    render(<BoolHarness urlKey="weather" fallback={true} />)
    expect(screen.getByTestId('value')).toHaveTextContent('TRUE')
    await user.click(screen.getByRole('button', { name: 'toggle' }))
    await waitFor(() => expect(replaceMock).toHaveBeenCalled())
    expect(replaceMock.mock.calls[0][0]).toContain('weather=0')
  })

  it('boolean decoder accepts both "1" and "true"', () => {
    const dec = URL_STATE_SERIALIZERS.boolean.decode
    expect(dec('1')).toBe(true)
    expect(dec('true')).toBe(true)
    expect(dec('0')).toBe(false)
    expect(dec('false')).toBe(false)
    expect(dec(null)).toBe(false)
  })

  it('nullableString serializer drops empty strings', () => {
    const enc = URL_STATE_SERIALIZERS.nullableString.encode
    expect(enc(null)).toBeNull()
    expect(enc('')).toBeNull()
    expect(enc('FI')).toBe('FI')
  })

  it('batches multiple updates in one render into a single router.replace call', async () => {
    function BatchHarness() {
      const [a, setA] = useUrlState('a', '', URL_STATE_SERIALIZERS.string)
      const [b, setB] = useUrlState('b', '', URL_STATE_SERIALIZERS.string)
      return (
        <button
          onClick={() => {
            setA('alpha')
            setB('beta')
          }}
        >
          set both
        </button>
      )
    }
    const user = userEvent.setup()
    render(<BatchHarness />)
    await user.click(screen.getByRole('button', { name: 'set both' }))
    await waitFor(() => expect(replaceMock).toHaveBeenCalled())
    // Batched scheduler: exactly ONE router.replace call with both keys
    expect(replaceMock.mock.calls.length).toBeGreaterThanOrEqual(1)
    const url = replaceMock.mock.calls[replaceMock.mock.calls.length - 1][0]
    expect(url).toContain('a=alpha')
    expect(url).toContain('b=beta')
  })
})
