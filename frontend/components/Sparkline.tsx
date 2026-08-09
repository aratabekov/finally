type Props = {
  points: number[];
  color: string;
  width?: number;
  height?: number;
};

/**
 * Hand-rolled SVG spark: one path per watchlist row redrawn several times a
 * second, so it stays cheaper than a full charting component.
 */
export function Sparkline({ points, color, width = 56, height = 16 }: Props) {
  if (points.length < 2) {
    return (
      <svg width={width} height={height} aria-hidden>
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="var(--color-rule)"
          strokeDasharray="2 3"
        />
      </svg>
    );
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const step = width / (points.length - 1);
  const d = points
    .map((p, i) => {
      const x = (i * step).toFixed(2);
      const y = (height - ((p - min) / span) * (height - 2) - 1).toFixed(2);
      return `${i === 0 ? "M" : "L"}${x} ${y}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} aria-hidden>
      <path d={d} fill="none" stroke={color} strokeWidth={1.25} />
    </svg>
  );
}
