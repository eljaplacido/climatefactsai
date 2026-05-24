import { test, expect, type Route } from '@playwright/test'

/**
 * GP5 — Quota gate end-to-end smoke (Phase 1A + Phase 2A backend → UIX).
 *
 * Smoke-tests the integration between three layers:
 *   1. Backend `/api/quota` returns a structured envelope (Phase 1A)
 *   2. `useQuota` hook + `QuotaCounter` component render the right
 *      remaining-count copy + colour tone (Phase 2A)
 *   3. `UpgradeModal` surfaces when a gated endpoint returns 429
 *      with the structured envelope (Phase 2A)
 *
 * Competitive bar — our quota UX is benchmarked against:
 *   - Persefoni: limit hit = "contact sales" buried banner. We do better.
 *   - OWID: no quota concept (everything free, fully open). N/A.
 *   - IQAir: monthly free limit → modal with upgrade CTA. We match.
 *   - Watershed: enterprise-only, no consumer quota. N/A.
 *
 * Backend is mocked via page.route so this passes in CI without a
 * running FastAPI backend. The structured envelope shape MUST match
 * what api/quota_service.py emits — see test_quota_service.py for
 * the canonical shape.
 */

test.describe('Quota gate · backend → UIX smoke', () => {
  test('inline counter renders remaining-count copy from /api/quota', async ({ page }) => {
    await page.route('**/api/quota', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tier: 'freemium',
          quotas: [
            {
              quota_key: 'deep_research',
              allowed: true,
              used: 1,
              limit: 2,
              period: 'monthly',
              reset_at: '2026-06-01T00:00:00+00:00',
              upgrade_url: '/dashboard/subscription',
              tier: 'freemium',
              label: 'deep research queries',
            },
            {
              quota_key: 'compare',
              allowed: true,
              used: 0,
              limit: 1,
              period: 'monthly',
              reset_at: '2026-06-01T00:00:00+00:00',
              upgrade_url: '/dashboard/subscription',
              tier: 'freemium',
              label: 'topic comparisons',
            },
            {
              quota_key: 'url_analysis',
              allowed: false,
              used: 1,
              limit: 1,
              period: 'monthly',
              reset_at: '2026-06-01T00:00:00+00:00',
              upgrade_url: '/dashboard/subscription',
              tier: 'freemium',
              label: 'URL analyses',
            },
            {
              quota_key: 'saved_articles',
              allowed: true,
              used: 0,
              limit: 3,
              period: 'lifetime',
              reset_at: null,
              upgrade_url: '/dashboard/subscription',
              tier: 'freemium',
              label: 'saved articles',
            },
            {
              quota_key: 'saved_searches',
              allowed: true,
              used: 0,
              limit: 3,
              period: 'lifetime',
              reset_at: null,
              upgrade_url: '/dashboard/subscription',
              tier: 'freemium',
              label: 'saved searches',
            },
          ],
        }),
      })
    })

    await page.goto('/deep-search')

    // QuotaCounter for deep_research should render with state="ok"
    // and the "1 left this month" copy (2 limit - 1 used).
    const counter = page.getByTestId('quota-counter-deep_research')
    await expect(counter).toBeVisible()
    // Tier-2A logic: 1/2 = 50% → boundary ok/low (data-quota-state ok)
    await expect(counter).toContainText(/left this month/i)
    await expect(counter).toHaveAttribute('data-quota-remaining', '1')
  })

  test('exhausted quota → counter shows red + inline Upgrade link', async ({ page }) => {
    await page.route('**/api/quota', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tier: 'freemium',
          quotas: [
            {
              quota_key: 'deep_research',
              allowed: false,
              used: 2,
              limit: 2,
              period: 'monthly',
              reset_at: '2026-06-01T00:00:00+00:00',
              upgrade_url: '/dashboard/subscription',
              tier: 'freemium',
              label: 'deep research queries',
            },
            // Other keys minimal — only deep_research matters for this test.
          ],
        }),
      })
    })

    await page.goto('/deep-search')
    const counter = page.getByTestId('quota-counter-deep_research')
    await expect(counter).toBeVisible()
    await expect(counter).toHaveAttribute('data-quota-state', 'exhausted')
    const upgradeLink = page.getByTestId('quota-counter-deep_research-upgrade')
    await expect(upgradeLink).toHaveAttribute('href', '/dashboard/subscription')
  })

  test('gated endpoint 429 → UpgradeModal opens with backend copy', async ({ page }) => {
    // Allow quota fetch with healthy state so the counter renders normally...
    await page.route('**/api/quota', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tier: 'freemium',
          quotas: [
            {
              quota_key: 'deep_research',
              allowed: true,
              used: 1,
              limit: 2,
              period: 'monthly',
              reset_at: '2026-06-01T00:00:00+00:00',
              upgrade_url: '/dashboard/subscription',
              tier: 'freemium',
              label: 'deep research queries',
            },
          ],
        }),
      })
    })

    // ...but the actual deep-search POST returns the 429 envelope.
    await page.route('**/api/deep-search/', async (route: Route) => {
      if (route.request().method() !== 'POST') {
        await route.fallback()
        return
      }
      await route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: {
            error: 'quota_exceeded',
            quota: {
              quota_key: 'deep_research',
              used: 2,
              limit: 2,
              period: 'monthly',
              reset_at: '2026-06-01T00:00:00+00:00',
              upgrade_url: '/dashboard/subscription',
              tier: 'freemium',
              label: 'deep research queries',
            },
            message:
              "You've used 2 of 2 deep research queries on the freemium tier (monthly). Upgrade for higher limits.",
          },
        }),
      })
    })

    await page.goto('/deep-search')
    await page.locator('textarea').first().fill('test query')
    await page.getByRole('button', { name: /^Search$/i }).click()

    // UpgradeModal must surface
    const modal = page.getByTestId('upgrade-modal')
    await expect(modal).toBeVisible()
    await expect(page.getByTestId('upgrade-modal-used')).toContainText('2 / 2')
    await expect(page.getByTestId('upgrade-modal-tier')).toContainText('freemium')
    // Modal CTA points at the backend-provided upgrade_url
    const cta = page.getByTestId('upgrade-modal-upgrade-cta')
    await expect(cta).toHaveAttribute('href', '/dashboard/subscription')
  })
})
