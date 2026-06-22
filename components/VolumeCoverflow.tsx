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

  // 無限ループ + ★継ぎ目 detent(指定挙動): 最終巻↔1巻の継ぎ目を ★進行方向に応じて一度止める。
  //   ・左スワイプ(前進=scrollLeft増): 最終巻を超え 1巻が ★右端 に出た瞬間に停止 → 再スワイプでループ継続
  //   ・右スワイプ(後退=scrollLeft減): 1巻の手前 最終巻が ★左端 に出た瞬間に停止 → 再スワイプでループ継続
  //   3コピー描画で継ぎ目をシームレスに(detent解放後は逆コピーへ recenter = 巻き戻し無く連続)。
  useEffect(() => {
    if (!loop) return;
    const el = scroller.current;
    if (!el) return;
    const set = () => el.scrollWidth / 3; // 1コピー幅
    el.scrollLeft = set(); // 中央コピー先頭=1巻が左端
    let ticking = false;
    let lastL = el.scrollLeft;
    const startPos = el.scrollLeft; // 起動位置(1巻が左端)
    let looped = false; // 一度前進して1巻が右端に出るまでは後退(左)させない
    let cooling = false; // detent直後の再発火防止(この間は触らない)
    let settle: ReturnType<typeof setTimeout> | undefined;
    // 継ぎ目横断をモジュラ検知(周回・両方向で正しく効く)。
    //   fwdIdx: 1巻が右端に来る境界 index(x+W-t が s の倍数) → 前進で増えたら横断。
    //   backIdx: 最終巻が左端に来る境界 index(x+t が s の倍数) → 後退で減ったら横断。
    //   ★横断した瞬間に overflow を一瞬切って ★慣性(弾み)を確実に殺す → ピタッと停止。
    //   220ms後に overflow を戻して操作を受け付ける(= 止まった後は自由に動く)。
    const snapStop = (target: number) => {
      el.style.overflowX = "hidden"; // ★慣性スクロールを即停止(ピタッ)
      el.scrollLeft = target;
      cooling = true;
      clearTimeout(settle);
      settle = setTimeout(() => {
        el.style.overflowX = ""; // 操作再開(class の overflow-x-auto に戻る)
        cooling = false;
        lastL = el.scrollLeft;
      }, 220);
    };
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        if (cooling) { ticking = false; return; } // 停止中は何もしない
        const s = set();
        const t = s / n; // 1アイテム幅(gap込み近似)
        const W = el.clientWidth;
        const L = el.scrollLeft;
        const fwdIdx = (x: number) => Math.floor((x + W - t) / s);
        const backIdx = (x: number) => Math.floor((x + t) / s);
        if (!looped) {
          // ★最初は左(後退)に行かせない: 一度前進して1巻が右端に出るまで開始位置が左壁。
          if (L < startPos - 1) { el.scrollLeft = startPos; lastL = startPos; ticking = false; return; }
          const dir = L - lastL;
          if (dir > 0 && fwdIdx(L) > fwdIdx(lastL)) {
            looped = true; // 一周した → 以降は後退も解禁
            snapStop(fwdIdx(L) * s + t - W); // 1巻が右端に出た → ピタッと停止
          } else {
            lastL = L;
          }
          ticking = false;
          return;
        }
        // 一周後: 左右ともループ + 継ぎ目で停止。
        // 3コピーの端に達したら中央へ巻き戻し(content周期=sなので継ぎ目位置は不変)。
        if (L > 2.5 * s) { el.scrollLeft = L - s; lastL = el.scrollLeft; ticking = false; return; }
        if (L < 0.5 * s) { el.scrollLeft = L + s; lastL = el.scrollLeft; ticking = false; return; }
        const dir = L - lastL;
        if (dir > 0 && fwdIdx(L) > fwdIdx(lastL)) {
          snapStop(fwdIdx(L) * s + t - W); // 前進: 1巻が右端に出た → ピタッと停止
        } else if (dir < 0 && backIdx(L) < backIdx(lastL)) {
          snapStop(backIdx(lastL) * s - t); // 後退: 最終巻が左端に出た → ピタッと停止
        }
        lastL = el.scrollLeft;
        ticking = false;
      });
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      el.removeEventListener("scroll", onScroll);
      clearTimeout(settle);
    };
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

      {/* この巻の特装版/限定版(案B: 通常版を主に、 特装版は捨てず併存) */}
      {cur.variants && cur.variants.length > 0 && (
        <div className="mt-2 rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3">
          <div className="text-[11px] font-bold text-ink/55">この巻の特装版・限定版</div>
          <div className="mt-2 space-y-3">
            {cur.variants.map((vr, i) => {
              const q = vr.isbn13 ? String(vr.isbn13) : `${title} ${cur.number}`;
              const e = encodeURIComponent(q);
              const vl = {
                rakuten: `https://books.rakuten.co.jp/search?sitem=${e}`,
                yahoo: `https://shopping.yahoo.co.jp/search?p=${e}`,
                amazon: `https://www.amazon.co.jp/s?k=${e}`,
              };
              return (
                <div key={i} className="rounded-xl border border-[var(--color-line)] p-2.5">
                  <div className="flex items-center gap-3">
                    <div
                      className="relative shrink-0 overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
                      style={{ width: 46, aspectRatio: "2 / 3" }}
                    >
                      {vr.cover_url ? (
                        <CoverImage src={vr.cover_url} alt={vr.label} sizes="46px" />
                      ) : (
                        <span className="flex h-full w-full items-center justify-center text-[8px] text-ink/40">特装版</span>
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-[12px] font-semibold leading-snug">{vr.label}</div>
                      {vr.price != null && (
                        <div className="text-[11px] text-ink/55">¥{vr.price.toLocaleString()}</div>
                      )}
                    </div>
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    <a href={vl.rakuten} target="_blank" rel="noopener noreferrer"
                       className="spring-press rounded-full bg-[#bf0000] py-1.5 text-center text-[12px] font-bold text-white">楽天</a>
                    <a href={vl.yahoo} target="_blank" rel="noopener noreferrer"
                       className="spring-press rounded-full bg-[#ff0033] py-1.5 text-center text-[12px] font-bold text-white">Yahoo!</a>
                    <a href={vl.amazon} target="_blank" rel="noopener noreferrer"
                       className="spring-press rounded-full bg-[#e69500] py-1.5 text-center text-[12px] font-bold text-white">Amazon</a>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

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
