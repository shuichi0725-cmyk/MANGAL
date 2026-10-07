"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { KIND_COLOR, type Geom } from "./compass";

/** 準備中のアニメの種類(見本 loading-mock の1〜5)。 */
export const LOADING_KINDS = ["needle", "threads", "frames", "dots", "ripple"] as const;
export type LoadingKind = (typeof LOADING_KINDS)[number];

/** 糸の色(作者・同じ雑誌・同じ年・要素・ジャンル)を順に使う */
const THREAD_COLORS = [KIND_COLOR.author, KIND_COLOR.mag, KIND_COLOR.year, KIND_COLOR.elem, KIND_COLOR.genre];

/**
 * 「準備中…」の場面1(索引を読み込み中・真ん中の本もまだ無い)に流すアニメ。
 * 2026-10-08 ユーザ: 文字だけだと止まって見える → 見本5案(針がゆれる/糸がのびる/枠が順に点滅/点がはねる/網点の波)を
 * 「全部とても良い・ランダムで全部出せる?」= 開くたびに5つから1つを引く。
 * ★乱数は水和の後(useEffect)で引く。 サーバ描画は従来どおり文字だけ(描画のたびに違う絵を出すと水和が食い違う)。
 * ★場面2(真ん中の本が出た後)は従来どおり糸の位置の点線の枠の点滅(.cp-ph)。 「枠が順に点滅」はその枠と同じ位置に出す
 *   = 本が届くとそのまま枠が埋まって見える。
 * ★「動きを減らす」設定の人には止めた絵(.cp-root[data-reduce] と prefers-reduced-motion の両方で止める)。
 */
export default function CompassLoading({
  geom,
  angles,
  nw,
  nh,
  cw,
  ch,
  fixed,
}: {
  geom: Geom;
  /** 周りの本(場面2の点線の枠)の角度 */
  angles: number[];
  /** 周りの本・真ん中の本の大きさ(場面2の枠と同じ置き方にする) */
  nw: number;
  nh: number;
  cw: number;
  ch: number;
  /** 種類を固定する(見本・確認用)。 省略 = ランダム */
  fixed?: LoadingKind;
}) {
  const [kind, setKind] = useState<LoadingKind | null>(null);
  useEffect(() => {
    setKind(fixed ?? LOADING_KINDS[Math.floor(Math.random() * LOADING_KINDS.length)]);
  }, [fixed]);
  const { CX, CY } = geom;
  const pts = angles.map((a) => {
    const t = (a * Math.PI) / 180;
    return { x: CX + geom.rx * Math.cos(t), y: CY + geom.ry * Math.sin(t) };
  });
  const text = (top: number, pill = false) => (
    <p className={pill ? "cp-wait-text cp-ld-pill" : "cp-wait-text"} style={{ top }}>
      <span>準備中…</span>
    </p>
  );

  if (kind === "needle")
    return (
      <div className="cp-wait">
        <svg className="cp-ld-needle" viewBox="0 0 24 24" width={64} height={64} style={{ left: CX - 32, top: CY - 32 }} aria-hidden="true">
          <circle cx={12} cy={12} r={8.5} />
          <g className="cp-ld-nd">
            <path d="M15.5 8.5l-2 5-5 2 2-5z" />
          </g>
        </svg>
        {text(CY + 44)}
      </div>
    );
  if (kind === "threads")
    return (
      <div className="cp-wait">
        <svg className="cp-ld-thr" width={geom.W} height={geom.H} aria-hidden="true">
          {pts.map((p, i) => (
            <line
              key={i}
              x1={CX}
              y1={CY}
              x2={p.x}
              y2={p.y}
              stroke={THREAD_COLORS[i % THREAD_COLORS.length]}
              style={{ animationDelay: `${(i * 0.18).toFixed(2)}s` }}
            />
          ))}
          <circle className="cp-ld-hub" cx={CX} cy={CY} r={5} />
        </svg>
        {text(CY + 16, true)}
      </div>
    );
  if (kind === "frames")
    return (
      <div className="cp-wait">
        {pts.map((p, i) => (
          <span
            key={i}
            className="cp-ph cp-ld-seq"
            style={{ left: p.x - nw / 2, top: p.y - nh / 2, animationDelay: `${(i * 0.17).toFixed(2)}s` }}
          />
        ))}
        <span className="cp-ph cp-ld-seq cp-ld-big" style={{ left: CX - cw / 2, top: CY - ch / 2 }} />
        {text(CY + ch / 2 + 14)}
      </div>
    );
  if (kind === "dots")
    return (
      <div className="cp-wait">
        <p className="cp-ld-dots" style={{ top: CY - 4 }} aria-hidden="true">
          <i />
          <i />
          <i />
        </p>
        {text(CY + 20)}
      </div>
    );
  if (kind === "ripple")
    return (
      <div className="cp-wait">
        <div className="cp-ld-ripple" style={{ "--cp-ld-cx": `${CX}px`, "--cp-ld-cy": `${CY}px` } as CSSProperties} aria-hidden="true" />
        {text(CY - 8)}
      </div>
    );
  // サーバ描画・水和の直前 = 文字だけ(従来と同じ)
  return text(CY - 8);
}
