import { expect, test } from "@playwright/test";
import { chat, money, openTerminal } from "./helpers";

/**
 * Mock behaviours are specified exactly in planning/handoffs/llm.md.
 * Action assertions are scoped to the reply under test: the transcript is
 * restored from GET /api/chat/history on mount, so earlier turns render their
 * own `chat-action` entries too.
 */
test.describe("assistant actions (LLM_MOCK)", () => {
  test("a trade instruction executes and shows an inline action", async ({ page }) => {
    await openTerminal(page);

    const cashBefore = await money(page.getByTestId("cash-balance"));
    const reply = await chat(page, "buy 5 AAPL");

    expect(reply.text).toBe("Executing buy 5 AAPL at the current market price.");
    await expect(reply.actions).toHaveCount(1);
    await expect(reply.actions).toHaveText(["BUY 5 AAPL"]);

    await expect(page.getByTestId("position-row-AAPL")).toBeVisible();
    await expect(page.getByTestId("position-row-AAPL")).toContainText("5");
    await expect
      .poll(async () => money(page.getByTestId("cash-balance")))
      .toBeLessThan(cashBefore);
  });

  test("a watchlist instruction executes and shows an inline action", async ({
    page,
  }) => {
    await openTerminal(page);

    const reply = await chat(page, "add pypl to the watchlist");

    expect(reply.text).toBe("Adding PYPL to the watchlist.");
    await expect(reply.actions).toHaveText(["ADD PYPL"]);
    await expect(page.getByTestId("watchlist-row-PYPL")).toBeVisible();
  });

  test("a compound instruction executes both actions", async ({ page }) => {
    await openTerminal(page);

    const reply = await chat(page, "sell 2 AAPL and remove pypl from the watchlist");

    expect(reply.text).toBe(
      "Executing sell 2 AAPL at the current market price. Removing PYPL from the watchlist.",
    );
    await expect(reply.actions).toHaveText(["SELL 2 AAPL", "REMOVE PYPL"]);

    await expect(page.getByTestId("watchlist-row-PYPL")).toHaveCount(0);
    await expect(page.getByTestId("position-row-AAPL")).toContainText("3");
  });

  test("a rejected trade is reported inline and in the message", async ({ page }) => {
    await openTerminal(page);

    const reply = await chat(page, "buy 1000 AAPL");

    expect(reply.text).toContain(
      "Executing buy 1000 AAPL at the current market price.",
    );
    expect(reply.text).toContain("Could not complete: Insufficient cash: need $");

    await expect(reply.actions).toHaveCount(1);
    await expect(reply.actions).toContainText(
      "BUY 1000 AAPL rejected: Insufficient cash",
    );
  });

  test("the transcript is restored on reload", async ({ page }) => {
    await openTerminal(page);

    // Everything the earlier tests in this file sent is persisted server side.
    const users = page.getByTestId("chat-message-user");
    await expect(users.first()).toBeVisible();
    await expect(users.filter({ hasText: "buy 5 AAPL" })).toHaveCount(1);

    // Executed actions come back with the turn that produced them.
    await expect(
      page.getByTestId("chat-message-assistant").filter({ hasText: "Adding PYPL" }),
    ).toHaveCount(1);
    await expect(page.getByTestId("chat-action").first()).toHaveText("BUY 5 AAPL");
  });

  test("the assistant panel collapses and expands", async ({ page }) => {
    await openTerminal(page);

    await page.getByTestId("chat-collapse").click();
    await expect(page.getByTestId("chat-panel")).toHaveCount(0);
    await page.getByTestId("chat-expand").click();
    await expect(page.getByTestId("chat-panel")).toBeVisible();
  });
});
