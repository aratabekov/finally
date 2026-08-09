"use client";

import { useEffect, useRef, useState } from "react";
import { fmtPrice } from "@/lib/format";

type Flash = { dir: "up" | "down"; seq: number } | null;

type Props = {
  price: number;
  testId?: string;
  className?: string;
};

/**
 * Price readout that tints green on an uptick and red on a downtick, decaying
 * over 500ms. `seq` remounts the node so back-to-back upticks replay the
 * animation instead of holding a static class.
 */
export function PriceCell({ price, testId, className = "" }: Props) {
  const previous = useRef(price);
  const [flash, setFlash] = useState<Flash>(null);

  useEffect(() => {
    if (price !== previous.current) {
      const dir = price > previous.current ? "up" : "down";
      previous.current = price;
      setFlash((prev) => ({ dir, seq: (prev?.seq ?? 0) + 1 }));
    }
  }, [price]);

  useEffect(() => {
    if (!flash) return;
    const timer = setTimeout(() => setFlash(null), 500);
    return () => clearTimeout(timer);
  }, [flash]);

  return (
    <span
      key={flash?.seq ?? 0}
      data-testid={testId}
      data-flash={flash?.dir ?? "none"}
      className={`inline-block px-1 ${flash ? `flash-${flash.dir}` : ""} ${className}`}
    >
      {fmtPrice(price)}
    </span>
  );
}
