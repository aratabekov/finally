"use client";

import {
  Area,
  AreaChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from "recharts";
import { Panel } from "./Panel";
import { fmtMoney, fmtPct, toneClass } from "@/lib/format";
import type { Snapshot } from "@/lib/types";

const START_EQUITY = 10_000;

type Props = { snapshots: Snapshot[]; liveValue: number };

export function PnlChart({ snapshots, liveValue }: Props) {
  const data = snapshots.map((snap) => ({
    label: snap.recorded_at,
    value: snap.total_value,
  }));
  if (liveValue > 0) data.push({ label: "now", value: liveValue });

  const first = data[0]?.value ?? START_EQUITY;
  const last = data.at(-1)?.value ?? START_EQUITY;
  const changePct = first ? ((last - first) / first) * 100 : 0;
  const stroke = changePct >= 0 ? "var(--color-up)" : "var(--color-down)";

  return (
    <Panel
      title="Equity curve"
      testId="pnl-chart"
      stat={<span className={toneClass(changePct)}>{fmtPct(changePct)}</span>}
    >
      {data.length < 2 ? (
        <p className="flex flex-1 items-center justify-center text-[0.6875rem] tracking-[0.14em] text-dim">
          AWAITING FIRST SNAPSHOT
        </p>
      ) : (
        <div className="min-h-0 flex-1 p-1">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 6, right: 4, bottom: 4, left: 0 }}>
              <defs>
                <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={stroke} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={stroke} stopOpacity={0} />
                </linearGradient>
              </defs>
              <YAxis
                domain={["auto", "auto"]}
                orientation="right"
                width={54}
                tick={{ fill: "var(--color-dim)", fontSize: 9 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value: number) => value.toFixed(0)}
              />
              <ReferenceLine
                y={first}
                stroke="var(--color-rule)"
                strokeDasharray="3 3"
              />
              <Tooltip
                contentStyle={{
                  background: "var(--color-panel-hi)",
                  border: "1px solid var(--color-rule)",
                  fontSize: 11,
                }}
                labelFormatter={() => ""}
                formatter={(value) => [fmtMoney(Number(value)), "Equity"]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={stroke}
                strokeWidth={1.5}
                fill="url(#pnlFill)"
                isAnimationActive={false}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}
