"use client";

import { useRef, useState } from "react";
import CoverImage from "./CoverImage";
import type { Volume } from "@/lib/schema";

/**
 * 巻リストのコーフロー表示(案A=均等サイズ・中央フォーカス・両側を暗く・ループ)。
 * 初期フォーカス=1巻。 タップ=選択 / 横スワイプ=巻送り(…30 31 [1] 2 3… ループ)。
 * 下にフォーカス巻の情報 + 3ストア(楽天/Yahoo!/Amazon)+ 全巻まとめ買い。
 * ※ストアリンクは試作=ISBN/題のストア内検索。 本実装でアフィリエイトタグ + PR表記を付与。
 */
function fmtDate(d?: string | null): string {
  return d ? String(d).replaceAll("-", ".") : "";
}

function searchLinks(title: string, v: Volume) {
  const isbn = v.isbn13 || "";
  const q = encodeURIComponent(isbn || `${title} ${v.number}`);
  return {
    rakuten: `https://books.rakuten.co.jp/search?sitem=${encodeURIComponent(isbn || `${title} ${v.number}`)}`,
    yahoo: `https://shopping.yahoo.co.jp/search?p=${q}`,
    amazon: `https://www.amazon.co.jp/s?k=${q}`,
  };
}

export default function VolumeCoverflow({ title, volumes }: { title: string; volumes: Volume[] }) {
  const vols = [...volumes]
    .filter((v) => v.number != null)
    .sort((a, b) => (a.number as number) - (b.number as number));
  const n = vols.length;
  const init = Math.max(0, vols.findIndex((v) => v.number === 1));
  const [focus, setFocus] = useState(init < 0 ? 0 : init);
  const touch = useRef<number | null>(null);
  // スワイプ中の指追従(translateX)+ 離した時のスライドアニメ用。
  const [dragX, setDragX] = useState(0);
  const [anim, setAnim] = useState(false); // true=transition有効(離した直後のスライド/スナップ)
  const STEP = 104; // 1スロット送り幅 = タイル96 + gap8

  if (n === 0) return null;

  // 表示スロット(±2)。 5巻以下はループせず全部並べる。
  let slots: { off: number; idx: number }[];
  if (n <= 5) {
    slots = vols.map((_, idx) => ({ idx, off: idx - focus }));
  } else {
    slots = [];
    for (let off = -2; off <= 2; off++) slots.push({ off, idx: ((focus + off) % n + n) % n });
  }
  const cur = vols[focus];
  const links = searchLinks(title, cur);
  const move = (d: number) => setFocus((f) => ((f + d) % n + n) % n);
  const bulk = `https://www.amazon.co.jp/s?k=${encodeURIComponent(`${title} 全巻 コミック セット`)}`;

  const endSwipe = (endX: number) => {
    if (touch.current == null) return;
    const dx = endX - touch.current;
    touch.current = null;
    if (Math.abs(dx) > 40) {
      // 送る方向に1スロット分スライドさせてから focus を確定(窓が1つずれて見た目連続)。
      const dir = dx < 0 ? 1 : -1; // 左スワイプ=次へ
      setAnim(true);
      setDragX(-dir * STEP);
      window.setTimeout(() => {
        setAnim(false);
        setDragX(0);
        move(dir);
      }, 220);
    } else {
      // しきい値未満 = 元位置へスナップバック。
      setAnim(true);
      setDragX(0);
      window.setTimeout(() => setAnim(false), 180);
    }
  };

  return (
    <div>
      {/* 外側=クリップ + タッチ受け / 内側=指追従で translateX するトラック */}
      <div
        className="relative select-none overflow-hidden py-3"
        onTouchStart={(e) => { touch.current = e.touches[0].clientX; setAnim(false); setDragX(0); }}
        onTouchMove={(e) => {
          if (touch.current == null) return;
          const raw = e.touches[0].clientX - touch.current;
          const lim = STEP + 40; // ±2スロットしか描画しないので窓外(空白)まで引っ張らせない
          setDragX(Math.max(-lim, Math.min(lim, raw)));
        }}
        onTouchEnd={(e) => endSwipe(e.changedTouches[0].clientX)}
      >
      <div
        className="flex items-center justify-center gap-2"
        style={{
          transform: `translateX(${dragX}px)`,
          transition: anim ? "transform 220ms ease-out" : "none",
        }}
      >
        {slots.map(({ off, idx }) => {
          const v = vols[idx];
          const dist = Math.abs(off);
          const center = dist === 0;
          const bright = center ? 1 : dist === 1 ? 0.72 : 0.5;
          return (
            <button
              key={`${off}-${idx}`}
              onClick={() => !center && setFocus(idx)}
              aria-label={`第${v.number}巻`}
              className="relative shrink-0 overflow-hidden rounded-md bg-[var(--color-surface-2)]"
              style={{
                width: 96,
                aspectRatio: "2 / 3",
                filter: `brightness(${bright})`,
                outline: center ? "3px solid var(--color-accent)" : "none",
                outlineOffset: center ? "-1px" : 0,
                zIndex: center ? 2 : 1,
                transition: "filter 220ms ease",
              }}
            >
              {v.cover_url ? (
                <CoverImage src={v.cover_url} alt={`第${v.number}巻`} sizes="96px" />
              ) : (
                <span className="flex h-full w-full items-center justify-center p-1 text-center text-[10px] text-ink/40">
                  第{v.number}巻
                </span>
              )}
              <span className="absolute inset-x-0 bottom-0 bg-black/55 text-center text-[10px] font-bold text-white">
                {v.number}
              </span>
            </button>
          );
        })}
      </div>
      </div>

      {/* フォーカス巻の情報 + カート */}
      <div className="px-1">
        <div className="flex items-baseline gap-2">
          <span className="text-lg font-bold">第{cur.number}巻</span>
          {fmtDate(cur.release_date) && (
            <span className="text-xs text-ink/55">・ {fmtDate(cur.release_date)}</span>
          )}
          <span className="ml-auto text-[10px] text-ink/40">← スワイプ / タップで選択 →</span>
        </div>
        <div className="mt-2 grid grid-cols-3 gap-2">
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
    </div>
  );
}
