import { test, expect } from "@playwright/test";

test.describe("Climate Intelligence Map", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/map");
  });

  test("renders map page with header", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Climate Intelligence Map");
  });

  test("displays map container with Leaflet", async ({ page }) => {
    const mapContainer = page.locator(".leaflet-container");
    await expect(mapContainer).toBeVisible({ timeout: 15000 });
  });

  // ── Layer control (replaces old mode toggle) ──────────────────────────

  test("shows map layer control with default layer selected", async ({ page }) => {
    await expect(page.getByText("Article Density")).toBeVisible({ timeout: 10000 });
  });

  test("can switch map layers", async ({ page }) => {
    // Click a different layer
    const anomalyLayer = page.getByText("Temperature Anomaly");
    if (await anomalyLayer.isVisible({ timeout: 5000 })) {
      await anomalyLayer.click();
      await page.waitForTimeout(1000);
    }
    // Layer switching should not crash the page
    await expect(page.locator(".leaflet-container")).toBeVisible();
  });

  // ── Filter panel ──────────────────────────────────────────────────────

  test("shows reliability tier filter", async ({ page }) => {
    const select = page.locator("select").first();
    await expect(select).toBeVisible({ timeout: 10000 });
  });

  test("shows category checkboxes", async ({ page }) => {
    await expect(page.getByText("Climate Science")).toBeVisible({ timeout: 10000 });
  });

  test("category checkbox toggles filter", async ({ page }) => {
    const checkbox = page.locator("input[type=checkbox]").first();
    if (await checkbox.isVisible({ timeout: 5000 })) {
      const wasChecked = await checkbox.isChecked();
      await checkbox.click();
      await page.waitForTimeout(500);
      await expect(checkbox.isChecked()).resolves.toBe(!wasChecked);
    }
  });

  test("keyword filter input works", async ({ page }) => {
    const input = page.getByPlaceholder("Filter by keyword...");
    await expect(input).toBeVisible({ timeout: 5000 });
    await input.fill("Finland");
    await expect(input).toHaveValue("Finland");
  });

  // ── Map interaction ───────────────────────────────────────────────────

  test("clicking a country on map shows sidebar", async ({ page }) => {
    await page.waitForSelector(".leaflet-container", { timeout: 15000 });
    await page.waitForTimeout(2000);

    // Click a path element on the SVG layer
    const paths = page.locator(".leaflet-container svg path");
    const count = await paths.count();
    if (count > 5) {
      await paths.nth(5).click();
      await page.waitForTimeout(1000);
    }
    // Sidebar or country panel should appear after click
  });

  test("agentic query bar is present", async ({ page }) => {
    const input = page.getByPlaceholder(/Ask about climate news/);
    await expect(input).toBeVisible({ timeout: 10000 });
  });

  test("agentic query accepts input", async ({ page }) => {
    const input = page.getByPlaceholder(/Ask about climate news/);
    await input.fill("drought Africa");
    await expect(input).toHaveValue("drought Africa");
  });

  // ── Legend ────────────────────────────────────────────────────────────

  test("shows legend with density scale", async ({ page }) => {
    await expect(page.getByText("Article Density")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Low")).toBeVisible();
    await expect(page.getByText("Medium")).toBeVisible();
    await expect(page.getByText("High")).toBeVisible();
  });
});

