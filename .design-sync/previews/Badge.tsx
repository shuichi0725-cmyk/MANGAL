import React from "react";
import { Badge } from "mangal";

/** The three tones, side by side — the whole visual API of the component. */
export function Tones() {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge tone="neutral">完結</Badge>
      <Badge tone="accent">連載中</Badge>
      <Badge tone="warm">新刊あり</Badge>
    </div>
  );
}

/** How the list view actually uses it: a status pill trailing a title row. */
export function InContext() {
  return (
    <div className="max-w-md space-y-2">
      <div className="flex items-center gap-2">
        <p className="flex-1 min-w-0 truncate text-sm font-bold">ハンター×ハンター</p>
        <Badge tone="warm">連載中</Badge>
      </div>
      <div className="flex items-center gap-2">
        <p className="flex-1 min-w-0 truncate text-sm font-bold">よろしくメカドック</p>
        <Badge tone="neutral">完結</Badge>
      </div>
      <div className="flex items-center gap-2">
        <p className="flex-1 min-w-0 truncate text-sm font-bold">ベルサイユのばら</p>
        <Badge tone="accent">全10巻</Badge>
      </div>
    </div>
  );
}

/** Volume counts and imprint labels — the other everyday payload. */
export function Metadata() {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge>全37巻</Badge>
      <Badge>ジャンプ・コミックス</Badge>
      <Badge tone="accent">アニメ化</Badge>
      <Badge tone="warm">1968年開始</Badge>
    </div>
  );
}
