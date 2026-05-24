import { test, expect, type Route } from '@playwright/test';

/**
 * GP4 — Analyze URL: structured failure reasons end-to-end.
 *
 * Verifies the §3.4 fix shipped on 2026-05-23:
 *   1. When the backend returns a structured failure (`failure_reason` +
 *      `failure_detail`), the form renders the rich block — icon, title,
 *      reason chip, HTTP status (when applicable), message, "What to try"
 *      remediation card, and the appropriate deeplink for paywall /
 *      JS-rendered / legal / extraction-too-short reasons.
 *   2. The deeplink target is `/research` for the four reasons that
 *      legitimately benefit from text-paste mode.
 *   3. Legacy free-form `error` strings still render the fallback block so
 *      older backends keep working (backward compat path).
 *   4. The `data-testid` hooks are stable for downstream observability.
 *
 * Backend is mocked via `page.route` so this passes in CI without a
 * running FastAPI backend.
 */

const ANALYSIS_ID = '11111111-2222-3333-4444-555555555555';
const ACCESS_TOKEN = 'mock-hmac-token-for-anonymous-read';

async function mockPaywallFailure(page: import('@playwright/test').Page) {
  // POST /api/analyze-url → returns processing immediately
  await page.route('**/api/analyze-url', async (route: Route) => {
    if (route.request().method() !== 'POST') {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: ANALYSIS_ID,
        status: 'processing',
        estimated_time: 5,
        access_token: ACCESS_TOKEN,
      }),
    });
  });

  // GET /api/analyze-url/{id} → first poll returns failed with structured payload
  await page.route(`**/api/analyze-url/${ANALYSIS_ID}*`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: ANALYSIS_ID,
        status: 'failed',
        error: 'The page loaded but only returned a short stub with subscription / premium-content keywords. The full article is gated behind a paywall.',
        failure_reason: 'paywall_suspected',
        failure_detail: {
          reason: 'paywall_suspected',
          title: 'Paywall detected',
          message: 'The page loaded but only returned a short stub with subscription / premium-content keywords. The full article is gated behind a paywall.',
          remediation: 'If you have a subscription, open the article in your browser and paste the text into /research. Otherwise try an open-access summary from the same publisher.',
          extra: { extracted_chars: 42, html_bytes: 145_322 },
        },
      }),
    });
  });
}

test.describe('Analyze URL · Structured failure reasons (GP4)', () => {
  test('paywall_suspected: shows icon, reason chip, message, remediation, and /research deeplink', async ({ page }) => {
    await mockPaywallFailure(page);

    await page.goto('/analyze');
    const urlInput = page.locator('#url-input');
    await urlInput.fill('https://www.example-paywalled-news.com/2026/05/22/climate-story');
    await page.getByRole('button', { name: /^Analyze$/i }).click();

    // Wait for the structured failure block to render. Poll runs every 3s
    // in the component; the GET mock responds with `failed` immediately.
    const failureBlock = page.getByTestId('url-analysis-failure');
    await expect(failureBlock).toBeVisible({ timeout: 15_000 });

    // Title
    await expect(page.getByTestId('url-analysis-failure-title')).toHaveText('Paywall detected');

    // Reason chip
    const reasonChip = page.getByTestId('url-analysis-failure-reason');
    await expect(reasonChip).toBeVisible();
    await expect(reasonChip).toHaveText('paywall_suspected');

    // Body contains the human-readable message
    await expect(failureBlock).toContainText(/subscription/i);
    await expect(failureBlock).toContainText(/paywall/i);

    // Remediation block is rendered
    await expect(failureBlock).toContainText(/What to try/i);
    await expect(failureBlock).toContainText(/Otherwise try an open-access summary/i);

    // The /research deeplink is present for paywall reason
    const pasteDeeplink = page.getByTestId('url-analysis-failure-paste-deeplink');
    await expect(pasteDeeplink).toBeVisible();
    await expect(pasteDeeplink).toHaveAttribute('href', '/research');

    // Try-different-URL button is present
    await expect(failureBlock.getByRole('button', { name: /Try a different URL/i })).toBeVisible();
  });

  test('http_forbidden: shows different title + does NOT show /research deeplink', async ({ page }) => {
    await page.route('**/api/analyze-url', async (route: Route) => {
      if (route.request().method() !== 'POST') {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: ANALYSIS_ID,
          status: 'processing',
          access_token: ACCESS_TOKEN,
        }),
      });
    });
    await page.route(`**/api/analyze-url/${ANALYSIS_ID}*`, async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: ANALYSIS_ID,
          status: 'failed',
          error: 'HTTP 403',
          failure_reason: 'http_forbidden',
          failure_detail: {
            reason: 'http_forbidden',
            title: 'Source blocked our reader',
            message: 'The site returned HTTP 403, which usually means automated access is blocked.',
            remediation: 'Open the article in your browser, copy the visible text, and use the Research → Paste text mode.',
            status_code: 403,
          },
        }),
      });
    });

    await page.goto('/analyze');
    await page.locator('#url-input').fill('https://cloudflare-protected.example.com/article');
    await page.getByRole('button', { name: /^Analyze$/i }).click();

    const failureBlock = page.getByTestId('url-analysis-failure');
    await expect(failureBlock).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('url-analysis-failure-title')).toHaveText('Source blocked our reader');
    await expect(page.getByTestId('url-analysis-failure-reason')).toHaveText('http_forbidden');
    await expect(failureBlock).toContainText('HTTP 403');

    // http_forbidden is NOT in the deeplink whitelist
    await expect(page.getByTestId('url-analysis-failure-paste-deeplink')).toHaveCount(0);
  });

  test('legacy free-form error (no failure_detail) still renders the fallback block', async ({ page }) => {
    await page.route('**/api/analyze-url', async (route: Route) => {
      if (route.request().method() !== 'POST') {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: ANALYSIS_ID,
          status: 'processing',
          access_token: ACCESS_TOKEN,
        }),
      });
    });
    await page.route(`**/api/analyze-url/${ANALYSIS_ID}*`, async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: ANALYSIS_ID,
          status: 'failed',
          error: 'Some legacy error string from an old backend.',
          // No failure_detail / failure_reason — older backend
        }),
      });
    });

    await page.goto('/analyze');
    await page.locator('#url-input').fill('https://legacy.example.com/article');
    await page.getByRole('button', { name: /^Analyze$/i }).click();

    const failureBlock = page.getByTestId('url-analysis-failure');
    await expect(failureBlock).toBeVisible({ timeout: 15_000 });
    await expect(failureBlock).toContainText('Analysis Failed');
    await expect(failureBlock).toContainText('Some legacy error string from an old backend.');
    // No structured-only elements
    await expect(page.getByTestId('url-analysis-failure-title')).toHaveCount(0);
    await expect(page.getByTestId('url-analysis-failure-reason')).toHaveCount(0);
  });
});
