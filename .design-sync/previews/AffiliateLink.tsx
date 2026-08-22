import React from "react";
import { AffiliateLink } from "mangal";

/**
 * The buy button. It reads the global purchase mode (print vs ebook) through
 * `usePurchaseMode`, which returns a safe "print" default outside the
 * provider — so it renders standalone. The associate tag is intentionally
 * empty in design artifacts, so links carry no tracking id.
 */
const volume = { number: 1, release_date: "1990-11-24", isbn13: "9784592132011" };
const manga = {
  slug: "berserk",
  title: "ベルセルク",
  editions: [{ label: "通常版", publisher: "白泉社", volumes: [volume] }],
};

/** The accent-filled button as the volume list renders it. */
export function BuyButton() {
  return (
    <AffiliateLink
      manga={manga}
      volume={volume}
      labelPrefix="ベルセルク 通常版 第1巻"
      className="mode-recolor inline-flex items-center rounded-chip bg-[var(--color-accent)] px-3 py-1.5 text-xs font-medium text-[var(--color-on-accent)]"
    />
  );
}

/** Falling back to the work's primary volume when no volume is passed. */
export function PrimaryVolume() {
  return (
    <AffiliateLink
      manga={manga}
      labelPrefix="ベルセルク"
      className="mode-recolor inline-flex items-center rounded-chip bg-[var(--color-accent)] px-3 py-1.5 text-xs font-medium text-[var(--color-on-accent)]"
    />
  );
}

/** Repeated down a volume list — one button per volume. */
export function PerVolume() {
  const vols = [1, 2, 3].map((n) => ({
    number: n,
    release_date: `199${n}-01-24`,
    isbn13: `978459213201${n}`,
  }));
  return (
    <div className="max-w-sm space-y-2">
      {vols.map((v) => (
        <div key={v.number} className="flex items-center justify-between gap-2">
          <span className="text-sm">第{v.number}巻</span>
          <AffiliateLink
            manga={manga}
            volume={v}
            labelPrefix={`ベルセルク 第${v.number}巻`}
            className="mode-recolor inline-flex items-center rounded-chip bg-[var(--color-accent)] px-3 py-1.5 text-xs font-medium text-[var(--color-on-accent)]"
          />
        </div>
      ))}
    </div>
  );
}
