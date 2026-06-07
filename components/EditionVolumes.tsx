"use client";

import { useState } from "react";
import type { Edition, Manga, Volume } from "@/lib/schema";
import VolumeTile from "./VolumeTile";
import Card from "./ui/Card";
import Badge from "./ui/Badge";

/**
 * 1 つの版 (edition) を描画。 ★複数の刷 (versions = 初版/新装版/復刻 等) がある場合は
 * 古い順タブで切替表示する。 既定で選ぶ刷 = 「全巻が購入可能 (ISBN/ASIN 有り) の最古の刷」。
 * (複数が全巻揃う場合も versions は古い順なので findIndex が最古を返す)
 * 刷が無い版は従来どおり edition.volumes をそのまま表示。
 */
function buyable(v: Volume): boolean {
  return !!(v.isbn13 || v.asin || v.kindle_asin);
}
function fullStock(vols: Volume[]): boolean {
  return vols.length > 0 && vols.every(buyable);
}

export default function EditionVolumes({ manga, edition }: { manga: Manga; edition: Edition }) {
  const versions = edition.versions;
  const hasTabs = !!versions && versions.length > 1;
  // 既定 = 全巻購入可の最古刷 (versions は古い順)。 無ければ先頭。
  const defaultIdx = hasTabs
    ? Math.max(0, versions!.findIndex((v) => fullStock(v.volumes)))
    : 0;
  const [sel, setSel] = useState(defaultIdx);
  const vols = hasTabs ? versions![sel].volumes : edition.volumes;

  return (
    <div>
      <h2 className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-base font-bold">{edition.label}</span>
        <Badge>全 {vols.length} 巻</Badge>
        {edition.publisher && (
          <span className="text-xs text-ink/55">出版社: {edition.publisher}</span>
        )}
      </h2>
      {hasTabs && (
        // ★3列均等グリッド = 下の巻タイル幅に揃う。 4つ目以降は左下に折り返す。
        <div className="mb-3 grid grid-cols-3 gap-2" role="tablist" aria-label="刷の切替">
          {versions!.map((v, i) => {
            const active = i === sel;
            const full = fullStock(v.volumes);
            return (
              <button
                key={v.label}
                role="tab"
                aria-selected={active}
                onClick={() => setSel(i)}
                // 角丸はジャンルタグ並み (radius-tag)。 選択中はアニメ化オレンジ (accent-warm) で明示。
                className={`w-full rounded-[var(--radius-tag)] border px-2 py-1.5 text-xs font-medium leading-tight transition active:scale-[0.97] ${
                  active
                    ? "bg-[var(--color-accent-warm)] text-white border-[var(--color-accent-warm)]"
                    : "bg-[var(--color-surface-2)] border-[var(--color-line)] text-ink/70"
                }`}
                title={full ? "全巻そろい" : "一部欠け"}
              >
                {v.label}
                {!full && <span className="ml-1 opacity-70">(一部)</span>}
              </button>
            );
          })}
        </div>
      )}
      <ul className="space-y-2">
        {vols.map((v) => (
          <li key={`${edition.type}-${v.number}`}>
            <Card className="p-3">
              <VolumeTile manga={manga} volume={v} edition={edition} />
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
