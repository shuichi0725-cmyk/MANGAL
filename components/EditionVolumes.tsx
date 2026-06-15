"use client";

import { useState } from "react";
import type { Edition, Manga, Volume } from "@/lib/schema";
import VolumeCoverflow from "./VolumeCoverflow";
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

// ★伸縮アニメ: grid-rows 0fr⇄1fr。 ※renderの外で定義必須(内側に書くと毎renderで別
//   コンポーネント扱い=remountされ、遷移が一切走らないバグになる。2026-06-13実害)
function Grow({ open, children }: { open: boolean; children: React.ReactNode }) {
  return (
    <div
      className="grid"
      style={{
        gridTemplateRows: open ? "1fr" : "0fr",
        opacity: open ? 1 : 0,
        transition:
          "grid-template-rows 550ms cubic-bezier(0.22, 1, 0.36, 1), opacity 450ms ease",
      }}
    >
      <div className="min-h-0 overflow-hidden">{children}</div>
    </div>
  );
}

export default function EditionVolumes({
  manga,
  edition,
  defaultCollapsed = false,
}: {
  manga: Manga;
  edition: Edition;
  defaultCollapsed?: boolean;
}) {
  const versions = edition.versions;
  const hasTabs = !!versions && versions.length > 1;
  // 既定 = 全巻購入可の最古刷 (versions は古い順)。 無ければ先頭。
  const defaultIdx = hasTabs
    ? Math.max(0, versions!.findIndex((v) => fullStock(v.volumes)))
    : 0;
  const [sel, setSel] = useState(defaultIdx);
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const vols = hasTabs ? versions![sel].volumes : edition.volumes;

  return (
    <div>
      {/* 見出し: 畳める版(2版目以降)は見出し自体がトグル */}
      {defaultCollapsed ? (
        <button
          onClick={() => setCollapsed((c) => !c)}
          className={`spring-press flex w-full items-center gap-2 text-left ${
            collapsed ? "tactile rounded-card px-3.5 py-3" : "mb-3 px-0"
          }`}
        >
          <span className={`inline-block text-ink/40 transition-transform duration-[550ms] ${collapsed ? "" : "rotate-90"}`}>▸</span>
          <span className={`font-bold ${collapsed ? "text-[15px]" : "text-base"}`}>{edition.label}</span>
          <Badge>全 {vols.length} 巻</Badge>
          {edition.publisher && (
            <span className="text-xs text-ink/55">出版社: {edition.publisher}</span>
          )}
          <span className="ml-auto text-[11px] text-ink/45">{collapsed ? "ひらく" : "たたむ ▴"}</span>
        </button>
      ) : (
        <h2 className="mb-3 flex flex-wrap items-center gap-2">
          <span className="text-base font-bold">{edition.label}</span>
          <Badge>全 {vols.length} 巻</Badge>
          {edition.publisher && (
            <span className="text-xs text-ink/55">出版社: {edition.publisher}</span>
          )}
        </h2>
      )}

      <Grow open={!collapsed}>
      <div>
      {hasTabs && (
        // ★採用デザイン: 3列・間隔0.125rem(gap-0.5)・高さ2.1rem。
        //   極太名を中央 + 年を右下隅。 選択中はアニメ化オレンジ塗り。 4つ目以降は左下に折返し。
        <div className="mb-3 grid grid-cols-3 gap-0.5" role="tablist" aria-label="刷の切替">
          {versions!.map((v, i) => {
            const active = i === sel;
            const full = fullStock(v.volumes);
            return (
              <button
                key={v.label}
                role="tab"
                aria-selected={active}
                onClick={() => setSel(i)}
                className={`relative flex items-center justify-center overflow-hidden rounded-[var(--radius-tag)] border px-2 transition active:scale-[0.98] ${
                  active ? "shadow-soft" : "border-[var(--color-line)] bg-[var(--color-surface-2)] text-ink/70"
                }`}
                style={
                  active
                    ? {
                        minHeight: "2.1rem",
                        paddingTop: "0.15rem",
                        paddingBottom: "0.15rem",
                        background: "var(--color-accent-warm)",
                        borderColor: "var(--color-accent-warm)",
                        color: "#fff",
                      }
                    : { minHeight: "2.1rem", paddingTop: "0.15rem", paddingBottom: "0.15rem" }
                }
                title={full ? "全巻そろい" : "一部欠け"}
              >
                <span className="text-[18px] font-black leading-none">{v.label}</span>
                <span
                  className={`absolute bottom-0.5 right-1.5 text-[7px] tabular-nums ${active ? "text-white/70" : "opacity-40"}`}
                >
                  {v.year_started ?? ""}
                </span>
                {!full && (
                  <span
                    className="absolute left-1 top-0.5 text-[7px]"
                    style={{ color: active ? "rgba(255,255,255,0.85)" : "var(--color-accent)" }}
                  >
                    一部
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
      {/* ★巻リスト = コーフロー(案A: 中央フォーカス・両側暗・ループ・初期1巻) */}
      <VolumeCoverflow title={manga.title} volumes={vols} />
      </div>
      </Grow>
    </div>
  );
}
