import { vi } from 'vitest'

/**
 * Shared `next/navigation` mock for Vitest component + page tests.
 *
 * Extracted 2026-05-23 (Phase 2 audit) — was duplicated across 4+ test
 * files. Centralising means a Next.js router-API change touches one
 * file instead of many.
 *
 * Usage:
 *   import { mockNextNavigation } from '@/__tests__/testHelpers/nextNavigation'
 *   mockNextNavigation({ pathname: '/deep-search', initialSearch: 'q=test' })
 *
 * Returns the mocked router so the test can assert on `replace` / `push`
 * calls and the live searchParams ref so the test can swap URL state
 * mid-test to exercise hydration.
 */

export interface MockNextNavigationOptions {
  /** Pathname returned by usePathname(). Defaults to '/'. */
  pathname?: string
  /** Initial query string (without leading '?'). Defaults to ''. */
  initialSearch?: string
  /** Optional URL params returned by useParams(). */
  params?: Record<string, string>
}

export interface MockedNextNavigationRefs {
  /** Mocked router.replace — assertable spy. */
  replace: ReturnType<typeof vi.fn>
  /** Mocked router.push — assertable spy. */
  push: ReturnType<typeof vi.fn>
  /** Mutable getter for the current search string. Tests can write to
   *  `searchRef.current = 'q=new'` and the next searchParams read returns it. */
  searchRef: { current: string }
}

export function mockNextNavigation(
  options: MockNextNavigationOptions = {},
): MockedNextNavigationRefs {
  const refs: MockedNextNavigationRefs = {
    replace: vi.fn((url: string, _opts?: { scroll?: boolean }) => {
      const qIdx = url.indexOf('?')
      refs.searchRef.current = qIdx >= 0 ? url.slice(qIdx + 1) : ''
    }),
    push: vi.fn((url: string, _opts?: { scroll?: boolean }) => {
      const qIdx = url.indexOf('?')
      refs.searchRef.current = qIdx >= 0 ? url.slice(qIdx + 1) : ''
    }),
    searchRef: { current: options.initialSearch ?? '' },
  }

  vi.mock('next/navigation', () => ({
    useRouter: () => ({
      replace: refs.replace,
      push: refs.push,
    }),
    usePathname: () => options.pathname ?? '/',
    useSearchParams: () => new URLSearchParams(refs.searchRef.current),
    useParams: () => options.params ?? {},
  }))

  return refs
}
