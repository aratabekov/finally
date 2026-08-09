import { expect, test } from "@playwright/test";
import { openTerminal, placeOrder } from "./helpers";

test.describe("portfolio visualisation", () => {
  test("the exposure treemap draws one cell per position", async ({ page }) => {
    await openTerminal(page);

    // Open a second position so the treemap has to split.
    await placeOrder(page, "JPM", "5", "buy");
    await expect(page.getByTestId("position-row-JPM")).toBeVisible();

    const heatmap = page.getByTestId("heatmap");
    await expect(heatmap).not.toContainText("NO OPEN POSITIONS");
    await expect(heatmap).toContainText("2 POS");
    await expect
      .poll(async () => heatmap.locator("svg rect").count(), { timeout: 15_000 })
      .toBeGreaterThanOrEqual(2);
    await expect(heatmap.locator("svg")).toContainText("NVDA");
    await expect(heatmap.locator("svg")).toContainText("JPM");
  });

  test("the equity curve has plotted data", async ({ page }) => {
    await openTerminal(page);

    const chart = page.getByTestId("pnl-chart");
    await expect(chart).not.toContainText("AWAITING FIRST SNAPSHOT");
    // Recharts draws the area as an svg path with a real "d" attribute.
    const d = await chart.locator("svg path.recharts-area-area").first().getAttribute("d");
    expect(d ?? "").toMatch(/^M/);
  });

  test("the positions table lists both holdings", async ({ page }) => {
    await openTerminal(page);

    await expect(page.locator('[data-testid^="position-row-"]')).toHaveCount(2);
    await expect(page.getByTestId("positions-table")).toBeVisible();
    await expect(page.getByTestId("position-pl-NVDA")).toBeVisible();
    await expect(page.getByTestId("position-pl-JPM")).toBeVisible();
  });

  test("clicking a position selects it in the chart", async ({ page }) => {
    await openTerminal(page);

    await page.getByTestId("position-row-JPM").click();
    await expect(page.getByTestId("main-chart")).toContainText("JPM");
    await expect(page.getByTestId("trade-ticker")).toHaveValue("JPM");
  });
});
