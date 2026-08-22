import React from "react";
import { Card, Badge } from "mangal";

/** The pressable form: `href` makes it an anchor, so it lifts on hover. */
export function AsLink() {
  return (
    <div className="max-w-sm">
      <Card href="/manga/hunter-x-hunter" className="block p-4">
        <p className="font-bold">ハンター×ハンター</p>
        <p className="mt-1 text-xs text-ink/60">冨樫義博　1998〜 連載中</p>
      </Card>
    </div>
  );
}

/** No `href` — a plain container with the same tactile surface. */
export function AsContainer() {
  return (
    <div className="max-w-sm">
      <Card className="p-4">
        <p className="text-sm font-bold">絞り込み</p>
        <p className="mt-1 text-xs text-ink/60">条件を選ぶと一覧が更新されます。</p>
      </Card>
    </div>
  );
}

/** Cards stacked as a list — the shape /browse and /list actually render. */
export function AsList() {
  const rows = [
    { slug: "berserk", title: "ベルセルク", meta: "三浦建太郎　1989〜 連載中", tone: "warm" as const, label: "連載中" },
    { slug: "yoroshiku-mechadoc", title: "よろしくメカドック", meta: "次原隆二　1982〜1985 完結", tone: "neutral" as const, label: "完結" },
    { slug: "versailles-no-bara", title: "ベルサイユのばら", meta: "池田理代子　1972〜1973 完結", tone: "neutral" as const, label: "完結" },
  ];
  return (
    <div className="max-w-sm space-y-2">
      {rows.map((r) => (
        <Card key={r.slug} href={`/manga/${r.slug}`} className="flex items-center gap-2 p-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold">{r.title}</p>
            <p className="mt-0.5 truncate text-xs text-ink/60">{r.meta}</p>
          </div>
          <Badge tone={r.tone}>{r.label}</Badge>
        </Card>
      ))}
    </div>
  );
}
