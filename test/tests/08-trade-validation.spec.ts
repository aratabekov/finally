import { expect, test } from "@playwright/test";
import {
  expectPriced,
  fmtMoney,
  money,
  openTerminal,
  placeOrder,
} from "./helpers";

/**
 * Each rejection is checked twice: the server contract
 * (planning/handoffs/backend.md) and what the order rail actually shows the
 * user. The two currently disagree — see planning/handoffs/integration.md.
 */
test.describe("order rail validation", () => {
  test("an unaffordable buy shows the backend reason", async ({ page }) => {
    await openTerminal(page);

    const cashBefore = await money(page.getByTestId("cash-balance"));
    const res = await placeOrder(page, "AAPL", "100000", "buy");

    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/^Insufficient cash: need \$/);
    expect(await money(page.getByTestId("cash-balance"))).toBe(cashBefore);

    await expect(page.getByTestId("trade-status")).toContainText(
      String(res.body.error),
    );
  });

  test("selling more than is held shows the backend reason", async ({ page }) => {
    await openTerminal(page);

    const res = await placeOrder(page, "NVDA", "999", "sell");

    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/^Insufficient shares: tried to sell/);

    await expect(page.getByTestId("trade-status")).toContainText(
      String(res.body.error),
    );
  });

  // QQQQ is never added to the watchlist anywhere in this suite, so it has
  // never entered the price cache.
  test("a ticker the feed has never priced is refused", async ({ page }) => {
    await openTerminal(page);

    const res = await placeOrder(page, "QQQQ", "1", "buy");

    expect(res.status).toBe(400);
    expect(res.body.error).toBe("No price available for QQQQ");

    await expect(page.getByTestId("trade-status")).toContainText(
      "No price available for QQQQ",
    );
  });

  test("the fill echo reports the price the server actually filled at", async ({
    page,
  }) => {
    await openTerminal(page);

    const res = await placeOrder(page, "NVDA", "1", "buy");
    expect(res.status, JSON.stringify(res.body)).toBe(200);

    // The rail must echo the server's fill, not the last price it saw on the
    // tape — the two differ because the feed ticks while the order is in flight.
    const filled = Number(res.body.price);
    expect(filled).toBeGreaterThan(0);
    await expect(page.getByTestId("trade-status")).toContainText(
      `BUY 1 NVDA at ${fmtMoney(filled)}`,
    );
  });

  test("a ticker removed from the watchlist is no longer tradeable", async ({
    page,
  }) => {
    await openTerminal(page);

    // The feed evicts a symbol with no open position, so its cached price goes
    // away rather than freezing and filling later orders.
    await page.getByTestId("watchlist-input").fill("VWXY");
    await page.getByTestId("watchlist-add").click();
    await expectPriced(page.getByTestId("price-VWXY"));

    await page.getByTestId("watchlist-row-VWXY").hover();
    await page.getByTestId("watchlist-remove-VWXY").click();
    await expect(page.getByTestId("watchlist-row-VWXY")).toHaveCount(0);

    // Eviction happens on the next feed cycle (SSE_PUSH_SECONDS=0.5). Wait a
    // few cycles rather than retrying the order — a retry that succeeded would
    // open a position and pin the ticker in the cache for good.
    await page.waitForTimeout(3_000);

    const res = await placeOrder(page, "VWXY", "1", "buy");
    expect(res.status, JSON.stringify(res.body)).toBe(400);
    expect(res.body.error).toBe("No price available for VWXY");
    await expect(page.getByTestId("trade-status")).toContainText(
      "No price available for VWXY",
    );
  });

  test("a zero quantity is refused client-side", async ({ page }) => {
    await openTerminal(page);

    await page.getByTestId("trade-ticker").fill("AAPL");
    await page.getByTestId("trade-quantity").fill("0");
    await page.getByTestId("trade-buy").click();

    await expect(page.getByTestId("trade-status")).toHaveText(
      "Enter a symbol and a quantity above zero.",
    );
  });

  test("a full sell closes the position", async ({ page }) => {
    await openTerminal(page);

    await expect(page.getByTestId("position-row-JPM")).toBeVisible();
    const res = await placeOrder(page, "JPM", "5", "sell");
    expect(res.status).toBe(200);

    await expect(page.getByTestId("position-row-JPM")).toHaveCount(0);
    await expect(page.getByTestId("heatmap")).not.toContainText("JPM");
  });
});
