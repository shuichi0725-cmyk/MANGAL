import React from "react";
import { MarqueeTitle } from "mangal";

/** Fits the box — no motion, plain static text. */
export function ShortTitle() {
  return (
    <div style={{ width: 256 }} className="rounded-card border border-[var(--color-line)] p-2">
      <MarqueeTitle text="ベルセルク" className="text-base font-bold leading-tight" />
    </div>
  );
}

/** Overflows — the title scrolls back and forth instead of truncating. */
export function LongTitle() {
  return (
    <div style={{ width: 256 }} className="rounded-card border border-[var(--color-line)] p-2">
      <MarqueeTitle
        text="ハズレスキル《影が薄い》を持つギルド職員が、実は伝説の暗殺者"
        className="text-base font-bold leading-tight"
      />
    </div>
  );
}

/** Several widths at once — where the switch from static to scrolling happens. */
export function WidthComparison() {
  const text = "転生したらスライムだった件";
  return (
    <div className="space-y-2">
      {[320, 200, 120].map((w) => (
        <div key={w} style={{ width: w }} className="rounded-card border border-[var(--color-line)] p-2">
          <MarqueeTitle text={text} className="text-sm font-bold leading-tight" />
        </div>
      ))}
    </div>
  );
}
