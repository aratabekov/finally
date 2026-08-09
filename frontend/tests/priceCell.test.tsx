import { describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { PriceCell } from "@/components/PriceCell";

describe("PriceCell", () => {
  it("renders the price with two decimals", () => {
    render(<PriceCell price={190.4} testId="p" />);
    expect(screen.getByTestId("p")).toHaveTextContent("190.40");
  });

  it("flashes up on an uptick and down on a downtick", () => {
    const { rerender } = render(<PriceCell price={100} testId="p" />);
    expect(screen.getByTestId("p")).toHaveAttribute("data-flash", "none");

    rerender(<PriceCell price={101} testId="p" />);
    expect(screen.getByTestId("p").className).toContain("flash-up");

    rerender(<PriceCell price={99} testId="p" />);
    expect(screen.getByTestId("p").className).toContain("flash-down");
  });

  it("does not flash when the price is unchanged", () => {
    const { rerender } = render(<PriceCell price={100} testId="p" />);
    rerender(<PriceCell price={100} testId="p" />);
    expect(screen.getByTestId("p")).toHaveAttribute("data-flash", "none");
  });

  it("clears the flash after 500ms", () => {
    vi.useFakeTimers();
    try {
      const { rerender } = render(<PriceCell price={100} testId="p" />);
      rerender(<PriceCell price={105} testId="p" />);
      expect(screen.getByTestId("p")).toHaveAttribute("data-flash", "up");

      act(() => {
        vi.advanceTimersByTime(600);
      });
      expect(screen.getByTestId("p")).toHaveAttribute("data-flash", "none");
    } finally {
      vi.useRealTimers();
    }
  });
});
