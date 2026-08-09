"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Panel } from "./Panel";
import { fetchBars } from "@/lib/api";
import { fmtDay, fmtPct, fmtPrice, toneClass } from "@/lib/format";
import type { Bar, PriceTick } from "@/lib/types";

type Range = "LIVE" | "30D" | "90D";

const RANGES: Range[] = ["LIVE", "30D", "90D"];

type Props = {
  ticker: string;
  tick?: PriceTick;
  series: number[];
  prevClose?: number;
};

export function MainChart({ ticker, tick, series, prevClose }: Props) {
  const [range, setRange] = useState<Range>("90D");
  const [loaded, setLoaded] = useState<{ ticker: string; bars: Bar[] }>({
    ticker,
    bars: [],
  });

  useEffect(() => {
    fetchBars(ticker, 90)
      .then((bars) => setLoaded({ ticker, bars }))
      .catch(() => undefined);
  }, [ticker]);

  const data = useMemo(() => {
    if (range === "LIVE") {
      return series.map((value, index) => ({ label: String(index), value }));
    }
    // Bars for a ticker we have since navigated away from are stale.
    const bars = loaded.ticker === ticker ? loaded.bars : [];
    const window = range === "30D" ? 30 : 90;
    return bars.slice(-window).map((bar) => ({ label: fmtDay(bar.t), value: bar.c }));
  }, [range, series, loaded, ticker]);

  const price = tick?.price ?? data.at(-1)?.value ?? 0;
  const base = prevClose ?? series[0] ?? price;
  const changePct = base ? ((price - base) / base) * 100 : 0;
  const stroke = changePct >= 0 ? "var(--color-up)" : "var(--color-down)";

  return (
    <Panel
      title={ticker}
      testId="main-chart"
      stat={
        <span className="flex items-center gap-3">
          <span className="text-base text-ink" data-testid="main-chart-price">
            {fmtPrice(price)}
          </span>
          <span className={toneClass(changePct)}>{fmtPct(changePct)}</span>
          <span className="flex overflow-hidden rounded-xs border border-rule">
            {RANGES.map((option) => (
              <button
                key={option}
                type="button"
                data-testid={`range-${option}`}
                onClick={() => setRange(option)}
                className={`px-2 py-0.5 text-[0.625rem] tracking-[0.12em] ${
                  range === option
                    ? "bg-blue/20 text-blue"
                    : "text-dim hover:text-muted"
                }`}
              >
                {option}
              </button>
            ))}
          </span>
        </span>
      }
      className="flex-1"
    >
      <div className="min-h-0 flex-1 p-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity={0.28} />
                <stop offset="100%" stopColor={stroke} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--color-rule-soft)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "var(--color-dim)", fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: "var(--color-rule)" }}
              minTickGap={40}
            />
            <YAxis
              domain={["auto", "auto"]}
              orientation="right"
              width={56}
              tick={{ fill: "var(--color-dim)", fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) => fmtPrice(value)}
            />
            <Tooltip
              contentStyle={{
                background: "var(--color-panel-hi)",
                border: "1px solid var(--color-rule)",
                fontSize: 11,
              }}
              labelStyle={{ color: "var(--color-muted)" }}
              formatter={(value) => [fmtPrice(Number(value)), ticker]}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke={stroke}
              strokeWidth={1.5}
              fill="url(#chartFill)"
              isAnimationActive={false}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}
