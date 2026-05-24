import { test, expect, type Route } from '@playwright/test'

/**
 * GP6 — Country Climate Passport (Phase 2B + MH3 from competitive UX audit).
 *
 * Smoke-tests the full Passport surface end-to-end through the UI:
 *   - Headline KPIs + plain-language sentence (Phase 2C) on the header
 *   - 5 modular tabs (Overview/News/Climate/Sources/Claims) per the
 *     Climate Watch country-profile pattern
 *   - URL-persistent tab selection via ?tab=... (Phase 1B MH1)
 *   - MultiViewTabs chart/table toggle on Climate Data (Phase 2G MH2)
 *   - Embed share button (Phase 2E MH6) opens iframe-snippet modal
 *
 * Competitive bar — benchmark against:
 *   - Climate Watch (climatewatchdata.org/countries/DEU) → modular tabs ✓
 *   - World Bank CCKP (climateknowledgeportal.worldbank.org) → KPI strip ✓
 *   - Climate ADAPT (EU) → news + claim ledger ✓
 *   - Probable Futures → plain-language interpretation ✓
 *
 * We exceed all four on: URL-persistent tab state, AI Act provenance
 * badge, plain-language tone-coloured sentences, embed widget.
 */

const COUNTRY_FIXTURE = {
  country_code: 'DE',
  country_name: 'Germany',
  flag: '🇩🇪',
  continent: 'Europe',
  article_count: 142,
  avg_credibility: 78,
  climate_risk_score: 32,
  category_breakdown: { climate_science: 45, policy: 67 },
  weather: { temperature_anomaly_c: 1.4 },
  sources: [{ source_name: 'Tagesschau', article_count: 50, avg_credibility: 80 }],
  recent_articles: [
    {
      article_id: 'a-1',
      title: 'Germany hits 50% renewable share milestone',
      source_name: 'Tagesschau',
      published_date: '2026-05-20T10:00:00Z',
      credibility: 'HIGH',
    },
  ],
}

const CLIMATE_FIXTURE = {
  country_code: 'DE',
  current_month: { period: '2026-05', temperature_avg_c: 14.2, precipitation_avg_mm: 2.1 },
  last_year_same_month: { period: '2025-05', temperature_avg_c: 12.8, precipitation_avg_mm: 3.0 },
  five_years_ago_same_month: { period: '2021-05', temperature_avg_c: 11.9, precipitation_avg_mm: 2.7 },
  temperature_trend: 'rising' as const,
  precipitation_comparison: 'similar to last year',
}

async function mockPassportBackend(page: import('@playwright/test').Page) {
  await page.route('**/api/map/country/DE/detail', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(COUNTRY_FIXTURE),
    })
  })
  await page.route('**/api/map/country/DE/climate-data', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(CLIMATE_FIXTURE),
    })
  })
  await page.route('**/api/map/country/DE/claim-ledger', async (route: Route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
}

test.describe('Country Passport · Phase 2B+ smoke', () => {
  test('renders headline KPIs + plain-language sentence on header', async ({ page }) => {
    await mockPassportBackend(page)
    await page.goto('/country/DE')

    await expect(page.getByTestId('country-passport-title')).toContainText('Germany')
    await expect(page.getByTestId('kpi-articles')).toContainText('142')
    await expect(page.getByTestId('kpi-credibility')).toContainText('78/100')
    await expect(page.getByTestId('kpi-anomaly')).toContainText('+1.4°C')

    // Phase 2C plain-language: every KPI carries an interpretation sentence
    await expect(page.getByTestId('kpi-anomaly-plain')).toContainText(
      /1\.4°C warmer/i,
    )
    await expect(page.getByTestId('kpi-credibility-plain')).toContainText(
      /generally reliable|highly-trusted/i,
    )
  })

  test('all 5 tabs render with proper a11y wiring', async ({ page }) => {
    await mockPassportBackend(page)
    await page.goto('/country/DE')

    for (const t of ['overview', 'news', 'climate', 'sources', 'claims']) {
      await expect(page.getByTestId(`passport-tab-${t}`)).toBeVisible()
    }
    const tablist = page.getByRole('tablist').first()
    await expect(tablist).toBeVisible()
  })

  test('tab selection is URL-persistent (MH1)', async ({ page }) => {
    await mockPassportBackend(page)
    await page.goto('/country/DE')
    await page.getByTestId('passport-tab-climate').click()
    await expect(page).toHaveURL(/tab=climate/)
    // Hydration: full-page reload preserves the climate tab
    await page.reload()
    await expect(page.getByTestId('passport-tab-climate')).toHaveAttribute(
      'aria-selected',
      'true',
    )
  })

  test('Climate Data offers chart + table views (MH2)', async ({ page }) => {
    await mockPassportBackend(page)
    await page.goto('/country/DE?tab=climate')
    // Chart view (default) renders the period cards
    await expect(page.getByTestId('multiview-tab-chart')).toHaveAttribute(
      'aria-selected',
      'true',
    )
    // Switch to table view → climate-table-view rendered
    await page.getByTestId('multiview-tab-table').click()
    await expect(page.getByTestId('climate-table-view')).toBeVisible()
    await expect(page.getByTestId('climate-table-view')).toContainText('Current month')
    await expect(page.getByTestId('climate-table-view')).toContainText('2026-05')
  })

  test('Embed share button opens iframe-snippet modal (MH6)', async ({ page }) => {
    await mockPassportBackend(page)
    await page.goto('/country/DE')
    await page.getByTestId('embed-share-button').click()
    await expect(page.getByTestId('embed-share-modal')).toBeVisible()
    const snippet = page.getByTestId('embed-share-snippet')
    await expect(snippet).toContainText('/embed/country/DE')
    await expect(snippet).toContainText('<iframe')
    // Width preset switches reflect in the snippet
    await page.getByTestId('embed-share-width-560').click()
    await expect(snippet).toContainText('width="560"')
  })
})

test.describe('Country Embed · iframe-ready surface smoke', () => {
  test('embed page renders standalone with watermark', async ({ page }) => {
    await mockPassportBackend(page)
    await page.goto('/embed/country/DE')
    await expect(page.getByTestId('country-embed-root')).toBeVisible()
    await expect(page.getByTestId('country-embed-title')).toContainText('Germany')
    // Watermark + back-link MANDATORY for embed distribution
    await expect(page.getByTestId('country-embed-watermark')).toBeVisible()
    await expect(page.getByTestId('country-embed-watermark')).toContainText(
      /Climatefacts\.ai/,
    )
    // The 4 KPI mini-tiles
    await expect(page.getByTestId('embed-kpi-articles')).toBeVisible()
    await expect(page.getByTestId('embed-kpi-credibility')).toBeVisible()
    await expect(page.getByTestId('embed-kpi-risk')).toBeVisible()
    await expect(page.getByTestId('embed-kpi-temp')).toBeVisible()
  })
})
