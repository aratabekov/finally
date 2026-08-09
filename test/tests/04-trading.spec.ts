import { expect, test } from "@playwright/test";
import { expectPriced, money, openTerminal, placeOrder, watchForErrors } from "./helpers";

test.describe("order rail", () => {
  test("buy opens a position and debits cash", async ({ page }) => {
    const errors = watchForErrors(page);
    await openTerminal(page);

    const cashBefore = await money(page.getByTestId("cash-balance"));
    expect(cashBefore).toBe(10_000);

    await page.getByTestId("watchlist-row-NVDA").click();
    await expectPriced(page.getByTestId("trade-estimate"));
    await placeOrder(page, "NVDA", "3", "buy");

    await expect(page.getByTestId("trade-status")).toContainText(/BUY 3 NVDA at \$/);
    await expect(page.getByTestId("position-row-NVDA")).toBeVisible();

    await expect
      .poll(async () => money(page.getByTestId("cash-balance")))
      .toBeLessThan(cashBefore);

    // Quantity 3 in the positions table.
    await expect(page.getByTestId("position-row-NVDA")).toContainText("3");
    await expectPriced(page.getByTestId("position-price-NVDA"));
    await expect(page.getByTestId("position-pl-NVDA")).toBeVisible();

    // Net liquidation is roughly conserved by a market order with no fees.
    const total = await money(page.getByTestId("portfolio-total"));
    expect(Math.abs(total - 10_000)).toBeLessThan(100);

    expect(errors, errors.join("\n")).toEqual([]);
  });

  test("a partial sell credits cash and reduces the position", async ({ page }) => {
    await openTerminal(page);

    const cashBefore = await money(page.getByTestId("cash-balance"));
    await placeOrder(page, "NVDA", "1", "sell");

    await expect(page.getByTestId("trade-status")).toContainText(/SELL 1 NVDA at \$/);
    await expect
      .poll(async () => money(page.getByTestId("cash-balance")))
      .toBeGreaterThan(cashBefore);

    await expect(page.getByTestId("position-row-NVDA")).toBeVisible();
    await expect(page.getByTestId("position-row-NVDA")).toContainText("2");
  });

  test("positions survive a reload", async ({ page }) => {
    await openTerminal(page);
    await expect(page.getByTestId("position-row-NVDA")).toBeVisible();
    expect(await money(page.getByTestId("cash-balance"))).toBeLessThan(10_000);
  });
});
