import React from "react";
import { LikeButton } from "mangal";

/**
 * The live control. It reads its own count from `/api/like`, which no preview
 * host serves — so what renders here is the pre-count resting state, exactly
 * what a visitor sees before the request settles.
 */
export function Resting() {
  return <LikeButton id="hunter-x-hunter" />;
}

/** In the row it ships in, beside a title. */
export function InRow() {
  return (
    <div className="flex max-w-sm items-center justify-between gap-2">
      <span className="truncate text-sm font-bold">ハンター×ハンター</span>
      <LikeButton id="hunter-x-hunter" />
    </div>
  );
}
