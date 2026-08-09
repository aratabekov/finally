"use client";

import { fmtMoney, fmtPct, fmtSignedMoney, toneClass } from "@/lib/format";
import type { ConnectionStatus } from "@/lib/types";

const STATUS_LABEL: Record<ConnectionStatus, string> = {
  connected: "LIVE",
  reconnecting: "RECONNECTING",
  disconnected: "OFFLINE",
};

const STATUS_COLOR: Record<ConnectionStatus, string> = {
  connected: "bg-up",
  reconnecting: "bg-accent",
  disconnected: "bg-down",
};

type Props = {
  totalValue: number;
  cash: number;
  dayChange: number;
  dayChangePct: number;
  status: ConnectionStatus;
  clock: string;
};

function Stat({
  label,
  value,
  tone = "text-ink",
  testId,
}: {
  label: string;
  value: string;
  tone?: string;
  testId?: string;
}) {
  return (
    <div className="flex h-full flex-col justify-center border-l border-rule px-4">
      <span className="text-[0.5625rem] tracking-[0.18em] text-dim">{label}</span>
      <span className={`text-[0.9375rem] leading-tight ${tone}`} data-testid={testId}>
        {value}
      </span>
    </div>
  );
}

export function Header({
  totalValue,
  cash,
  dayChange,
  dayChangePct,
  status,
  clock,
}: Props) {
  return (
    <header className="flex h-14 flex-none items-stretch border-b border-rule bg-panel">
      <div className="flex items-center gap-2 px-4">
        <span className="text-lg font-semibold tracking-[0.24em] text-ink">
          FIN<span className="text-accent">ALLY</span>
        </span>
        <span className="mt-1 hidden text-[0.5625rem] tracking-[0.18em] text-dim md:inline">
          TRADING TERMINAL
        </span>
      </div>

      <Stat label="NET LIQUIDATION" value={fmtMoney(totalValue)} testId="portfolio-total" />
      <Stat
        label="UNREALIZED P&L"
        value={`${fmtSignedMoney(dayChange)}  ${fmtPct(dayChangePct)}`}
        tone={toneClass(dayChange)}
        testId="portfolio-pl"
      />
      <Stat label="CASH" value={fmtMoney(cash)} testId="cash-balance" />

      <div className="ml-auto flex items-center gap-4 border-l border-rule px-4">
        <span className="text-[0.6875rem] tracking-[0.14em] text-muted" data-testid="clock">
          {clock}
        </span>
        <span className="flex items-center gap-2">
          <span
            data-testid="connection-dot"
            data-status={status}
            className={`h-2 w-2 rounded-full ${STATUS_COLOR[status]} ${
              status === "connected" ? "dot-live" : ""
            }`}
          />
          <span className="text-[0.6875rem] tracking-[0.14em] text-muted">
            {STATUS_LABEL[status]}
          </span>
        </span>
      </div>
    </header>
  );
}
