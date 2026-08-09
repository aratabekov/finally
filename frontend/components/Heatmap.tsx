"use client";

import { ResponsiveContainer, Treemap } from "recharts";
import { Panel } from "./Panel";
import { fmtPct } from "@/lib/format";
import type { Position } from "@/lib/types";

type Props = { positions: Position[] };

type CellProps = {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  pct?: number;
  depth?: number;
};

/** Saturation encodes P&L magnitude; hue encodes its sign. */
function fill(pct: number): string {
  const intensity = Math.min(Math.abs(pct) / 5, 1);
  const alpha = (0.18 + 0.62 * intensity).toFixed(2);
  return pct >= 0 ? `rgba(46, 204, 143, ${alpha})` : `rgba(242, 84, 91, ${alpha})`;
}

function Cell(props: CellProps) {
  const { x = 0, y = 0, width = 0, height = 0, name = "", pct = 0, depth = 1 } = props;
  // Treemap also renders a root node covering the whole plot; only leaves are cells.
  if (depth === 0) return null;
  const roomy = width > 52 && height > 30;
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={fill(pct)}
        stroke="var(--color-panel)"
        strokeWidth={1}
      />
      {roomy ? (
        <>
          <text x={x + 6} y={y + 15} fill="var(--color-ink)" fontSize={11}>
            {name}
          </text>
          <text x={x + 6} y={y + 28} fill="var(--color-ink)" fontSize={10} opacity={0.75}>
            {fmtPct(pct)}
          </text>
        </>
      ) : null}
    </g>
  );
}

export function Heatmap({ positions }: Props) {
  const data = positions
    .filter((p) => p.market_value > 0)
    .map((p) => ({ name: p.ticker, size: p.market_value, pct: p.pct_change }));

  return (
    <Panel title="Exposure" stat={`${data.length} POS`} testId="heatmap">
      {data.length === 0 ? (
        <p className="flex flex-1 items-center justify-center text-[0.6875rem] tracking-[0.14em] text-dim">
          NO OPEN POSITIONS
        </p>
      ) : (
        <div className="min-h-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <Treemap
              data={data}
              dataKey="size"
              isAnimationActive={false}
              content={<Cell />}
            />
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}
