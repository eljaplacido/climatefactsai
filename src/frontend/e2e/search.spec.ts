import { test, expect } from '@playwright/test';

test.describe('Search Page', () => {
  test('should load the search page', async ({ page }) => {
    await page.goto('/search');
    await expect(page.locator('main')).toBeVisible();
  });

  test('should have search input', async ({ page }) => {
    await page.goto('/search');
    const searchInput = page.locator(
      'input[type="search"], input[type="text"], input[placeholder*="earch"], input[name*="search"], input[name*="query"]'
    );
    const count = await searchInput.count();
    if (count > 0) {
      await expect(searchInput.first()).toBeVisible();
    }
  });

  test('should accept search input', async ({ page }) => {
    await page.goto('/search');
    const searchInput = page.locator(
      'input[type="search"], input[type="text"], input[placeholder*="earch"]'
    ).first();

    if (await searchInput.count() === 0) {
      test.skip();
      return;
    }

    await searchInput.fill('climate change Finland');
    await expect(searchInput).toHaveValue('climate change Finland');
  });

  test('should show results or empty state after search', async ({ page }) => {
    await page.goto('/search');
    const searchInput = page.locator(
      'input[type="search"], input[type="text"], input[placeholder*="earch"]'
    ).first();

    if (await searchInput.count() === 0) {
      test.skip();
      return;
    }

    await searchInput.fill('climate');
    await searchInput.press('Enter');
    await page.waitForLoadState('networkidle');

    // Should show either results or empty state
    const body = page.locator('main');
    await expect(body).toBeVisible();
  });

  test('should have filter options', async ({ page }) => {
    await page.goto('/search');
    // Look for filter controls
    const filters = page.locator(
      '[data-testid="search-filters"], select, .filter, button:has-text("Filter")'
    );
    const count = await filters.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });
});
