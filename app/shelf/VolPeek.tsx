"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { bigCover, loadVolCovers, type VolCover } from "@/lib/volCovers";

/**
 * 本棚: 番号タイルを押すと段の下に開く「前後の書影を覗かせる」パネル(2026-10-04 ユーザ裁定 3D)と、
 * 真ん中の書影を押すと頁のように大きく開く全画面(同 P2 = 黒地に大きく・送る時にめくるように回転)。
 * 書影 = lib/volCovers(作品ごとの巻の書影・開いた作品の1本だけ読む)。
 * ★全画面は body 直下へポータルで出す(祖先の z-index/transform に閉じ込められない = [[lightbox_no_portal_stacking_trap]])。
 */

const fmt = (d: string | null) => (d ? `${d.replace(/-/g, "/")} 発売` : "");

export default function VolPeek({
  slug,
  title,
  n,
  owned,
  onN,
  onClose,
}: {
  slug: string;
  title: string;
  n: number;
  owned: number;
  onN: (n: number) => void;
  onClose: () => void;
}) {
  const [vols, setVols] = useState<VolCover[] | null | undefined>(undefined);
  const [full, setFull] = useState(false);
  useEffect(() => {
    let live = true;
    loadVolCovers(slug).then((v) => live && setVols(v));
    return () => {
      live = false;
    };
  }, [slug]);
  if (vols === undefined) return <div className="shelf-vp shelf-vp-msg">書影を読み込み中…</div>;
  if (!vols || !vols.length)
    return (
      <div className="shelf-vp shelf-vp-msg">
        この作品の巻の書影はまだありません
        <button type="button" className="shelf-vp-x" onClick={onClose} aria-label="閉じる">
          ✕
        </button>
      </div>
    );
  const i = Math.max(0, vols.findIndex((v) => v.n === n));
  const cur = vols[i];
  const prev = vols[i - 1];
  const next = vols[i + 1];
  const go = (v: VolCover | undefined) => v && onN(v.n);
  return (
    <div className="shelf-vp" role="group" aria-label={`${title} 第${cur.n}巻`}>
      <div className="shelf-vp-stage">
        <button type="button" className="shelf-vp-peek" disabled={!prev} onClick={() => go(prev)} aria-label="前の巻">
          {prev?.cover && <img src={prev.cover} alt="" loading="lazy" decoding="async" className="bg-white" />}
        </button>
        <button type="button" className="shelf-vp-main" onClick={() => setFull(true)} aria-label={`第${cur.n}巻を大きく見る`}>
          {cur.cover ? (
            // eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク
            <img src={cur.cover} alt={`${title} 第${cur.n}巻 表紙`} decoding="async" className="bg-white" />
          ) : (
            <span className="shelf-vp-noimg">第{cur.n}巻</span>
          )}
        </button>
        <button type="button" className="shelf-vp-peek" disabled={!next} onClick={() => go(next)} aria-label="次の巻">
          {next?.cover && <img src={next.cover} alt="" loading="lazy" decoding="async" className="bg-white" />}
        </button>
      </div>
      <div className="shelf-vp-info">
        <b>第{cur.n}巻</b>
        <span>{fmt(cur.date)}</span>
        {cur.n > owned && <span className="is-alert">まだ持っていない巻</span>}
        <span className="shelf-vp-tap">書影を押すと大きく</span>
      </div>
      <button type="button" className="shelf-vp-x" onClick={onClose} aria-label="閉じる">
        ✕
      </button>
      {full && <VolPage title={title} vols={vols} i={i} onI={(j) => onN(vols[j].n)} onClose={() => setFull(false)} />}
    </div>
  );
}

/** 頁のように大きく(P2): 黒地に書影だけ大きく。 左右に払う/左右の端を押す = 前後の巻(めくるように回転)。 */
function VolPage({
  title,
  vols,
  i,
  onI,
  onClose,
}: {
  title: string;
  vols: VolCover[];
  i: number;
  onI: (i: number) => void;
  onClose: () => void;
}) {
  const [turn, setTurn] = useState<"" | "turn-next" | "turn-prev">("");
  const x0 = useRef<number | null>(null);
  const swiped = useRef(false); // 払った直後のクリックで閉じない
  const step = useCallback(
    (d: number) => {
      const j = i + d;
      if (j < 0 || j >= vols.length) return;
      setTurn(d > 0 ? "turn-next" : "turn-prev");
      onI(j);
    },
    [i, vols.length, onI],
  );
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") step(1);
      if (e.key === "ArrowLeft") step(-1);
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden"; // 後ろの頁を動かさない
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose, step]);
  // 端を押す = 前後の巻(★払った直後のクリックは捨てる = 払いと端押しで2巻送らない)
  const edge = (e: React.MouseEvent, d: number) => {
    e.stopPropagation();
    if (swiped.current) {
      swiped.current = false;
      return;
    }
    step(d);
  };
  const v = vols[i];
  return createPortal(
    <div
      className="shelf-vpage"
      role="dialog"
      aria-modal="true"
      aria-label={`${title} 第${v.n}巻 大きく表示`}
      onPointerDown={(e) => {
        x0.current = e.clientX;
      }}
      onPointerUp={(e) => {
        if (x0.current === null) return;
        const dx = e.clientX - x0.current;
        x0.current = null;
        swiped.current = Math.abs(dx) > 40;
        if (swiped.current) step(dx < 0 ? 1 : -1);
      }}
      onClick={(e) => {
        // 書影の外(暗い所)を押したら閉じる
        if (e.target === e.currentTarget && !swiped.current) onClose();
        swiped.current = false;
      }}
    >
      <button type="button" className="shelf-vpage-x" onClick={onClose} aria-label="閉じる">
        ✕
      </button>
      <button type="button" className="shelf-vpage-edge is-l" onClick={(e) => edge(e, -1)} aria-label="前の巻" disabled={i === 0} />
      <button type="button" className="shelf-vpage-edge is-r" onClick={(e) => edge(e, 1)} aria-label="次の巻" disabled={i === vols.length - 1} />
      <div key={v.n} className={`shelf-vpage-pg ${turn}`} onAnimationEnd={() => setTurn("")}>
        {v.cover ? (
          // eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク(楽天は大きい画像)
          <img src={bigCover(v.cover) ?? undefined} alt={`${title} 第${v.n}巻 表紙`} draggable={false} className="bg-white" />
        ) : (
          <span className="shelf-vp-noimg">第{v.n}巻</span>
        )}
      </div>
      <p className="shelf-vpage-cap">第{v.n}巻</p>
      <p className="shelf-vpage-sub">{fmt(v.date)}</p>
      <p className="shelf-vpage-hint">
        {i + 1} / {vols.length}・左右に払う/端を押す = 前後の巻・✕で閉じる
      </p>
    </div>,
    document.body,
  );
}
