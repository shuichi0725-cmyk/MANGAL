import React from "react";
import { CatPict } from "mangal";

/**
 * The icons are gated by CSS: `.cat-svg { display: none }` unless an ancestor
 * carries `.theme-d3`. Every cell wraps in that class, exactly as the D3 theme
 * does on /browse.
 */
const KEYS = ["anime", "done", "ongoing", "kodomo", "shounen", "seinen", "shoujo", "josei"];
const LABEL: Record<string, string> = {
  anime: "アニメ化", done: "完結", ongoing: "連載中", kodomo: "児童",
  shounen: "少年", seinen: "青年", shoujo: "少女", josei: "女性",
};

/** Every icon in the set, labelled. */
export function AllIcons() {
  return (
    <div className="theme-d3 grid max-w-md grid-cols-4 gap-4">
      {KEYS.map((k) => (
        <div key={k} className="flex flex-col items-center gap-1">
          <CatPict k={k} />
          <span style={{ fontSize: 10 }} className="text-ink/60">{LABEL[k]}</span>
        </div>
      ))}
    </div>
  );
}

/** Inside the category cards it ships in — icon over label and count. */
export function InCategoryCards() {
  return (
    <div className="theme-d3 grid max-w-md grid-cols-3 gap-2">
      {["shounen", "seinen", "shoujo"].map((k) => (
        <div key={k} className="tactile rounded-card px-3 py-4 text-center">
          <CatPict k={k} className="h-7 w-7" />
          <p className="mt-2 text-xs font-medium">{LABEL[k]}</p>
          <p style={{ fontSize: 10 }} className="text-ink/50">12,480作品</p>
        </div>
      ))}
    </div>
  );
}

/** Scaled up via className — the stroke stays hairline. */
export function Sizes() {
  return (
    <div className="theme-d3 flex items-end gap-4">
      <CatPict k="ongoing" className="h-4 w-4" />
      <CatPict k="ongoing" className="h-6 w-6" />
      <CatPict k="ongoing" className="h-10 w-10" />
      <CatPict k="ongoing" className="h-10 w-10" />
    </div>
  );
}
