import { expect, test } from "@playwright/test";
import { DEFAULT_TICKERS, expectPriced, openTerminal } from "./helpers";

test.describe("watchlist CRUD", () => {
  test("add a ticker", async ({ page }) => {
    await openTerminal(page);

    await page.getByTestId("watchlist-input").fill("pypl");
    await page.getByTestId("watchlist-add").click();

    await expect(page.getByTestId("watchlist-row-PYPL")).toBeVisible();
    await expect(page.locator('[data-testid^="watchlist-row-"]')).toHaveCount(
      DEFAULT_TICKERS.length + 1,
    );
    // The feed picks the new symbol up on its next poll.
    await expectPriced(page.getByTestId("price-PYPL"));
  });

  test("the addition survives a reload", async ({ page }) => {
    await openTerminal(page);
    await expect(page.getByTestId("watchlist-row-PYPL")).toBeVisible();
  });

  test("remove a ticker", async ({ page }) => {
    await openTerminal(page);

    await page.getByTestId("watchlist-row-PYPL").hover();
    await page.getByTestId("watchlist-remove-PYPL").click();

    await expect(page.getByTestId("watchlist-row-PYPL")).toHaveCount(0);
    await expect(page.locator('[data-testid^="watchlist-row-"]')).toHaveCount(
      DEFAULT_TICKERS.length,
    );
  });

  test("a blank symbol is ignored client-side", async ({ page }) => {
    await openTerminal(page);

    let posted = false;
    page.on("request", (req) => {
      if (req.method() === "POST" && req.url().includes("/api/watchlist")) posted = true;
    });

    await page.getByTestId("watchlist-input").fill("   ");
    await page.getByTestId("watchlist-add").click();
    await page.waitForTimeout(500);

    expect(posted).toBe(false);
    await expect(page.locator('[data-testid^="watchlist-row-"]')).toHaveCount(
      DEFAULT_TICKERS.length,
    );
  });

  test("an unknown symbol is accepted and the simulator invents a price", async ({
    page,
  }) => {
    await openTerminal(page);

    await page.getByTestId("watchlist-input").fill("WXYZ");
    await page.getByTestId("watchlist-add").click();

    // There is no symbol validation on either side; market/gbm.py falls back to
    // DEFAULT_SEED for anything not in SEEDS, so a typo streams a fake price.
    await expect(page.getByTestId("watchlist-row-WXYZ")).toBeVisible();
    await expectPriced(page.getByTestId("price-WXYZ"));

    await page.getByTestId("watchlist-row-WXYZ").hover();
    await page.getByTestId("watchlist-remove-WXYZ").click();
    await expect(page.getByTestId("watchlist-row-WXYZ")).toHaveCount(0);
  });
});
