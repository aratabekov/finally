"use client";

import { Panel } from "./Panel";
import { PriceCell } from "./PriceCell";
import { fmtMoney, fmtPct, fmtQty, fmtSignedMoney, toneClass } from "@/lib/format";
import type { Position, PriceTick } from "@/lib/types";

type Props = {
  positions: Position[];
  prices: Record<string, PriceTick>;
  onSelect: (ticker: string) => void;
  className?: string;
};

const HEAD = "px-2 py-1 text-[0.5625rem] tracking-[0.16em] text-dim";

/** Revalues a REST position against the live tape. */
export function liveRow(position: Position, price: number) {
  const marketValue = position.quantity * price;
  const cost = position.quantity * position.avg_cost;
  const pl = marketValue - cost;
  return {
    price,
    marketValue,
    pl,
    pctChange: cost ? (pl / cost) * 100 : 0,
  };
}

export function Positions({ positions, prices, onSelect, className }: Props) {
  const totalPl = positions.reduce((sum, p) => {
    const price = prices[p.ticker]?.price ?? p.current_price;
    return sum + liveRow(p, price).pl;
  }, 0);

  return (
    <Panel
      title="Positions"
      testId="positions"
      className={className}
      stat={<span className={toneClass(totalPl)}>{fmtSignedMoney(totalPl)}</span>}
    >
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        <table className="w-full border-collapse text-[0.8125rem]" data-testid="positions-table">
          <thead className="sticky top-0 bg-panel">
            <tr className="border-b border-rule-soft text-left">
              <th className={HEAD}>SYM</th>
              <th className={`${HEAD} text-right`}>QTY</th>
              <th className={`${HEAD} text-right`}>AVG COST</th>
              <th className={`${HEAD} text-right`}>LAST</th>
              <th className={`${HEAD} text-right`}>MKT VAL</th>
              <th className={`${HEAD} text-right`}>UNREAL P&L</th>
              <th className={`${HEAD} text-right`}>CHG</th>
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-2 py-6 text-center text-[0.6875rem] tracking-[0.14em] text-dim"
                >
                  NO OPEN POSITIONS
                </td>
              </tr>
            ) : (
              positions.map((position) => {
                const price = prices[position.ticker]?.price ?? position.current_price;
                const row = liveRow(position, price);
                return (
                  <tr
                    key={position.ticker}
                    data-testid={`position-row-${position.ticker}`}
                    onClick={() => onSelect(position.ticker)}
                    className="cursor-pointer border-b border-rule-soft hover:bg-panel-hi"
                  >
                    <td className="px-2 py-1 text-accent">{position.ticker}</td>
                    <td className="px-2 py-1 text-right">{fmtQty(position.quantity)}</td>
                    <td className="px-2 py-1 text-right text-muted">
                      {fmtMoney(position.avg_cost)}
                    </td>
                    <td className="py-1 pr-1 text-right">
                      <PriceCell price={row.price} testId={`position-price-${position.ticker}`} />
                    </td>
                    <td className="px-2 py-1 text-right text-muted">
                      {fmtMoney(row.marketValue)}
                    </td>
                    <td
                      className={`px-2 py-1 text-right ${toneClass(row.pl)}`}
                      data-testid={`position-pl-${position.ticker}`}
                    >
                      {fmtSignedMoney(row.pl)}
                    </td>
                    <td className={`px-2 py-1 text-right ${toneClass(row.pctChange)}`}>
                      {fmtPct(row.pctChange)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
