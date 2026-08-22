import React from "react";
import { LikeButtonMock } from "mangal";

/** Resting state — the count comes straight from `base`. */
export function Resting() {
  return <LikeButtonMock id="hunter-x-hunter" base={128} />;
}

/** A quiet page — small counts read differently from popular ones. */
export function LowCount() {
  return <LikeButtonMock id="yoroshiku-mechadoc" base={3} />;
}

/** Several rows, as a list of works shows them. */
export function InList() {
  const rows = [
    { id: "berserk", title: "ベルセルク", base: 942 },
    { id: "versailles-no-bara", title: "ベルサイユのばら", base: 310 },
    { id: "kyojin-no-hoshi", title: "巨人の星", base: 57 },
  ];
  return (
    <div className="max-w-sm space-y-2">
      {rows.map((r) => (
        <div key={r.id} className="flex items-center justify-between gap-2">
          <span className="truncate text-sm">{r.title}</span>
          <LikeButtonMock id={r.id} base={r.base} />
        </div>
      ))}
    </div>
  );
}
