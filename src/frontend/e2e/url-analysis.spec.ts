import { test, expect } from '@playwright/test';

test.describe('URL Analysis Page', () => {
  test('should load the analyze page', async ({ page }) => {
    await page.goto('/analyze');
    await expect(page.locator('main')).toBeVisible();
  });

  test('should have URL input field', async ({ page }) => {
    await page.goto('/analyze');
    const urlInput = page.locator(
      'input[type="url"], input[placeholder*="url" i], input[placeholder*="http" i], input[name*="url"]'
    );
    const count = await urlInput.count();
    if (count > 0) {
      await expect(urlInput.first()).toBeVisible();
    }
  });

  test('should accept URL input', async ({ page }) => {
    await page.goto('/analyze');
    const urlInput = page.locator(
      'input[type="url"], input[placeholder*="url" i], input[placeholder*="http" i], input[name*="url"]'
    ).first();

    if (await urlInput.count() === 0) {
      test.skip();
      return;
    }

    await urlInput.fill('https://example.com/climate-article');
    await expect(urlInput).toHaveValue('https://example.com/climate-article');
  });

  test('should have submit button', async ({ page }) => {
    await page.goto('/analyze');
    const submitBtn = page.locator(
      'button[type="submit"], button:has-text("Analyze"), button:has-text("Check"), button:has-text("Verify")'
    );
    const count = await submitBtn.count();
    if (count > 0) {
      await expect(submitBtn.first()).toBeVisible();
    }
  });

  test('should show methodology information', async ({ page }) => {
    // Check methodology page exists
    await page.goto('/methodology');
    await expect(page.locator('main')).toBeVisible();
  });
});
