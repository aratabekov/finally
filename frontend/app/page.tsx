"use client";

import { useEffect, useMemo, useState } from "react";
import { Chat } from "@/components/Chat";
import { CommandRail } from "@/components/CommandRail";
import { Header } from "@/components/Header";
import { Heatmap } from "@/components/Heatmap";
import { MainChart } from "@/components/MainChart";
import { PnlChart } from "@/components/PnlChart";
import { Positions } from "@/components/Positions";
import { Watchlist } from "@/components/Watchlist";
import { usePriceStream } from "@/lib/usePriceStream";
import { useTerminalData } from "@/lib/useTerminalData";

function useClock(): string {
  const [now, setNow] = useState("--:--:--");
  useEffect(() => {
    const tick = () => setNow(new Date().toTimeString().slice(0, 8));
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, []);
  return now;
}

export default function Terminal() {
  const { prices, series, status } = usePriceStream();
  const {
    portfolio,
    snapshots,
    watchlist,
    prevCloses,
    refresh,
    addToWatchlist,
    removeFromWatchlist,
  } = useTerminalData();
  const [picked, setSelected] = useState("AAPL");
  const [chatOpen, setChatOpen] = useState(true);
  const clock = useClock();

  // Fall back to the top of the watchlist until the picked ticker is on it.
  const selected =
    watchlist.length > 0 && !watchlist.includes(picked) ? watchlist[0] : picked;

  const totals = useMemo(() => {
    let held = 0;
    let cost = 0;
    for (const position of portfolio.positions) {
      const price = prices[position.ticker]?.price ?? position.current_price;
      held += position.quantity * price;
      cost += position.quantity * position.avg_cost;
    }
    const unrealized = held - cost;
    return {
      totalValue: portfolio.cash + held,
      unrealized,
      unrealizedPct: cost ? (unrealized / cost) * 100 : 0,
    };
  }, [portfolio, prices]);

  return (
    <div className="flex h-full flex-col">
      <Header
        totalValue={totals.totalValue}
        cash={portfolio.cash}
        dayChange={totals.unrealized}
        dayChangePct={totals.unrealizedPct}
        status={status}
        clock={clock}
      />

      <main
        className="grid min-h-0 flex-1 gap-1.5 p-1.5"
        style={{
          gridTemplateColumns: chatOpen
            ? "280px minmax(0, 1fr) 360px"
            : "280px minmax(0, 1fr) 2.25rem",
        }}
      >
        <Watchlist
          tickers={watchlist}
          prices={prices}
          series={series}
          prevCloses={prevCloses}
          selected={selected}
          onSelect={setSelected}
          onAdd={addToWatchlist}
          onRemove={removeFromWatchlist}
        />

        <div className="flex min-h-0 min-w-0 flex-col gap-1.5">
          <MainChart
            ticker={selected}
            tick={prices[selected]}
            series={series[selected] ?? []}
            prevClose={prevCloses[selected]}
          />
          <div className="grid h-44 flex-none grid-cols-2 gap-1.5">
            <Heatmap positions={portfolio.positions} />
            <PnlChart snapshots={snapshots} liveValue={totals.totalValue} />
          </div>
          <Positions
            positions={portfolio.positions}
            prices={prices}
            onSelect={setSelected}
            className="h-52 flex-none"
          />
        </div>

        {chatOpen ? (
          <Chat onCollapse={() => setChatOpen(false)} onActions={refresh} />
        ) : (
          <button
            type="button"
            data-testid="chat-expand"
            onClick={() => setChatOpen(true)}
            aria-label="Open assistant"
            className="panel items-center justify-center gap-2 py-3 text-[0.625rem] tracking-[0.2em] text-muted hover:text-accent"
          >
            <span style={{ writingMode: "vertical-rl" }}>ALLY</span>
          </button>
        )}
      </main>

      <CommandRail ticker={selected} prices={prices} onFilled={refresh} />
    </div>
  );
}
