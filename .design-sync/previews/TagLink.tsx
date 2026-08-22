import React from "react";
import { TagLink } from "mangal";

/** Outlined metadata values on a work page — a different family from chips. */
export function WorkMetadata() {
  return (
    <div style={{ maxWidth: 512 }} className="flex flex-wrap gap-2">
      <TagLink href="/author/togashi-yoshihiro">冨樫義博</TagLink>
      <TagLink href="/publisher/shueisha">集英社</TagLink>
      <TagLink href="/magazine/weekly-shonen-jump">週刊少年ジャンプ</TagLink>
      <TagLink href="/genre/adventure">冒険</TagLink>
      <TagLink href="/year/1998">1998年</TagLink>
    </div>
  );
}

/** A single value inline in a sentence-like meta row. */
export function SingleValue() {
  return (
    <p className="flex items-center gap-2 text-sm text-ink/70">
      掲載誌
      <TagLink href="/magazine/weekly-shonen-jump">週刊少年ジャンプ</TagLink>
    </p>
  );
}
