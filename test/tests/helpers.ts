import { expect, type Page, type Locator } from "@playwright/test";

export const DEFAULT_TICKERS = [
  "AAPL",
  "GOOGL",
  "MSFT",
  "AMZN",
  "TSLA",
  "NVDA",
  "META",
  "JPM",
  "V",
  "NFLX",
];

/** Mirrors fmtMoney in frontend/lib/format.ts. */
export function fmtMoney(value: number): string {
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/** "$9,430.50" / "-$12.34" / "+1.20%" -> number */
export function parseMoney(text: string | null): number {
  if (!text) return NaN;
  const match = text.trim().match(/-?\$?-?[\d,]+(\.\d+)?/);
  if (!match) return NaN;
  const negative = /^-/.test(text.trim());
  const value = Number(match[0].replace(/[$,\-]/g, ""));
  return negative ? -value : value;
}

export async function money(locator: Locator): Promise<number> {
  return parseMoney(await locator.textContent());
}

/**
 * Wait for a price-ish cell to hold a real, non-zero number. Cells render as
 * "--" before mount and as "0.00" between mount and the first SSE flush, so
 * both a missing element and a placeholder have to fail.
 */
export async function expectPriced(locator: Locator, timeout = 20_000) {
  await expect
    .poll(
      async () =>
        parseMoney(await locator.textContent({ timeout: 1_000 }).catch(() => null)),
      { timeout },
    )
    .toBeGreaterThan(0);
}

/** Open the terminal and wait for the first portfolio + stream data to land. */
export async function openTerminal(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("watchlist")).toBeVisible();
  await expect(page.getByTestId("connection-dot")).toHaveAttribute(
    "data-status",
    "connected",
  );
  // Prices only exist once the first SSE flush lands.
  await expectPriced(page.getByTestId("price-AAPL"));
}

export type Reply = {
  /** The assistant's prose. */
  text: string;
  /** Actions rendered under this reply only — restored history has its own. */
  actions: Locator;
};

/** Send a chat message and return the reply it produced. */
export async function chat(page: Page, message: string): Promise<Reply> {
  const replies = page.getByTestId("chat-message-assistant");
  const before = await replies.count();

  await page.getByTestId("chat-input").fill(message);
  await page.getByTestId("chat-send").click();
  await expect(replies).toHaveCount(before + 1, { timeout: 30_000 });
  await expect(page.getByTestId("chat-loading")).toHaveCount(0);

  const reply = replies.nth(before);
  return {
    text: (await reply.locator("p").first().textContent()) ?? "",
    actions: reply.getByTestId("chat-action"),
  };
}

export type TradeResponse = { status: number; body: Record<string, unknown> };

/**
 * Place a market order through the order rail and wait for the fill echo.
 * Returns the raw server response, which is the only place the rejection
 * reason survives today (the rail masks it).
 */
export async function placeOrder(
  page: Page,
  ticker: string,
  quantity: string,
  side: "buy" | "sell",
): Promise<TradeResponse> {
  await page.getByTestId("trade-ticker").fill(ticker);
  await page.getByTestId("trade-quantity").fill(quantity);

  const pending = page.waitForResponse((res) =>
    res.url().includes("/api/portfolio/trade"),
  );
  await page.getByTestId(`trade-${side}`).click();
  const res = await pending;
  const body = await res.json();
  await expect(page.getByTestId("trade-status")).not.toHaveText("Working...");
  return { status: res.status(), body };
}

/** Collect console errors and failed responses for bug evidence. */
export function watchForErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(`console: ${msg.text()}`);
  });
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  page.on("response", (res) => {
    if (res.url().includes("/api/") && res.status() >= 400) {
      errors.push(`http ${res.status()} ${res.url()}`);
    }
  });
  return errors;
}
