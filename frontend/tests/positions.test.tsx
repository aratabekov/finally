import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Positions, liveRow } from "@/components/Positions";
import type { Position, PriceTick } from "@/lib/types";

const position: Position = {
  ticker: "AAPL",
  quantity: 10,
  avg_cost: 100,
  current_price: 100,
  market_value: 1000,
  unrealized_pl: 0,
  pct_change: 0,
};

const tick: PriceTick = {
  ticker: "AAPL",
  price: 120,
  previous_price: 119,
  direction: "up",
  timestamp: "2026-08-09T12:00:00Z",
};

describe("liveRow", () => {
  it("revalues a position against the live price", () => {
    const row = liveRow(position, 120);
    expect(row.marketValue).toBe(1200);
    expect(row.pl).toBe(200);
    expect(row.pctChange).toBeCloseTo(20);
  });

  it("reports a loss when the price falls below average cost", () => {
    const row = liveRow(position, 80);
    expect(row.pl).toBe(-200);
    expect(row.pctChange).toBeCloseTo(-20);
  });
});

describe("Positions", () => {
  it("prefers the live price over the value returned by the API", () => {
    render(
      <Positions positions={[position]} prices={{ AAPL: tick }} onSelect={vi.fn()} />,
    );
    expect(screen.getByTestId("position-price-AAPL")).toHaveTextContent("120.00");
    expect(screen.getByTestId("position-pl-AAPL")).toHaveTextContent("+$200.00");
  });

  it("falls back to the API price when no tick has arrived", () => {
    render(<Positions positions={[position]} prices={{}} onSelect={vi.fn()} />);
    expect(screen.getByTestId("position-price-AAPL")).toHaveTextContent("100.00");
    expect(screen.getByTestId("position-pl-AAPL")).toHaveTextContent("+$0.00");
  });

  it("shows an empty state with no positions", () => {
    render(<Positions positions={[]} prices={{}} onSelect={vi.fn()} />);
    expect(screen.getByText("NO OPEN POSITIONS")).toBeInTheDocument();
  });
});
