import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Watchlist } from "@/components/Watchlist";
import type { PriceTick } from "@/lib/types";

const tick = (ticker: string, price: number): PriceTick => ({
  ticker,
  price,
  previous_price: price,
  direction: "flat",
  timestamp: "2026-08-09T12:00:00Z",
});

function setup(overrides: Partial<React.ComponentProps<typeof Watchlist>> = {}) {
  const props = {
    tickers: ["AAPL", "MSFT"],
    prices: { AAPL: tick("AAPL", 110), MSFT: tick("MSFT", 90) },
    series: { AAPL: [100, 105, 110], MSFT: [100, 95, 90] },
    prevCloses: { AAPL: 100, MSFT: 100 },
    selected: "AAPL",
    onSelect: vi.fn(),
    onAdd: vi.fn().mockResolvedValue(undefined),
    onRemove: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
  render(<Watchlist {...props} />);
  return props;
}

describe("Watchlist", () => {
  it("shows each ticker with its price and change against the prior close", () => {
    setup();
    expect(screen.getByTestId("price-AAPL")).toHaveTextContent("110.00");
    expect(screen.getByTestId("change-AAPL")).toHaveTextContent("+10.00%");
    expect(screen.getByTestId("change-MSFT")).toHaveTextContent("-10.00%");
  });

  it("marks the selected row and selects on click", async () => {
    const props = setup();
    expect(screen.getByTestId("watchlist-row-AAPL")).toHaveAttribute(
      "data-selected",
      "true",
    );
    await userEvent.click(screen.getByTestId("watchlist-row-MSFT"));
    expect(props.onSelect).toHaveBeenCalledWith("MSFT");
  });

  it("adds a ticker in upper case and clears the field", async () => {
    const props = setup();
    await userEvent.type(screen.getByTestId("watchlist-input"), "pypl");
    await userEvent.click(screen.getByTestId("watchlist-add"));
    expect(props.onAdd).toHaveBeenCalledWith("PYPL");
    expect(screen.getByTestId("watchlist-input")).toHaveValue("");
  });

  it("reports why an add failed", async () => {
    const props = setup({
      onAdd: vi.fn().mockRejectedValue(new Error("Unknown ticker ZZZZ")),
    });
    await userEvent.type(screen.getByTestId("watchlist-input"), "ZZZZ");
    await userEvent.click(screen.getByTestId("watchlist-add"));
    expect(props.onAdd).toHaveBeenCalled();
    expect(await screen.findByTestId("watchlist-error")).toHaveTextContent(
      "Unknown ticker ZZZZ",
    );
  });

  it("removes a ticker without selecting it", async () => {
    const props = setup();
    await userEvent.click(screen.getByTestId("watchlist-remove-MSFT"));
    expect(props.onRemove).toHaveBeenCalledWith("MSFT");
    expect(props.onSelect).not.toHaveBeenCalled();
  });
});
