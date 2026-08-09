import { expect, test } from "@playwright/test";
import { chat, openTerminal } from "./helpers";

/**
 * Runs before any trade so the mock's canned analysis line is exact.
 * Contract: planning/handoffs/llm.md, LLM_MOCK rule 3.
 */
test("mock analysis line is exact on a fresh book", async ({ page }) => {
  await openTerminal(page);

  const reply = await chat(page, "how is my portfolio doing?");

  expect(reply.text).toBe(
    "Mock analysis: total value $10,000.00, cash $10,000.00, 0 open positions, unrealized P&L $0.00.",
  );

  // An analysis question executes nothing.
  await expect(reply.actions).toHaveCount(0);
});

test("the transcript records the user turn and shows a loading state", async ({
  page,
}) => {
  await openTerminal(page);

  await page.getByTestId("chat-input").fill("what is my cash?");
  await page.getByTestId("chat-send").click();
  // The user turn is echoed optimistically, before the reply lands. Earlier
  // turns are restored from history, so assert on the newest one.
  await expect(page.getByTestId("chat-message-user").last()).toHaveText(
    /what is my cash\?/,
  );
  await expect(page.getByTestId("chat-loading")).toHaveCount(0, { timeout: 30_000 });
  await expect(page.getByTestId("chat-message-assistant").last()).toContainText(
    "Mock analysis: total value",
  );
});
