import type { ReactNode } from "react";

type Props = {
  title: string;
  stat?: ReactNode;
  children: ReactNode;
  className?: string;
  testId?: string;
};

/** Hairline-ruled panel: a mono micro-label left, a live micro-stat right. */
export function Panel({ title, stat, children, className = "", testId }: Props) {
  return (
    <section className={`panel ${className}`} data-testid={testId}>
      <header className="panel-head">
        <span className="panel-title">{title}</span>
        {stat ? <span className="panel-stat">{stat}</span> : null}
      </header>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </section>
  );
}
