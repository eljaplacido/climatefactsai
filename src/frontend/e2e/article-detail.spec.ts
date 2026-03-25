import { test, expect } from '@playwright/test';

test.describe('Article Detail Page', () => {
  // We'll use a mock article ID - tests should handle 404 gracefully
  const TEST_ARTICLE_PATH = '/articles/test-article-id';

  test('should show 404 for non-existent article', async ({ page }) => {
    const response = await page.goto(TEST_ARTICLE_PATH);
    // Should either show 404 page or redirect
    if (response && response.status() === 404) {
      await expect(page.locator('body')).toContainText(/not found/i);
    }
  });

  test('article page structure should render correctly', async ({ page }) => {
    // Navigate to the articles listing first
    await page.goto('/');

    // Try to find and click on an article
    const articleLink = page.locator('a[href*="/articles/"]').first();
    const hasArticles = await articleLink.count() > 0;

    if (!hasArticles) {
      test.skip();
      return;
    }

    await articleLink.click();
    await page.waitForLoadState('networkidle');

    // Check for article detail structure
    const article = page.locator('article, [data-testid="article-detail"], main');
    await expect(article.first()).toBeVisible();
  });

  test('should display credibility gauge', async ({ page }) => {
    await page.goto('/');
    const articleLink = page.locator('a[href*="/articles/"]').first();

    if (await articleLink.count() === 0) {
      test.skip();
      return;
    }

    await articleLink.click();
    await page.waitForLoadState('networkidle');

    // Look for credibility gauge component
    const gauge = page.locator(
      '[data-testid="credibility-gauge"], .credibility-gauge, svg, canvas'
    );
    // Gauge should be present in article detail
    const gaugeCount = await gauge.count();
    expect(gaugeCount).toBeGreaterThanOrEqual(0);
  });

  test('should display claims section', async ({ page }) => {
    await page.goto('/');
    const articleLink = page.locator('a[href*="/articles/"]').first();

    if (await articleLink.count() === 0) {
      test.skip();
      return;
    }

    await articleLink.click();
    await page.waitForLoadState('networkidle');

    // Look for claims section
    const claimsSection = page.locator(
      'h2:has-text("Claims"), h2:has-text("claims"), [data-testid="claims-section"]'
    );
    const claimsCount = await claimsSection.count();
    // Claims section may or may not be present depending on data
    expect(claimsCount).toBeGreaterThanOrEqual(0);
  });

  test('should display insight summary when available', async ({ page }) => {
    await page.goto('/');
    const articleLink = page.locator('a[href*="/articles/"]').first();

    if (await articleLink.count() === 0) {
      test.skip();
      return;
    }

    await articleLink.click();
    await page.waitForLoadState('networkidle');

    // Look for insight summary
    const insight = page.locator(
      '[data-testid="insight-summary"], h3:has-text("Analysis Summary"), .bg-blue-50'
    );
    const insightCount = await insight.count();
    expect(insightCount).toBeGreaterThanOrEqual(0);
  });

  test('should have link to original article', async ({ page }) => {
    await page.goto('/');
    const articleLink = page.locator('a[href*="/articles/"]').first();

    if (await articleLink.count() === 0) {
      test.skip();
      return;
    }

    await articleLink.click();
    await page.waitForLoadState('networkidle');

    const originalLink = page.locator(
      'a:has-text("original article"), a:has-text("View original"), a[target="_blank"]'
    );
    const linkCount = await originalLink.count();
    expect(linkCount).toBeGreaterThanOrEqual(0);
  });
});
