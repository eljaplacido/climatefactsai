import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

/**
 * Accessibility CI gate — runs axe-core on the five most-trafficked pages.
 *
 * Phase 0 day 2 (2026-05-23): wires WCAG 2.1 AA + WCAG 2.2 AA into the
 * Playwright suite so any PR that regresses contrast, missing aria-labels,
 * heading hierarchy, or landmark structure breaks CI instead of shipping.
 *
 * Scope is intentionally tight on day 2: assert ZERO violations of
 * `serious` and `critical` severity, but allow `moderate` and `minor`
 * violations to land while we burn down the backlog. Tighten the
 * `disableRules` list to empty and lower the severity bar as we fix
 * findings.
 *
 * Each page is tested twice — light mode and dark mode — because the most
 * common a11y regression on this codebase is light-mode-only colour tokens
 * (the UI/UX audit named this as P2). Running both catches the next leak.
 *
 * Pages covered:
 *   - / (homepage)
 *   - /deep-search (Phase 0 §3.1 surface)
 *   - /analyze (Phase 0 §3.4 surface)
 *   - /sources (Phase 0 §3.7 surface)
 *   - /map (high-traffic surface with custom map controls)
 */

const PAGES = [
  { name: 'home', path: '/' },
  { name: 'deep-search', path: '/deep-search' },
  { name: 'analyze', path: '/analyze' },
  { name: 'sources', path: '/sources' },
  { name: 'map', path: '/map' },
]

const SEVERITY_FAIL_THRESHOLD: Array<'critical' | 'serious'> = ['critical', 'serious']

// Day-2 known-issues allowlist. Each disabled rule MUST have a backlog
// task to remove it. As we ship fixes, we delete entries from this list
// rather than leaving silent suppressions.
const KNOWN_ISSUES_BACKLOG = [
  // Map.tsx uses Leaflet which renders <a> tags without href on attribution
  // links; tracked under Phase 3 (deck.gl migration) where we replace Leaflet.
  'link-name',
  // Some legacy article cards still use generic role=button on divs;
  // tracked under Phase 1 (in-place article depth) where the card is rewritten.
  'aria-allowed-role',
]

for (const mode of ['light', 'dark'] as const) {
  test.describe(`a11y · ${mode} mode`, () => {
    test.use({
      colorScheme: mode,
    })

    for (const { name, path } of PAGES) {
      test(`${name} (${path}) has no critical or serious axe violations`, async ({ page }) => {
        await page.goto(path)
        // Give late-mounted client components (charts, maps, dynamic imports)
        // a moment to settle before scanning. 1.5s is empirically enough on
        // the CI baseline.
        await page.waitForTimeout(1500)

        const results = await new AxeBuilder({ page })
          .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
          .disableRules(KNOWN_ISSUES_BACKLOG)
          .analyze()

        const blocking = results.violations.filter((v) =>
          SEVERITY_FAIL_THRESHOLD.includes(v.impact as 'critical' | 'serious'),
        )

        if (blocking.length > 0) {
          // Surface every blocking violation with enough context to fix it
          // — rule id, severity, count of affected nodes, and one HTML
          // snippet to point at the offending element.
          const formatted = blocking.map((v) => ({
            id: v.id,
            impact: v.impact,
            help: v.help,
            helpUrl: v.helpUrl,
            nodeCount: v.nodes.length,
            firstTarget: v.nodes[0]?.target?.join(' > '),
            firstHtmlSnippet: v.nodes[0]?.html?.slice(0, 200),
          }))
          console.error(
            `\n[a11y] ${name} (${mode} mode) has ${blocking.length} blocking violation(s):\n` +
              JSON.stringify(formatted, null, 2),
          )
        }

        expect(blocking, `axe found ${blocking.length} critical/serious violations on ${path} (${mode})`).toEqual([])
      })
    }
  })
}
