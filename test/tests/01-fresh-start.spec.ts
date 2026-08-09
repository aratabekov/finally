import { expect, test } from "@playwright/test";
import {
  DEFAULT_TICKERS,
  expectPriced,
  money,
  openTerminal,
  watchForErrors,
} from "./helpers";

test.describe("fresh start", () => {
  test("default watchlist, $10,000 seed, live stream", async ({ page }) => {
    const errors = watchForErrors(page);
    await openTerminal(page);

    // 10 default tickers, exactly.
    const rows = page.locator('[data-testid^="watchlist-row-"]');
    await expect(rows).toHaveCount(DEFAULT_TICKERS.length);
    for (const ticker of DEFAULT_TICKERS) {
      await expect(page.getByTestId(`watchlist-row-${ticker}`)).toBeVisible();
    }

    // Seeded cash and net liquidation on an empty book.
    await expect(page.getByTestId("cash-balance")).toHaveText("$10,000.00");
    await expect(page.getByTestId("portfolio-total")).toHaveText("$10,000.00");
    expect(await money(page.getByTestId("portfolio-pl"))).toBe(0);

    // Empty book: no positions, empty exposure panel.
    await expect(page.locator('[data-testid^="position-row-"]')).toHaveCount(0);
    await expect(page.getByTestId("heatmap")).toContainText("NO OPEN POSITIONS");

    expect(errors, errors.join("\n")).toEqual([]);
  });

  test("prices stream and flash", async ({ page }) => {
    await openTerminal(page);

    const cell = page.getByTestId("price-AAPL");
    const first = await cell.textContent();

    // Simulator ticks at ~500ms; the client flushes every 250ms.
    await expect
      .poll(async () => cell.textContent(), { timeout: 20_000 })
      .not.toBe(first);

    // A tick sets data-flash to up/down for ~500ms before decaying to none.
    const flashed = await page
      .locator('[data-testid^="price-"][data-flash="up"], [data-testid^="price-"][data-flash="down"]')
      .count();
    expect(flashed).toBeGreaterThan(0);
  });

  test("selecting a ticker drives the chart and the order rail", async ({ page }) => {
    await openTerminal(page);

    await page.getByTestId("watchlist-row-TSLA").click();
    await expect(page.getByTestId("watchlist-row-TSLA")).toHaveAttribute(
      "data-selected",
      "true",
    );
    await expect(page.getByTestId("main-chart")).toContainText("TSLA");
    await expect(page.getByTestId("trade-ticker")).toHaveValue("TSLA");
    await expectPriced(page.getByTestId("main-chart-price"));
  });
});
