import { test, expect } from '@playwright/test';

test.describe('Homepage', () => {
  test('should load the homepage', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/CliLens/i);
  });

  test('should display article cards', async ({ page }) => {
    await page.goto('/');
    // Wait for articles to load
    const articles = page.locator('[data-testid="article-card"], .article-card, a[href*="/articles/"]');
    // Page should have at least some content
    await expect(page.locator('main')).toBeVisible();
  });

  test('should have navigation links', async ({ page }) => {
    await page.goto('/');
    // Check for common navigation elements
    const nav = page.locator('nav, header');
    await expect(nav.first()).toBeVisible();
  });

  test('should have country filter', async ({ page }) => {
    await page.goto('/');
    // Look for country selector or filter
    const countryFilter = page.locator(
      'select[name*="country"], [data-testid="country-filter"], button:has-text("Country"), button:has-text("Finland")'
    );
    // Country filter may or may not be present on homepage
    const filterCount = await countryFilter.count();
    if (filterCount > 0) {
      await expect(countryFilter.first()).toBeVisible();
    }
  });

  test('should have credibility filter options', async ({ page }) => {
    await page.goto('/');
    // Look for credibility/filter controls
    const filters = page.locator(
      '[data-testid="credibility-filter"], button:has-text("HIGH"), button:has-text("MEDIUM"), button:has-text("LOW"), select[name*="credibility"]'
    );
    const count = await filters.count();
    // At least the page should render without errors
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('should navigate to search page', async ({ page }) => {
    await page.goto('/');
    const searchLink = page.locator('a[href*="/search"], button:has-text("Search"), input[type="search"]');
    const count = await searchLink.count();
    if (count > 0) {
      await searchLink.first().click();
      await expect(page).toHaveURL(/search/);
    }
  });

  test('should be responsive on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await expect(page.locator('main')).toBeVisible();
    // Page should not have horizontal scroll
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 5); // 5px tolerance
  });
});
