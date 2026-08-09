"use client";

import { useState } from "react";
import { submitTrade } from "@/lib/api";
import { fmtMoney } from "@/lib/format";
import type { PriceTick, TradeSide } from "@/lib/types";

type Props = {
  ticker: string;
  prices: Record<string, PriceTick>;
  onFilled: () => Promise<void>;
};

const FIELD =
  "w-full bg-transparent px-1 py-0.5 text-[0.875rem] uppercase text-ink focus:outline-none";

/**
 * The order rail: a persistent command prompt docked to the bottom of the
 * terminal. Market orders only, filled instantly at the live price.
 */
export function CommandRail({ ticker, prices, onFilled }: Props) {
  const [symbol, setSymbol] = useState(ticker);
  const [quantity, setQuantity] = useState("10");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [failed, setFailed] = useState(false);

  // Selecting a ticker elsewhere in the terminal loads it into the rail.
  const [lastTicker, setLastTicker] = useState(ticker);
  if (ticker !== lastTicker) {
    setLastTicker(ticker);
    setSymbol(ticker);
  }

  const upper = symbol.trim().toUpperCase();
  const qty = Number(quantity);
  const price = prices[upper]?.price ?? 0;
  const estimate = qty > 0 && price > 0 ? qty * price : 0;

  async function place(side: TradeSide) {
    if (!upper || !Number.isFinite(qty) || qty <= 0) {
      setFailed(true);
      setStatus("Enter a symbol and a quantity above zero.");
      return;
    }
    setBusy(true);
    setFailed(false);
    try {
      const fill = await submitTrade(upper, qty, side);
      const stamp = new Date().toTimeString().slice(0, 8);
      // Echo the server's fill price, not the last price seen on the tape.
      setStatus(
        `${stamp}  ${side.toUpperCase()} ${qty} ${upper} at ${fmtMoney(fill.price)}`,
      );
      await onFilled();
    } catch (err) {
      setFailed(true);
      setStatus(err instanceof Error ? err.message : "Order rejected.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <footer
      data-testid="trade-bar"
      className="flex h-12 flex-none items-stretch border-t border-rule bg-panel"
    >
      <span className="flex items-center px-3 text-[0.6875rem] tracking-[0.2em] text-accent">
        ORDER
      </span>

      <label className="flex w-36 flex-col justify-center border-l border-rule px-2">
        <span className="text-[0.5625rem] tracking-[0.16em] text-dim">SYMBOL</span>
        <input
          data-testid="trade-ticker"
          value={symbol}
          maxLength={8}
          onChange={(event) => setSymbol(event.target.value)}
          className={FIELD}
          aria-label="Order symbol"
        />
      </label>

      <label className="flex w-32 flex-col justify-center border-l border-rule px-2">
        <span className="text-[0.5625rem] tracking-[0.16em] text-dim">QUANTITY</span>
        <input
          data-testid="trade-quantity"
          value={quantity}
          inputMode="decimal"
          onChange={(event) => setQuantity(event.target.value)}
          className={FIELD}
          aria-label="Order quantity"
        />
      </label>

      <div className="flex w-40 flex-col justify-center border-l border-rule px-2">
        <span className="text-[0.5625rem] tracking-[0.16em] text-dim">ESTIMATED</span>
        <span className="px-1 text-[0.875rem] text-muted" data-testid="trade-estimate">
          {estimate ? fmtMoney(estimate) : "--"}
        </span>
      </div>

      <div className="flex items-center gap-2 border-l border-rule px-3">
        <button
          type="button"
          data-testid="trade-buy"
          disabled={busy}
          onClick={() => place("buy")}
          className="flex h-8 items-center gap-2 rounded-xs bg-purple px-4 text-[0.75rem] tracking-[0.16em] text-ink hover:brightness-125 disabled:opacity-50"
        >
          <span className="text-up">&#9650;</span> BUY
        </button>
        <button
          type="button"
          data-testid="trade-sell"
          disabled={busy}
          onClick={() => place("sell")}
          className="flex h-8 items-center gap-2 rounded-xs border border-purple bg-panel-hi px-4 text-[0.75rem] tracking-[0.16em] text-ink hover:brightness-125 disabled:opacity-50"
        >
          <span className="text-down">&#9660;</span> SELL
        </button>
      </div>

      <p
        data-testid="trade-status"
        className={`flex flex-1 items-center px-3 text-[0.75rem] ${
          failed ? "text-down" : "text-muted"
        }`}
      >
        {busy ? "Working..." : status}
      </p>
    </footer>
  );
}
