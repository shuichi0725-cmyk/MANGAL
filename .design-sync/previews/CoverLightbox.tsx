import React from "react";
import { CoverLightbox } from "mangal";

const COVER =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 120'>" +
      "<rect width='80' height='120' fill='#2f74d0'/>" +
      "<text x='40' y='64' font-size='10' fill='#fff' text-anchor='middle'>COVER</text>" +
      "</svg>",
  );

/** Closed state — the wrapped child is what the page shows until it is clicked. */
export function Closed() {
  return (
    <CoverLightbox src={COVER} label="ベルセルク 1巻 表紙">
      <div className="relative w-16 aspect-[2/3] cursor-zoom-in overflow-hidden rounded-md bg-[var(--color-surface-2)]">
        <img src={COVER} alt="ベルセルク 1巻 表紙" className="h-full w-full object-cover" />
      </div>
    </CoverLightbox>
  );
}

/** No source — the wrapper stays inert and just renders its child. */
export function WithoutSource() {
  return (
    <CoverLightbox src={null}>
      <div className="relative w-16 aspect-[2/3] overflow-hidden rounded-md bg-[var(--color-surface-2)]">
        <span className="flex h-full items-center justify-center text-xl text-ink/20" aria-hidden="true">
          📖
        </span>
      </div>
    </CoverLightbox>
  );
}
