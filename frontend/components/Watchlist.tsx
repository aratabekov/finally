"use client";

import { useState } from "react";
import { Panel } from "./Panel";
import { PriceCell } from "./PriceCell";
import { Sparkline } from "./Sparkline";
import { fmtPct } from "@/lib/format";
import type { PriceTick } from "@/lib/types";

type Props = {
  tickers: string[];
  prices: Record<string, PriceTick>;
  series: Record<string, number[]>;
  prevCloses: Record<string, number>;
  selected: string;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (ticker: string) => Promise<void>;
};

const UP = "#2ecc8f";
const DOWN = "#f2545b";
const FLAT = "#79839a";

export function Watchlist({
  tickers,
  prices,
  series,
  prevCloses,
  selected,
  onSelect,
  onAdd,
  onRemove,
}: Props) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");

  async function add(event: React.FormEvent) {
    event.preventDefault();
    const ticker = draft.trim().toUpperCase();
    if (!ticker) return;
    setError("");
    try {
      await onAdd(ticker);
      setDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add ticker");
    }
  }

  return (
    <Panel title="Watchlist" stat={`${tickers.length} SYM`} testId="watchlist">
      <div className="flex items-center gap-2 border-b border-rule-soft px-2 py-1 text-[0.5625rem] tracking-[0.16em] text-dim">
        <span className="w-12">SYM</span>
        <span className="w-14">TREND</span>
        <span className="ml-auto w-16 pr-1 text-right">LAST</span>
        <span className="w-14 text-right">CHG</span>
      </div>

      <div className="scroll-thin flex-1 overflow-y-auto">
        {tickers.map((ticker) => {
          const tick = prices[ticker];
          const price = tick?.price ?? 0;
          const base = prevCloses[ticker] ?? series[ticker]?.[0] ?? price;
          const changePct = base ? ((price - base) / base) * 100 : 0;
          const tone =
            changePct > 0 ? "text-up" : changePct < 0 ? "text-down" : "text-muted";
          const isSelected = ticker === selected;

          return (
            <div
              key={ticker}
              data-testid={`watchlist-row-${ticker}`}
              data-selected={isSelected}
              className={`group relative flex cursor-pointer items-center gap-2 border-b border-rule-soft px-2 py-1.5 text-[0.8125rem] hover:bg-panel-hi ${
                isSelected ? "bg-panel-hi" : ""
              }`}
              onClick={() => onSelect(ticker)}
            >
              <span
                className={`absolute inset-y-0 left-0 w-0.5 ${
                  isSelected ? "bg-accent" : "bg-transparent"
                }`}
              />
              <span className={`w-12 ${isSelected ? "text-accent" : "text-ink"}`}>
                {ticker}
              </span>
              <Sparkline
                points={series[ticker] ?? []}
                color={changePct > 0 ? UP : changePct < 0 ? DOWN : FLAT}
              />
              <PriceCell
                price={price}
                testId={`price-${ticker}`}
                className="ml-auto w-16 text-right"
              />
              <span
                data-testid={`change-${ticker}`}
                className={`w-14 text-right text-[0.75rem] ${tone}`}
              >
                {fmtPct(changePct)}
              </span>
              <button
                type="button"
                data-testid={`watchlist-remove-${ticker}`}
                aria-label={`Remove ${ticker}`}
                className="absolute right-1 hidden h-4 w-4 items-center justify-center rounded-xs bg-rule text-[0.625rem] text-muted hover:text-down group-hover:flex"
                onClick={(event) => {
                  event.stopPropagation();
                  onRemove(ticker).catch(() => undefined);
                }}
              >
                x
              </button>
            </div>
          );
        })}
      </div>

      <form
        onSubmit={add}
        className="flex flex-none items-center gap-1 border-t border-rule px-2 py-1.5"
      >
        <span className="text-accent">+</span>
        <input
          data-testid="watchlist-input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="add symbol"
          maxLength={8}
          className="w-full bg-transparent text-[0.8125rem] uppercase placeholder:text-dim placeholder:normal-case focus:outline-none"
        />
        <button
          type="submit"
          data-testid="watchlist-add"
          className="rounded-xs border border-rule px-2 py-0.5 text-[0.625rem] tracking-[0.14em] text-muted hover:border-blue hover:text-blue"
        >
          ADD
        </button>
      </form>
      {error ? (
        <p data-testid="watchlist-error" className="px-2 pb-1 text-[0.6875rem] text-down">
          {error}
        </p>
      ) : null}
    </Panel>
  );
}
