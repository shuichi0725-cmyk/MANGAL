"use client";

// ★方位盤(2026-10-31 ユーザ裁定 = 案A2「回すつまみ」): 広げた糸の「回」(24冊ずつ)を、真ん中の本を囲む輪を回して選ぶ。
//   輪は指についてくる(左へ回すと先の回)。 回している間は後ろに透けている本がその回の本に入れ替わる(onPreview)。
//   指を離すとその回が「今の回」(onCommit)。 外側の細い輪 = 全体のどこにいるか(白=見た所)・押す/なぞると一気に飛ぶ。
//   16回までは目盛りを全部並べ、それより多いと12個の窓を回す。 31回以上は速く回すと10回ずつ。
//   真ん中か輪の外を押すと閉じる。 見本 = 2026-10-31 の「回すつまみ試作」(scratchpad)。
import { useCallback, useEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from "react";
import { dialSlots, wrapRound } from "./compass";

type Pt = { x: number; y: number };
type Props = {
  /** 回の数 */
  total: number;
  /** 今の回(0始まり・確定した回) */
  k: number;
  /** 見た回(0始まり) */
  seen: readonly number[];
  /** 回ごとの冊目 [始まり, 終わり)(0始まり) */
  ranges: readonly [number, number][];
  color: string;
  /** 輪の中心(舞台の座標 = 広げた時の真ん中の本) */
  cx: number;
  cy: number;
  /** PC の横長の倍率(スマホ = 1) */
  scale: number;
  /** 回している間(後ろの本をその回に入れ替える)。 origin = 舞台の座標で指の位置(波紋の中心) */
  onPreview: (k: number, origin: Pt) => void;
  /** 指を離した = その回を今の回にする */
  onCommit: (k: number, origin: Pt) => void;
  onClose: () => void;
};

const FAST = 650; // 度/秒 = これより速く回すと10回ずつ

export default function RoundDial({ total, k, seen, ranges, color, cx, cy, scale, onPreview, onCommit, onClose }: Props) {
  const R1 = 78 * scale;
  const R2 = 112 * scale;
  const RO = 126 * scale;
  const N = dialSlots(total);
  const step = 360 / N;
  const big = total > 30;
  const [pos, setPosState] = useState(k);
  // ★指の動きは描画より速く来る = 今の位置は ref で持つ(state は描くため)
  const posRef = useRef(k);
  const setPos = (v: number) => {
    posRef.current = v;
    setPosState(v);
  };
  const [x10, setX10] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ mode: "jog" | "scrub"; lastA: number; lastT: number; moved: number; start: number; origin: Pt } | null>(null);
  const closeTap = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shown = useRef(k);
  const to = wrapRound(Math.round(pos), total);
  const seenSet = new Set(seen);

  // 確定した回が外から変わった(次を見る等)= 輪もそこへ
  useEffect(() => {
    if (!drag.current) {
      posRef.current = k;
      setPosState(k);
    }
    shown.current = k;
  }, [k]);
  useEffect(() => {
    rootRef.current?.focus({ preventScroll: true });
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  // 回している間の入れ替え = 少し止まった所だけ(速く回している間は書影を読み込まない)
  const want = useCallback(
    (r: number, origin: Pt, fast: boolean) => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(
        () => {
          if (shown.current === r) return;
          shown.current = r;
          onPreview(r, origin);
        },
        fast ? 260 : 70,
      );
    },
    [onPreview],
  );

  const local = (e: { clientX: number; clientY: number }): Pt => {
    const rc = rootRef.current?.getBoundingClientRect();
    return { x: e.clientX - (rc?.left ?? 0) - cx, y: e.clientY - (rc?.top ?? 0) - cy };
  };
  /** 真上 = 0・時計回り(度) */
  const angTop = (p: Pt) => ((Math.atan2(p.y, p.x) * 180) / Math.PI + 450) % 360;

  const onDown = (e: PointerEvent<HTMLDivElement>) => {
    const p = local(e);
    const r = Math.hypot(p.x, p.y);
    closeTap.current = r < R1 - 8 || r > RO + 24;
    if (closeTap.current) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    const origin = { x: cx + p.x, y: cy + p.y };
    if (r > R2 + 6) {
      drag.current = { mode: "scrub", lastA: 0, lastT: 0, moved: 99, start: posRef.current, origin };
      scrubTo(p);
    } else {
      drag.current = { mode: "jog", lastA: angTop(p), lastT: performance.now(), moved: 0, start: posRef.current, origin: { x: cx, y: cy - R2 } };
    }
  };
  const scrubTo = (p: Pt) => {
    const r = Math.min(total - 1, Math.floor((angTop(p) / 360) * total));
    setPos(r);
    if (drag.current) drag.current.origin = { x: cx + p.x, y: cy + p.y };
    want(r, { x: cx + p.x, y: cy + p.y }, false);
  };
  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d) return;
    const p = local(e);
    if (d.mode === "scrub") return scrubTo(p);
    const a = angTop(p);
    let da = a - d.lastA;
    if (da > 180) da -= 360;
    if (da < -180) da += 360;
    const now = performance.now();
    const fast = big && (Math.abs(da) / Math.max(1, now - d.lastT)) * 1000 > FAST;
    setX10(fast);
    d.lastA = a;
    d.lastT = now;
    d.moved += Math.abs(da);
    // 輪は指についてくる = 時計回りに回すと前の回が真上へ
    const nx = posRef.current - (da / step) * (fast ? 10 : 1);
    setPos(nx);
    want(wrapRound(Math.round(nx), total), d.origin, fast);
  };
  const onUp = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    drag.current = null;
    setX10(false);
    if (!d) return;
    let nx = posRef.current;
    if (d.mode === "jog" && d.moved < 4) {
      // 目盛りを押した = その回へ
      let a = angTop(local(e));
      if (a > 180) a -= 360;
      nx = Math.round(d.start) + Math.round(a / step);
    }
    const r = wrapRound(Math.round(nx), total);
    if (timer.current) clearTimeout(timer.current);
    setPos(r);
    shown.current = r;
    onCommit(r, d.origin);
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const r = wrapRound(k + (e.key === "ArrowRight" ? 1 : -1), total);
      setPos(r);
      shown.current = r;
      onCommit(r, { x: cx, y: cy - R2 });
    } else if (e.key === "Enter") {
      e.preventDefault();
      onClose();
    }
  };

  // ── 描く ──
  const P = (r: number, a: number) => [cx + r * Math.cos(((a - 90) * Math.PI) / 180), cy + r * Math.sin(((a - 90) * Math.PI) / 180)];
  const f1 = (v: number) => v.toFixed(1);
  const arc = (a0: number, a1: number, r1: number, r2: number) => {
    const [x1, y1] = P(r2, a0);
    const [x2, y2] = P(r2, a1);
    const [x3, y3] = P(r1, a1);
    const [x4, y4] = P(r1, a0);
    return `M${f1(x1)},${f1(y1)} A${r2},${r2} 0 0 1 ${f1(x2)},${f1(y2)} L${f1(x3)},${f1(y3)} A${r1},${r1} 0 0 0 ${f1(x4)},${f1(y4)}Z`;
  };
  // 外側の細い輪(全体): 見た所の弧
  const A = (r: number) => (r / total) * 360;
  const outArc = (r0: number, r1: number) => {
    const a0 = A(r0);
    const a1 = A(r1) - 0.01;
    const [x1, y1] = P(RO, a0);
    const [x2, y2] = P(RO, a1);
    return `M${f1(x1)},${f1(y1)} A${RO},${RO} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${f1(x2)},${f1(y2)}`;
  };
  const seenRuns: [number, number][] = [];
  {
    let s0: number | null = null;
    for (let r = 0; r <= total; r++) {
      const on = r < total && seenSet.has(r);
      if (on && s0 === null) s0 = r;
      if (!on && s0 !== null) {
        seenRuns.push([s0, r]);
        s0 = null;
      }
    }
  }
  // 内側の目盛り: 真上 = 指の回・時計回りに先の回
  const base = Math.round(pos);
  const half = N / 2;
  const slots: { r: number; d: number }[] = [];
  for (let off = -Math.ceil(half) - 1; off <= Math.ceil(half) + 1; off++) {
    const r = wrapRound(base + off, total);
    let d = r - pos;
    d = ((((d + total / 2) % total) + total) % total) - total / 2;
    if (N < total && Math.abs(d) > half + 0.001) continue;
    if (N === total && slots.some((s) => s.r === r)) continue;
    slots.push({ r, d });
  }
  const [ta, tb] = ranges[to] ?? [0, 0];
  const mono = "ui-monospace,SFMono-Regular,Consolas,monospace";
  const toA = A(to) + 180 / total;
  const [mx, my] = P(RO + 9 * scale, toA);
  const [m1x, m1y] = P(RO + 16 * scale, toA - 3);
  const [m2x, m2y] = P(RO + 16 * scale, toA + 3);

  return (
    <div
      ref={rootRef}
      className="cp-dial"
      role="slider"
      tabIndex={0}
      aria-label="回を選ぶ(左右の矢印で1回ずつ)"
      aria-valuemin={1}
      aria-valuemax={total}
      aria-valuenow={to + 1}
      aria-valuetext={`${to + 1}回目(${ta + 1}〜${tb}冊目)`}
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={onUp}
      onPointerCancel={onUp}
      onKeyDown={onKey}
      onClick={(e) => {
        e.stopPropagation(); // 舞台の「何もない所を押す = 閉じる」に渡さない
        if (closeTap.current) {
          closeTap.current = false;
          onClose();
        }
      }}
      style={{ "--dc": color } as CSSProperties}
    >
      <svg className="cp-dial-svg" aria-hidden="true">
        <circle cx={cx} cy={cy} r={RO} fill="none" stroke="#ffffff26" strokeWidth={6 * scale} />
        {seenRuns.map(([a, b]) => (
          <path key={`s${a}`} d={outArc(a, b)} fill="none" stroke="#ffffffaa" strokeWidth={6 * scale} />
        ))}
        <path d={outArc(k, k + 1)} fill="none" stroke={color} strokeWidth={8 * scale} />
        {big &&
          [0, 0.25, 0.5, 0.75].map((f) => {
            const [x1, y1] = P(RO - 7 * scale, f * 360);
            const [x2, y2] = P(RO + 7 * scale, f * 360);
            const [tx, ty] = P(RO + 15 * scale, f * 360);
            return (
              <g key={f}>
                <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#ffffff55" />
                {f > 0 && (
                  <text x={tx} y={ty + 3} textAnchor="middle" fontSize={8 * scale} fill="#9aa6b0" fontFamily={mono}>
                    {Math.round(f * total) + 1}
                  </text>
                )}
              </g>
            );
          })}
        <path d={`M${f1(mx)},${f1(my)} L${f1(m1x)},${f1(m1y)} L${f1(m2x)},${f1(m2y)}Z`} fill="#fff" />
        {slots.map(({ r, d }) => {
          const am = d * step;
          const isTo = r === to;
          const isCur = r === k;
          const isSeen = seenSet.has(r);
          const fade = N < total ? Math.max(0, Math.min(1, (half + 0.2 - Math.abs(d)) / 1.4)) : 1;
          const [tx, ty] = P((R1 + R2) / 2, am);
          const fill = isTo ? "#e6ecf0" : isCur ? color : isSeen ? "#ffffff38" : "#0b0e14a8";
          const label = String(r + 1);
          return (
            <g key={r} opacity={fade.toFixed(2)}>
              <path d={arc(am - step / 2 + 1.2, am + step / 2 - 1.2, R1, R2)} fill={fill} stroke={isCur ? color : isTo ? "#fff" : `${color}66`} strokeWidth={1} />
              <text
                x={f1(tx)}
                y={f1(ty + 4 * scale)}
                textAnchor="middle"
                fontSize={(label.length >= 3 ? 10 : 11.5) * scale}
                fontWeight={800}
                fill={isTo || isCur ? "#0b0e14" : isSeen ? "#e6ecf0" : color}
                fontFamily={mono}
              >
                {label}
              </text>
              {isSeen && !isTo && !isCur && (
                <text x={f1(P(R2 - 7 * scale, am)[0])} y={f1(P(R2 - 7 * scale, am)[1] + 3)} textAnchor="middle" fontSize={7.5 * scale} fill={color}>
                  ✓
                </text>
              )}
            </g>
          );
        })}
        <path d={`M${cx - 6 * scale},${cy - RO - 12 * scale} L${cx + 6 * scale},${cy - RO - 12 * scale} L${cx},${cy - R2 + 1}Z`} fill="#e6ecf0" />
      </svg>
      <div className="cp-dial-in" style={{ left: cx, top: cy }}>
        <b>{to + 1}回目</b>
        <i>
          {(ta + 1).toLocaleString()}〜{tb.toLocaleString()}冊目
        </i>
        {seenSet.has(to) && <span>✓ 見た</span>}
      </div>
      <div className="cp-dial-lab" style={{ left: cx, top: cy - RO - 40 * scale }}>
        なぞって回す
        {big && <span className={x10 ? "on" : undefined}>速く回すと×10</span>}
      </div>
    </div>
  );
}
