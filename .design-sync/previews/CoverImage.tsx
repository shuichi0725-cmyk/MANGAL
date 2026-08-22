import React from "react";
import { CoverImage } from "mangal";

/**
 * CoverImage renders with `fill`, so it needs a positioned, sized parent —
 * the 2:3 slot the catalogue rows use. It returns null when `src` is null or
 * the image fails, which is why callers make the whole slot conditional.
 */
const COVER =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 120'>" +
      "<rect width='80' height='120' fill='#d23f3f'/>" +
      "<rect x='5' y='5' width='70' height='110' fill='none' stroke='#fff' stroke-opacity='.7'/>" +
      "<text x='40' y='58' font-size='10' fill='#fff' text-anchor='middle'>MANGAL</text>" +
      "<text x='40' y='72' font-size='8' fill='#fff' fill-opacity='.8' text-anchor='middle'>1</text>" +
      "</svg>",
  );

/** The 64px catalogue slot. */
export function InCatalogueSlot() {
  return (
    <div className="relative w-16 aspect-[2/3] shrink-0 overflow-hidden rounded-md bg-[var(--color-surface-2)]">
      <CoverImage src={COVER} alt="ベルセルク 1巻 表紙" sizes="64px" />
    </div>
  );
}

/** A row of covers, as a volume shelf renders them. */
export function Shelf() {
  return (
    <div className="flex gap-2">
      {[1, 2, 3, 4].map((n) => (
        <div
          key={n}
          className="relative w-16 aspect-[2/3] shrink-0 overflow-hidden rounded-md bg-[var(--color-surface-2)]"
        >
          <CoverImage src={COVER} alt={`ベルセルク ${n}巻 表紙`} sizes="64px" />
        </div>
      ))}
    </div>
  );
}

/** `src: null` — the component renders nothing, so the slot shows its own fallback. */
export function NoSource() {
  return (
    <div className="relative w-16 aspect-[2/3] shrink-0 overflow-hidden rounded-md bg-[var(--color-surface-2)]">
      <CoverImage src={null} alt="表紙未取得" sizes="64px" />
      <span className="flex h-full items-center justify-center text-xl text-ink/20" aria-hidden="true">
        📖
      </span>
    </div>
  );
}
