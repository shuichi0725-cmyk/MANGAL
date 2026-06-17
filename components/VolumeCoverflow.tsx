"use client";

import { useEffect, useRef, useState } from "react";
import CoverImage from "./CoverImage";
import type { Volume } from "@/lib/schema";

/**
 * 巻リスト(案D・試作 2026-06-17): 小サムネを横フリースクロール + 無限ループ + タップで選択。
 * - 左端=1巻起点 / 右へ巻数増 / 右端(最終巻)の先は1巻へループ(三重描画でシームレス)。
 * - ★スナップ/速度で歩数を変える物理は入れない = 引っかからない素のスクロール(ユーザ要望)。
 * - ぼかし無し(全書影表示)。 選択巻の下に大きい書影 + 情報(発売日/ISBN/出版社)。
 * - 下に3ストア(楽天/Yahoo!/Amazon)+ 全巻まとめ買い(据え置き)。
 * ※ストアリンクは試作=ISBN/題のストア内検索。 本実装でアフィリエイトタグ + PR表記を付与。
 */
function fmtDate(d?: string | null): string {
  return d ? String(d).replaceAll("-", ".") : "";
}
function fmtIsbn(v?: string | number | null): string {
  const s = v == null ? "" : String(v);
  if (s.length === 13) return `${s.slice(0, 3)}-${s.slice(3, 4)}-${s.slice(4, 6)}-${s.slice(6, 12)}-${s.slice(12)}`;
  return s;
}
function searchLinks(title: string, v: Volume) {
  const isbn = v.isbn13 ? String(v.isbn13) : "";
  const q = encodeURIComponent(isbn || `${title} ${v.number}`);
  return {
    rakuten: `https://books.rakuten.co.jp/search?sitem=${encodeURIComponent(isbn || `${title} ${v.number}`)}`,
    yahoo: `https://shopping.yahoo.co.jp/search?p=${q}`,
    amazon: `https://www.amazon.co.jp/s?k=${q}`,
  };
}

const THUMB = 44; // サムネ幅(案D=極小)
const LOOP_MIN = 9; // これ超で無限ループ(それ以下は全部並ぶのでループ不要)

export default function VolumeCoverflow({
  title,
  volumes,
  publisher,
  imprint,
}: {
  title: string;
  volumes: Volume[];
  publisher?: string | null;
  imprint?: string | null;
}) {
  const vols = [...volumes]
    .filter((v) => v.number != null)
    .sort((a, b) => (a.number as number) - (b.number as number));
  const n = vols.length;
  const init = Math.max(0, vols.findIndex((v) => v.number === 1));
  const [sel, setSel] = useState(init);
  const scroller = useRef<HTMLDivElement>(null);

  const loop = n > LOOP_MIN;
  const reps = loop ? [0, 1, 2] : [0];

  // 無限ループ(★指定挙動): 初期=1巻が左端で「左には進めない壁」。
  //   右へ送って最終巻の先(1巻)へ一度ループしたら、 以降は左方向もシームレス(1巻の左=最終巻)。
  useEffect(() => {
    if (!loop) return;
    const el = scroller.current;
    if (!el) return;
    const set = () => el.scrollWidth / 3;
    el.scrollLeft = set(); // 中央コピー先頭=1巻が左端
    let ticking = false;
    let looped = false; // 初回ループ済みか(以降は左ロック解除)
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        const s = set();
        if (el.scrollLeft > s * 1.5) {
          el.scrollLeft -= s; // 右端→1巻へシームレス・ループ
          looped = true; // 一度ループ=左方向を解放
        } else if (!looped && el.scrollLeft < s) {
          el.scrollLeft = s; // ★初回ループ前は1巻より左へ進ませない(壁)
        } else if (looped && el.scrollLeft < s * 0.5) {
          el.scrollLeft += s; // ループ後は左もシームレス(1巻の左=最終巻)
        }
        ticking = false;
      });
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [loop, n]);

  if (n === 0) return null;
  const cur = vols[sel];
  const links = searchLinks(title, cur);
  const bulk = `https://www.amazon.co.jp/s?k=${encodeURIComponent(`${title} 全巻 コミック セット`)}`;
  const pub = [publisher, imprint].filter(Boolean).join(" / ");

  return (
    <div>
      {/* 横フリースクロール(スナップ無し) */}
      <div
        ref={scroller}
        className="flex gap-1.5 overflow-x-auto py-2"
        style={{ scrollbarWidth: "none", WebkitOverflowScrolling: "touch" }}
      >
        {reps.map((rep) =>
          vols.map((v, idx) => {
            const active = idx === sel;
            return (
              <button
                key={`${rep}-${idx}`}
                onClick={() => setSel(idx)}
                aria-label={`第${v.number}巻`}
                className="relative shrink-0 overflow-hidden rounded bg-[var(--color-surface-2)]"
                style={{
                  width: THUMB,
                  aspectRatio: "2 / 3",
                  outline: active ? "2px solid var(--color-accent)" : "none",
                  outlineOffset: -1,
                }}
              >
                {v.cover_url ? (
                  <CoverImage src={v.cover_url} alt={`第${v.number}巻`} sizes="44px" />
                ) : (
                  <span className="flex h-full w-full items-center justify-center text-[8px] text-ink/40">
                    {v.number}
                  </span>
                )}
                <span className="absolute inset-x-0 bottom-0 bg-black/55 text-center text-[9px] font-bold text-white">
                  {v.number}
                </span>
              </button>
            );
          }),
        )}
      </div>

      {/* 選択巻の詳細パネル = 大書影 + 情報 */}
      <div className="mt-2 flex gap-3 rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3">
        <div
          className="relative shrink-0 overflow-hidden rounded-lg border border-[var(--color-line)]"
          style={{ width: 116, aspectRatio: "2 / 3" }}
        >
          {cur.cover_url ? (
            <CoverImage src={cur.cover_url} alt={cur.volume_label ?? `第${cur.number}巻`} sizes="116px" />
          ) : (
            <span className="flex h-full w-full items-center justify-center text-xs text-ink/40">
              第{cur.number}巻
            </span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-lg font-bold">{cur.volume_label ?? `第${cur.number}巻`}</div>
          {fmtDate(cur.release_date) && (
            <div className="text-xs text-ink/55">{fmtDate(cur.release_date)} 発売</div>
          )}
          <dl className="mt-2.5 space-y-1.5 text-[12px]">
            {cur.isbn13 && (
              <div>
                <dt className="text-[10px] text-ink/45">ISBN</dt>
                <dd className="font-semibold tabular-nums">{fmtIsbn(cur.isbn13)}</dd>
              </div>
            )}
            {pub && (
              <div>
                <dt className="text-[10px] text-ink/45">出版社</dt>
                <dd className="font-semibold">{pub}</dd>
              </div>
            )}
          </dl>
        </div>
      </div>

      {/* カート(据え置き) */}
      <div className="mt-3 grid grid-cols-3 gap-2">
        <a href={links.rakuten} target="_blank" rel="noopener noreferrer"
           className="spring-press rounded-full bg-[#bf0000] py-2 text-center text-sm font-bold text-white">楽天</a>
        <a href={links.yahoo} target="_blank" rel="noopener noreferrer"
           className="spring-press rounded-full bg-[#ff0033] py-2 text-center text-sm font-bold text-white">Yahoo!</a>
        <a href={links.amazon} target="_blank" rel="noopener noreferrer"
           className="spring-press rounded-full bg-[#e69500] py-2 text-center text-sm font-bold text-white">Amazon</a>
      </div>
      <a href={bulk} target="_blank" rel="noopener noreferrer"
         className="spring-press mt-2 flex items-center justify-between rounded-2xl px-5 py-3 text-white shadow-soft"
         style={{ background: "linear-gradient(90deg,#145a3c,#2ebe82)" }}>
        <span>
          <span className="block text-[15px] font-bold">全巻まとめ買い</span>
          <span className="block text-[11px] text-white/80">全{n}巻セットをまとめて</span>
        </span>
        <span className="text-2xl leading-none">›</span>
      </a>
    </div>
  );
}
