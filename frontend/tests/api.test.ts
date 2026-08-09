import { afterEach, describe, expect, it, vi } from "vitest";
import {
  fetchChatHistory,
  readChatActions,
  readPortfolio,
  readSnapshots,
  readWatchlist,
  submitTrade,
} from "@/lib/api";

function stubFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("readPortfolio", () => {
  it("accepts either cash field name and derives missing position math", () => {
    const portfolio = readPortfolio({
      cash_balance: 8000,
      positions: [{ ticker: "AAPL", quantity: 10, avg_cost: 100, current_price: 120 }],
    });
    expect(portfolio.cash).toBe(8000);
    expect(portfolio.total_value).toBe(9200);
    expect(portfolio.positions[0].market_value).toBe(1200);
    expect(portfolio.positions[0].unrealized_pl).toBe(200);
    expect(portfolio.positions[0].pct_change).toBeCloseTo(20);
  });

  it("keeps the server total when one is supplied", () => {
    const portfolio = readPortfolio({ cash: 100, total_value: 12345, positions: [] });
    expect(portfolio.total_value).toBe(12345);
  });
});

describe("readSnapshots", () => {
  it("reads a bare array or a wrapped one", () => {
    const bare = readSnapshots([{ total_value: 10, recorded_at: "t1" }]);
    const wrapped = readSnapshots({ snapshots: [{ total_value: 10, recorded_at: "t1" }] });
    expect(bare).toEqual(wrapped);
    expect(bare[0].total_value).toBe(10);
  });
});

describe("readWatchlist", () => {
  it("reads plain symbols or objects carrying prices", () => {
    expect(readWatchlist(["AAPL", "MSFT"])).toEqual(["AAPL", "MSFT"]);
    expect(readWatchlist([{ ticker: "AAPL", price: 1 }])).toEqual(["AAPL"]);
    expect(readWatchlist({ tickers: [{ ticker: "MSFT" }] })).toEqual(["MSFT"]);
  });
});

describe("readChatActions", () => {
  it("labels trades and watchlist changes, marking rejected ones", () => {
    const actions = readChatActions({
      trades: [
        { ticker: "AAPL", side: "buy", quantity: 5 },
        { ticker: "NVDA", side: "buy", quantity: 900, error: "insufficient cash" },
      ],
      watchlist_changes: [{ ticker: "PYPL", action: "add" }],
    });
    expect(actions).toHaveLength(3);
    expect(actions[0]).toEqual({ kind: "trade", label: "BUY 5 AAPL", ok: true });
    expect(actions[1].ok).toBe(false);
    expect(actions[1].label).toContain("insufficient cash");
    expect(actions[2]).toEqual({ kind: "watchlist", label: "ADD PYPL", ok: true });
  });

  it("returns nothing when the reply carries no actions", () => {
    expect(readChatActions({ message: "hello" })).toEqual([]);
  });
});

describe("request error handling", () => {
  it("surfaces the reason from a TradeResult rejection", async () => {
    stubFetch(400, {
      success: false,
      error: "Insufficient cash: need $19,008,000.00, have $6,640.78",
      ticker: null,
    });
    await expect(submitTrade("AAPL", 100000, "buy")).rejects.toThrow(
      "Insufficient cash: need $19,008,000.00, have $6,640.78",
    );
  });

  it("surfaces the reason from a FastAPI detail rejection", async () => {
    stubFetch(400, { detail: "Ticker is required" });
    await expect(submitTrade("", 1, "buy")).rejects.toThrow("Ticker is required");
  });

  it("falls back to the status when the body explains nothing", async () => {
    stubFetch(500, {});
    await expect(submitTrade("AAPL", 1, "buy")).rejects.toThrow(
      "/api/portfolio/trade failed (500)",
    );
  });
});

describe("submitTrade", () => {
  it("reports the price the server filled at, not the one requested", async () => {
    stubFetch(200, {
      success: true,
      ticker: "VWXY",
      quantity: 1,
      price: 63.29,
      cash_balance: 9000,
    });
    await expect(submitTrade("vwxy", 1, "buy")).resolves.toEqual({
      ticker: "VWXY",
      quantity: 1,
      price: 63.29,
    });
  });
});

describe("fetchChatHistory", () => {
  it("restores messages oldest first and replays their actions", async () => {
    stubFetch(200, {
      messages: [
        { role: "user", content: "buy 5 aapl", actions: null },
        {
          role: "assistant",
          content: "Bought 5 AAPL.",
          actions: {
            trades: [{ ticker: "AAPL", side: "buy", quantity: 5, error: null }],
            watchlist_changes: [],
            errors: [],
          },
        },
      ],
    });

    const history = await fetchChatHistory();
    expect(history.map((m) => m.role)).toEqual(["user", "assistant"]);
    expect(history[0].actions).toBeUndefined();
    expect(history[1].actions).toEqual([
      { kind: "trade", label: "BUY 5 AAPL", ok: true },
    ]);
  });
});
