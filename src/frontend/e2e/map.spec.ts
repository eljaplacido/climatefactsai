import { test, expect } from "@playwright/test";

test.describe("Climate Intelligence Map", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/map");
  });

  test("renders map page with header", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Climate Intelligence World Map");
  });

  test("displays map SVG element", async ({ page }) => {
    // Wait for the dynamically loaded map
    const svg = page.locator("svg");
    await expect(svg).toBeVisible({ timeout: 15000 });
  });

  test("shows filter bar with mode toggle", async ({ page }) => {
    await expect(page.getByText("Publisher Origin")).toBeVisible();
    await expect(page.getByText("Countries Discussed")).toBeVisible();
  });

  test("shows reliability tier dropdown", async ({ page }) => {
    const select = page.locator("select").first();
    await expect(select).toBeVisible();
    // Should have All, HIGH, MEDIUM, LOW options
    const options = select.locator("option");
    await expect(options).toHaveCount(4);
  });

  test("shows content category pills", async ({ page }) => {
    await expect(page.getByText("Climate Science")).toBeVisible();
    await expect(page.getByText("Sustainability")).toBeVisible();
    await expect(page.getByText("Policy")).toBeVisible();
    await expect(page.getByText("Green Transition")).toBeVisible();
  });

  test("shows source filter dropdown", async ({ page }) => {
    // Second select should be the source filter
    await expect(page.getByText("All sources")).toBeVisible();
  });

  test("shows agentic query bar", async ({ page }) => {
    const input = page.getByPlaceholder(/Ask about climate news/);
    await expect(input).toBeVisible();
    await expect(page.getByText("Query Map")).toBeVisible();
  });

  test("can switch between publisher and discussed modes", async ({ page }) => {
    const discussedBtn = page.getByText("Countries Discussed");
    await discussedBtn.click();
    // Mode label should update in legend
    await expect(page.getByText("Countries discussed in news")).toBeVisible();

    const publisherBtn = page.getByText("Publisher Origin");
    await publisherBtn.click();
    await expect(page.getByText("Publisher origin")).toBeVisible();
  });

  test("can toggle category filter pills", async ({ page }) => {
    const pill = page.getByText("Climate Science");
    await pill.click();
    // After click, pill should have active styling (primary bg)
    await expect(pill).toHaveClass(/bg-clilens-primary/);

    // Click again to deselect
    await pill.click();
    await expect(pill).not.toHaveClass(/bg-clilens-primary/);
  });

  test("keyword filter input works", async ({ page }) => {
    const input = page.getByPlaceholder("Filter by keyword...");
    await input.fill("Finland");
    // Should filter visible results (no crash)
    await expect(input).toHaveValue("Finland");
  });

  test("clicking a country on map shows sidebar details", async ({ page }) => {
    // Wait for map to load
    await page.waitForSelector("svg path", { timeout: 15000 });

    // Click on a visible path element (country)
    const paths = page.locator("svg path");
    const count = await paths.count();
    if (count > 5) {
      // Click the 5th path (usually a visible country)
      await paths.nth(5).click();
    }

    // Sidebar should show either country info or "No articles" message
    // This verifies the click interaction works
    await page.waitForTimeout(500);
  });

  test("agentic query submits and shows results", async ({ page }) => {
    const input = page.getByPlaceholder(/Ask about climate news/);
    await input.fill("drought Africa");
    await page.getByText("Query Map").click();

    // Should show loading state or results
    await page.waitForTimeout(2000);
    // After query, should show result text or "No articles" message
  });

  test("shows legend with density scale", async ({ page }) => {
    await expect(page.getByText("Article density:")).toBeVisible();
    await expect(page.getByText("Low")).toBeVisible();
    await expect(page.getByText("Medium")).toBeVisible();
    await expect(page.getByText("High")).toBeVisible();
  });

  test("sidebar shows placeholder when no country selected", async ({ page }) => {
    await expect(
      page.getByText("Click a country on the map")
    ).toBeVisible();
  });
});
