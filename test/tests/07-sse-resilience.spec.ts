import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";
import { expectPriced, openTerminal } from "./helpers";

const CONTAINER = process.env.E2E_CONTAINER;

test("the stream reconnects after the server drops it", async ({ page }) => {
  test.skip(!CONTAINER, "needs the containerised app (run via run-e2e.sh)");

  await openTerminal(page);
  await expect(page.getByTestId("connection-dot")).toHaveAttribute(
    "data-status",
    "connected",
  );

  // Restarting the server closes every open SSE connection for real; Chromium's
  // offline emulation leaves an already-established stream open.
  execFileSync("docker", ["restart", CONTAINER!], { stdio: "ignore" });

  await expect(page.getByTestId("connection-dot")).not.toHaveAttribute(
    "data-status",
    "connected",
    { timeout: 20_000 },
  );

  // EventSource retries on its own; no page reload.
  await expect(page.getByTestId("connection-dot")).toHaveAttribute(
    "data-status",
    "connected",
    { timeout: 60_000 },
  );

  const cell = page.getByTestId("price-AAPL");
  await expectPriced(cell);
  const first = await cell.textContent();
  await expect.poll(async () => cell.textContent(), { timeout: 20_000 }).not.toBe(first);
});

test("the stream comes back after a reload", async ({ page }) => {
  await openTerminal(page);
  await page.reload();
  await expect(page.getByTestId("connection-dot")).toHaveAttribute(
    "data-status",
    "connected",
    { timeout: 20_000 },
  );
  await expectPriced(page.getByTestId("price-AAPL"));
});
