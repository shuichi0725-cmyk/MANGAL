"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { MangaListItem } from "@/lib/schema";
import {
  ensureFullIndex,
  isCatchLoaded,
  isFullIndexLoaded,
  onIndexFailed,
  setIndexBase,
  useMangaIndex,
} from "@/lib/useMangaIndex";
import {
  KINDS,
  KIND_COLOR,
  KIND_NAME,
  SPREADS,
  allowedSpreads,
  buildGraph,
  neighborhood,
  placeRing,
  resolveSpread,
  spreadPositions,
  stageGeom,
  type Kind,
  type Spread,
  type ThreadKind,
} from "./compass";
import { Halftone } from "./halftone";
import { CompassShelveButton, CompassShelvePanel } from "./CompassShelve";

// ★この頁だけ本番の全件索引を読む(preview CI が本番の公開索引から public/prod-idx/ を作る)。
//   頁のJSは水和より前に評価されるので、ここで基点を変えれば最初の読み込みから /prod-idx になる。
//   module キャッシュは全頁共有 → この頁から出る時は <a>(全頁読み込み)で出る(next/link を使わない)。
if (typeof window !== "undefined") setIndexBase("/prod-idx");

const TOP = 100; // 糸の色チップ列 44 + 旅路 56
const SHEET = 96;
const NW = 58;
const NH = 81;
const CW = 92;
const CH = 128;
const STORE = "mangal.magicShelf.spreads.v1";
const PLACEHOLDER_ANGLES = [-90, -20, 20, 70, 110, 160, 200];
const FIRST = "\u0000first";

type Step = { slug: string; kind: ThreadKind | null };
type Spawn = { fx: number; fy: number; fs: number; d: number };
type NodeView = {
  slug: string;
  x: number;
  y: number;
  w: number;
  h: number;
  center?: boolean;
  small?: boolean;
  label?: string;
  color?: string;
  hidden?: boolean;
  dim?: boolean;
  pick?: boolean;
  back?: boolean;
  gone?: boolean;
  spawn: Spawn | null;
};
type LineView = {
  key: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
  width: number;
  opacity: number;
  dash?: string;
  sel?: boolean;
  lineIn?: boolean;
};
type Pan = { target: string; from: string; x: number; y: number; w: number; h: number; kind: ThreadKind; small: boolean };

function sheetColor(k: ThreadKind | null): string {
  if (!k || k === "back") return "#5b6570";
  return k === "author" ? "#b8860b" : KIND_COLOR[k];
}

/** 広げ方の小さな絵(アイコン) */
function SpreadIcon({ k }: { k: Spread }) {
  const p = { fill: "none", stroke: "currentColor", strokeWidth: 1.4, strokeLinecap: "round" as const };
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      {k === "fan" && <path {...p} d="M7 12 L2 4 A6.5 6.5 0 0 1 12 4 Z" />}
      {k === "ring" && (
        <>
          <circle {...p} cx="7" cy="7" r="2" />
          <circle {...p} cx="7" cy="7" r="5.5" />
        </>
      )}
      {k === "time" && <path {...p} d="M1.5 12.5 H12.5 M3.5 10 V7 M7 10 V3 M10.5 10 V5.5" />}
      {k === "dust" && (
        <g fill="currentColor">
          <circle cx="3" cy="4" r="1.3" />
          <circle cx="9.5" cy="2.8" r="1" />
          <circle cx="6.5" cy="7.5" r="1.4" />
          <circle cx="11.5" cy="9" r="1.1" />
          <circle cx="3.5" cy="11" r="1" />
        </g>
      )}
    </svg>
  );
}

export default function MagicCompass({ magazines }: { magazines: Record<string, string> }) {
  // ── データ: useMangaIndex(先頭100件 → 列形式の全件)+ キャッチ ──
  const index = useMangaIndex({ withCatch: true });
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    ensureFullIndex(); // 糸は全件で張る = 手すきを待たずに今すぐ
    return onIndexFailed(() => setFailed(true));
  }, []);
  const fullIndex = index && isFullIndexLoaded() ? index : null;
  const catchReady = isCatchLoaded();
  // 逆引き表は索引(+キャッチ)が届いた時に1回だけ
  const graph = useMemo(() => (fullIndex && catchReady ? buildGraph(fullIndex) : null), [fullIndex, catchReady]);
  const magName = useCallback((k: string) => magazines[k] ?? k, [magazines]);

  // ── 画面の大きさ ──
  const rootRef = useRef<HTMLDivElement>(null);
  const [vp, setVp] = useState({ w: 360, h: 740 });
  useLayoutEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const measure = () => setVp({ w: el.clientWidth || 360, h: el.clientHeight || 740 });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const geom = useMemo(() => stageGeom(vp.w, Math.max(240, vp.h - TOP - SHEET)), [vp]);

  // 全画面の間は下の頁を動かさない
  useEffect(() => {
    const html = document.documentElement;
    const prev = html.style.overflow;
    html.style.overflow = "hidden";
    return () => {
      html.style.overflow = prev;
    };
  }, []);

  const [reduce, setReduce] = useState(false);
  const reduceRef = useRef(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const f = () => {
      reduceRef.current = mq.matches;
      setReduce(mq.matches);
    };
    f();
    mq.addEventListener("change", f);
    return () => mq.removeEventListener("change", f);
  }, []);

  // ── タイマー(頁を出たら全部止める) ──
  const timers = useRef(new Set<ReturnType<typeof setTimeout>>());
  const later = useCallback((fn: () => void, ms: number) => {
    const t = setTimeout(() => {
      timers.current.delete(t);
      fn();
    }, ms);
    timers.current.add(t);
    return t;
  }, []);
  useEffect(() => {
    const ts = timers.current;
    return () => ts.forEach((t) => clearTimeout(t));
  }, []);

  // ── 旅の状態 ──
  const [path, setPath] = useState<Step[]>([]);
  const cur = path.length ? path[path.length - 1].slug : null;
  const [prev, setPrev] = useState<string | null>(null);
  const [backAng, setBackAng] = useState<number | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [off, setOff] = useState<Set<Kind>>(() => new Set());
  const [exp, setExp] = useState<string | null>(null);
  const [lays, setLays] = useState<Partial<Record<Kind, string>>>({});
  const [cw, setCw] = useState({ x: 0, y: 0 }); // 中央の本の世界座標
  const [cam, setCam] = useState({ x: 0, y: 0 }); // 画面の中央に来る世界座標
  const [pan, setPan] = useState<Pan | null>(null);
  const [firstRing, setFirstRing] = useState(true); // 最初の周りの本は中央から飛び出す
  // この中央の糸は伸びて現れる(FIRST = 最初に周りの本が出る時。 開く・切るで null = 伸ばさず即時)
  const [growFor, setGrowFor] = useState<string | null>(FIRST);
  const busy = useRef(false);
  // シートの「しまう」: 棚を選ぶ欄を開いている本 / しまった後の一言(本が替わったら消す)
  const [shelveFor, setShelveFor] = useState<string | null>(null);
  const [shelveMsg, setShelveMsg] = useState<string | null>(null);
  useEffect(() => {
    setShelveFor(null);
    setShelveMsg(null);
  }, [cur, sel, exp]);

  // 覚えた広げ方は水和の後で読む
  useEffect(() => {
    try {
      const v = JSON.parse(window.localStorage.getItem(STORE) || "{}");
      if (v && typeof v === "object") setLays(v);
    } catch {
      /* 読めなければ既定 */
    }
  }, []);

  // ── 旅の始まり: ?from=<slug> か、先頭100件(人気上位)からランダムに1冊 ──
  useEffect(() => {
    if (path.length || !index || !index.length) return;
    const full = isFullIndexLoaded();
    const from = new URLSearchParams(window.location.search).get("from");
    if (from) {
      if (index.some((m) => m.slug === from)) {
        setPath([{ slug: from, kind: null }]);
        return;
      }
      if (!full) return; // 先頭100件に無い = 全件を待つ
    }
    const pool = (full ? [...index].sort((a, b) => (b.popularity ?? 0) - (a.popularity ?? 0)).slice(0, 100) : index).filter(
      (m) => m.cover,
    );
    if (!pool.length) return;
    setPath([{ slug: pool[Math.floor(Math.random() * pool.length)].slug, kind: null }]);
  }, [index, path.length]);

  const curItem = useMemo<MangaListItem | null>(() => {
    if (!cur) return null;
    return graph?.all.get(cur) ?? index?.find((m) => m.slug === cur) ?? null;
  }, [cur, graph, index]);
  const lookup = useCallback(
    (slug: string): MangaListItem | undefined => graph?.all.get(slug) ?? (curItem?.slug === slug ? curItem : undefined),
    [graph, curItem],
  );

  // 1冊の中央につき計算は1回(周り+広げる単位)
  const nb = useMemo(() => (graph && curItem ? neighborhood(graph, curItem, magName) : null), [graph, curItem, magName]);
  const placed = useMemo(() => (nb ? placeRing(nb.ring, prev, backAng, geom.rx, geom.ry) : []), [nb, prev, backAng, geom]);
  const unit = useMemo(() => (exp && nb ? (nb.units.find((u) => u.key === exp) ?? null) : null), [exp, nb]);
  const spreadOf = useCallback((k: Kind) => resolveSpread(k, lays[k]), [lays]);
  const spread = useMemo(
    () =>
      unit
        ? spreadPositions(unit.kind, unit.items, spreadOf(unit.kind), geom, curItem?.year_started ?? null, unit.key)
        : null,
    [unit, spreadOf, geom, curItem],
  );

  // ── 背景の網点 ──
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const toneRef = useRef<Halftone | null>(null);
  const toneSlug = useRef<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; n: number } | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const showToast = useCallback((msg: string) => {
    setToast((t) => ({ msg, n: (t?.n ?? 0) + 1 }));
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast((t) => (t ? { ...t, msg: "" } : t)), 1300);
  }, []);
  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const h = new Halftone(cv);
    h.onTone = (name) => showToast(`網点の出方: ${name}`);
    toneRef.current = h;
    return () => {
      h.destroy();
      toneRef.current = null;
      if (toastTimer.current) clearTimeout(toastTimer.current);
    };
  }, [showToast]);
  useEffect(() => {
    toneRef.current?.resize(vp.w, vp.h, geom.CX, TOP + geom.CY);
  }, [vp, geom]);
  useEffect(() => {
    if (toneRef.current) toneRef.current.reduce = reduce;
  }, [reduce]);
  useEffect(() => {
    if (!cur || !curItem || toneSlug.current === cur) return;
    toneSlug.current = cur;
    toneRef.current?.setCover(curItem.cover);
  }, [cur, curItem]);

  const [flash, setFlash] = useState<{ color: string; on: boolean }>({ color: "transparent", on: false });
  const [bump, setBump] = useState(0);
  const bumpSheet = useCallback(() => {
    if (reduceRef.current) return;
    setBump((b) => b + 1);
    later(() => setBump(0), 160);
  }, [later]);

  // ── 進む = 糸を手繰る ──
  const travel = useCallback(
    (
      target: string,
      rel: { x: number; y: number; w: number; h: number; small: boolean },
      kind: ThreadKind,
      commit: (p: Step[]) => Step[],
    ) => {
      if (busy.current || !cur) return;
      busy.current = true;
      const from = cur;
      const tw = { x: cw.x + rel.x, y: cw.y + rel.y };
      // 前の中央は来た方向の反対側(楕円の上の角度で持つ = すべり終えた位置にそのまま残る)
      const ang = (Math.atan2(rel.y / geom.ry, rel.x / geom.rx) * 180) / Math.PI + 180;
      const item = lookup(target);
      toneSlug.current = target;
      toneRef.current?.setCover(item?.cover ?? null, { x: -rel.x * 0.6, y: -rel.y * 0.6 });
      const finish = () => {
        setPath(commit);
        setPrev(from);
        setBackAng(ang);
        setSel(null);
        setExp(null);
        setPan(null);
        setCw(tw);
        setCam(tw);
        setFirstRing(false);
        setGrowFor(target);
      };
      if (reduceRef.current) {
        finish();
        busy.current = false;
        return;
      }
      setFlash({ color: KIND_COLOR[kind], on: true });
      later(() => setFlash((f) => ({ ...f, on: false })), 300);
      setExp(null);
      setPan({ target, from, x: tw.x, y: tw.y, w: rel.w, h: rel.h, kind, small: rel.small });
      setCam(tw);
      later(() => {
        finish();
        later(() => {
          busy.current = false;
        }, 700);
      }, 760);
    },
    [cur, cw, geom, lookup, later],
  );

  const jumpBack = useCallback(
    (i: number) => {
      if (busy.current || i >= path.length - 1) return;
      const slug = path[i].slug;
      const o = placed.find((x) => x.slug === slug);
      const rel = o ? { x: o.dx, y: o.dy, w: NW, h: NH, small: false } : { x: -geom.rx, y: 0, w: NW, h: NH, small: false };
      travel(slug, rel, "back", (p) => p.slice(0, i + 1));
    },
    [path, placed, geom, travel],
  );

  const go = useCallback(
    (slug: string) => {
      if (unit && spread) {
        const p = spread.P.find((x) => x.slug === slug);
        if (!p) return;
        travel(
          slug,
          { x: p.x - geom.CX, y: p.y - geom.CY, w: p.w, h: p.h, small: true },
          unit.kind,
          (ps) => [...ps, { slug, kind: unit.kind }],
        );
        return;
      }
      const o = placed.find((x) => x.slug === slug);
      if (!o) return;
      if (o.back && path.length > 1 && path[path.length - 2].slug === slug) {
        jumpBack(path.length - 2);
        return;
      }
      const kind: ThreadKind = o.back ? "back" : o.kind;
      travel(slug, { x: o.dx, y: o.dy, w: NW, h: NH, small: false }, kind, (ps) => [...ps, { slug, kind }]);
    },
    [unit, spread, placed, path, geom, travel, jumpBack],
  );

  const tapNode = useCallback(
    (slug: string) => {
      if (busy.current) return;
      if (slug === cur) {
        setSel(null);
        return;
      }
      if (sel === slug) {
        go(slug);
        return;
      }
      setSel(slug);
      bumpSheet();
    },
    [cur, sel, go, bumpSheet],
  );

  const toggleKind = useCallback(
    (k: Kind) => {
      if (exp) return;
      setOff((s) => {
        const n = new Set(s);
        if (n.has(k)) n.delete(k);
        else n.add(k);
        return n;
      });
      const o = sel ? placed.find((x) => x.slug === sel) : null;
      if (o && !o.back && o.kind === k) setSel(null);
      setGrowFor(null);
    },
    [exp, sel, placed],
  );

  const openUnit = useCallback(
    (key: string | null) => {
      if (busy.current) return;
      setSel(null);
      setGrowFor(null);
      setExp((e) => (!key || key === e ? null : key));
      bumpSheet();
    },
    [bumpSheet],
  );

  const chooseSpread = useCallback((k: Kind, s: Spread) => {
    setSel(null);
    setLays((l) => {
      const n = { ...l, [k]: s };
      try {
        window.localStorage.setItem(STORE, JSON.stringify(n));
      } catch {
        /* 覚えられなくても動く */
      }
      return n;
    });
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || busy.current) return;
      if (sel) setSel(null);
      else if (exp) setExp(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sel, exp]);

  // ── 描く本(世界座標) ──
  const nodes = useMemo<NodeView[]>(() => {
    if (!cur || !curItem) return [];
    const toW = (sx: number, sy: number) => ({ x: cw.x + sx - geom.CX, y: cw.y + sy - geom.CY });
    if (pan) {
      return [
        { slug: pan.from, x: cw.x, y: cw.y, w: CW, h: CH, center: true, spawn: null },
        {
          slug: pan.target,
          x: pan.x,
          y: pan.y,
          w: pan.w,
          h: pan.h,
          small: pan.small,
          pick: true,
          color: KIND_COLOR[pan.kind],
          spawn: { fx: 0, fy: 0, fs: 1, d: 0 },
        },
      ];
    }
    const out: NodeView[] = [];
    const cBox = spread ? toW(spread.center.x, spread.center.y) : { x: cw.x, y: cw.y };
    out.push({
      slug: cur,
      ...cBox,
      w: spread ? spread.center.w : CW,
      h: spread ? spread.center.h : CH,
      center: true,
      spawn: { fx: 0, fy: 0, fs: 0.6, d: 0 },
    });
    const xs = spread ? new Map(spread.P.map((p) => [p.slug, p])) : null;
    placed.forEach((o, i) => {
      if (xs?.has(o.slug) || o.slug === cur) return; // 広げた本と同じ本は広げた側で描く
      const color = KIND_COLOR[o.back ? "back" : o.kind];
      out.push({
        slug: o.slug,
        x: cw.x + o.dx,
        y: cw.y + o.dy,
        w: NW,
        h: NH,
        label: o.back ? "← 来た道" : o.label,
        color,
        back: o.back,
        hidden: !!xs || (!o.back && off.has(o.kind as Kind)),
        pick: !xs && sel === o.slug,
        dim: !xs && !!sel && sel !== o.slug,
        spawn: firstRing
          ? { fx: -o.dx, fy: -o.dy, fs: 0.33, d: 120 + i * 55 }
          : { fx: 0, fy: 0, fs: 1, d: 120 + i * 55 },
      });
    });
    if (spread && unit) {
      spread.P.forEach((p, i) => {
        if (p.slug === cur) return;
        out.push({
          slug: p.slug,
          ...toW(p.x, p.y),
          w: p.w,
          h: p.h,
          small: true,
          color: KIND_COLOR[unit.kind],
          pick: sel === p.slug,
          dim: !!sel && sel !== p.slug,
          spawn: {
            fx: spread.center.x - p.x,
            fy: spread.center.y - p.y,
            fs: Math.min(1, 10 / p.w),
            d: 40 + i * 18,
          },
        });
      });
    }
    return out;
  }, [cur, curItem, cw, geom, pan, spread, unit, placed, off, sel, firstRing]);

  const lines = useMemo<LineView[]>(() => {
    if (!cur || !curItem) return [];
    const toW = (sx: number, sy: number) => ({ x: cw.x + sx - geom.CX, y: cw.y + sy - geom.CY });
    if (pan)
      return [
        {
          key: `l:${pan.target}`,
          x1: cw.x,
          y1: cw.y,
          x2: pan.x,
          y2: pan.y,
          color: KIND_COLOR[pan.kind],
          width: 3.4,
          opacity: 0.9,
          sel: true,
        },
      ];
    if (spread && unit) {
      const L: LineView[] = [];
      if (spread.axisY !== undefined) {
        const a = toW(12, spread.axisY);
        const b = toW(geom.W - 12, spread.axisY);
        L.push({ key: "axis", x1: a.x, y1: a.y, x2: b.x, y2: b.y, color: KIND_COLOR[unit.kind], width: 1, opacity: 0.6 });
        const c1 = toW(spread.center.x, spread.center.y + spread.center.h / 2 + 4);
        L.push({ key: "cdot", x1: c1.x, y1: c1.y, x2: c1.x, y2: a.y, color: "#ffffff88", width: 1, opacity: 1, dash: "3 4" });
      } else if (sel) {
        const p = spread.P.find((x) => x.slug === sel);
        if (p) {
          const t = toW(p.x, p.y);
          L.push({ key: `x:${sel}`, x1: cw.x, y1: cw.y, x2: t.x, y2: t.y, color: KIND_COLOR[unit.kind], width: 2.6, opacity: 0.9, sel: true });
        }
      }
      return L;
    }
    return placed
      .filter((o) => o.slug !== cur)
      .map((o) => {
        const hidden = !o.back && off.has(o.kind as Kind);
        const isSel = sel === o.slug;
        return {
          key: `l:${o.slug}`,
          x1: cw.x,
          y1: cw.y,
          x2: cw.x + o.dx,
          y2: cw.y + o.dy,
          color: KIND_COLOR[o.back ? "back" : o.kind],
          width: isSel ? 3.4 : sel ? 1.2 : o.back ? 1.4 : 2.2,
          opacity: hidden ? 0 : o.back ? 0.7 : 0.9,
          dash: o.back && !isSel ? "3 5" : undefined,
          sel: isSel,
          lineIn: !o.back && (growFor === cur || growFor === FIRST),
        };
      });
  }, [cur, curItem, cw, geom, pan, spread, unit, placed, off, sel, growFor]);

  // ── 出ていく本は0.5秒だけ残して薄れさせる(同じ要素のまま) ──
  const seen = useRef(new Map<string, { seq: number; spawn: Spawn | null; lineIn: number | null }>());
  const seqN = useRef(0);
  const prevRendered = useRef(new Map<string, NodeView>());
  const ghostUntil = useRef(new Map<string, number>());
  const [, setGhostTick] = useState(0);
  const live = new Map(nodes.map((n) => [n.slug, n]));
  const ghosts: NodeView[] = [];
  if (prevRendered.current.size) {
    const now = Date.now();
    for (const [slug, n] of prevRendered.current) {
      if (live.has(slug)) continue;
      let until = ghostUntil.current.get(slug);
      if (until === undefined) {
        until = now + 520;
        ghostUntil.current.set(slug, until);
      }
      if (until > now) ghosts.push({ ...n, gone: true, pick: false });
    }
  }
  const lineDelay = firstRing ? 260 : 200;
  const reg = (key: string, spawn: Spawn | null, lineIn: number | null) => {
    let s = seen.current.get(key);
    if (!s) {
      s = { seq: seqN.current++, spawn: reduce ? null : spawn, lineIn: reduce ? null : lineIn };
      seen.current.set(key, s);
    }
    return s;
  };
  const drawnNodes = [...nodes, ...ghosts]
    .map((n) => ({ n, s: reg(`n:${n.slug}`, n.spawn, null) }))
    .sort((a, b) => a.s.seq - b.s.seq);
  const drawnLines = lines
    .map((l) => ({ l, s: reg(`l:${l.key}`, null, l.lineIn ? lineDelay : null) }))
    .sort((a, b) => a.s.seq - b.s.seq);
  useLayoutEffect(() => {
    prevRendered.current = new Map(drawnNodes.map(({ n }) => [n.slug, n]));
    for (const slug of live.keys()) ghostUntil.current.delete(slug);
    const keep = new Set([...drawnNodes.map(({ n }) => `n:${n.slug}`), ...drawnLines.map(({ l }) => `l:${l.key}`)]);
    for (const k of seen.current.keys()) if (!keep.has(k)) seen.current.delete(k);
    const now = Date.now();
    for (const [slug, t] of ghostUntil.current) if (t <= now && !live.has(slug)) ghostUntil.current.delete(slug);
    if (!ghosts.length) return;
    const t = setTimeout(() => setGhostTick((x) => x + 1), 540);
    return () => clearTimeout(t);
  });

  // ── 旅路は最新を右端へ ──
  const histRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = histRef.current;
    if (h) h.scrollLeft = h.scrollWidth;
  }, [path.length]);

  // ── シート ──
  let sheetItem: MangaListItem | null = curItem;
  let sheetKind: ThreadKind | null = null;
  let why = "";
  let goLabel: string | null = null;
  if (!curItem) {
    why = failed ? "本番の索引が読めませんでした" : "星図を描いています…";
  } else if (!nb) {
    why = failed ? "本番の索引が読めませんでした" : "いまの中心 ・ 星図を描いています…";
  } else if (unit) {
    sheetKind = unit.kind;
    if (sel) {
      const it = unit.items.find((i) => i.slug === sel);
      sheetItem = lookup(sel) ?? curItem;
      why = `${KIND_NAME[unit.kind]} — ${unit.label}${it?.shared ? ` ・ 共通の要素${it.shared}つ` : ""}`;
      goLabel = `〈${unit.label}〉の糸で進む →`;
    } else {
      why = `「${unit.label}」の糸を広げています(${unit.items.length}冊) ・ 本に触れて選ぶ`;
    }
  } else {
    const o = sel ? placed.find((x) => x.slug === sel) : null;
    if (o) {
      sheetItem = lookup(o.slug) ?? curItem;
      sheetKind = o.back ? "back" : o.kind;
      why = o.back ? "来た道" : `${KIND_NAME[o.kind]} — ${o.label}`;
      goLabel = o.back ? "来た道を戻る ←" : `〈${KIND_NAME[o.kind]}〉の糸で進む →`;
    } else {
      why = "いまの中心 ・ 周りの本に触れるか、下の「広げる」から糸を選ぶ";
    }
  }
  const catchText = sheetItem?.catch || (catchReady ? "(紹介文はまだありません)" : "");

  const worldStyle: CSSProperties = {
    left: geom.CX,
    top: geom.CY,
    transform: `translate(${-cam.x}px, ${-cam.y}px)`,
  };

  return (
    <div ref={rootRef} className="cp-root" data-reduce={reduce ? "1" : undefined}>
      <div className="cp-bg" aria-hidden="true">
        <canvas ref={canvasRef} />
        <div className="cp-vig" />
        <div
          className={`cp-flash${flash.on ? " on" : ""}`}
          style={{ background: `radial-gradient(circle at 50% ${TOP + geom.CY}px, ${flash.color}33, transparent 70%)` }}
        />
      </div>
      <div className={`cp-toast${toast?.msg ? " on" : ""}`} role="status">
        {toast?.msg}
      </div>

      {/* 1. 糸の色チップ列 */}
      <div className="cp-top">
        <a href="/" className="cp-exit" aria-label="MANGAL のトップへ戻る">
          ←
        </a>
        {KINDS.map((k) => (
          <button
            key={k}
            type="button"
            className={`cp-chip${off.has(k) ? "" : " on"}`}
            style={{ "--c": KIND_COLOR[k] } as CSSProperties}
            aria-pressed={!off.has(k)}
            disabled={!!exp}
            onClick={() => toggleKind(k)}
          >
            {KIND_NAME[k]}
          </button>
        ))}
        <button type="button" className="cp-save" onClick={() => showToast("旅の保存は準備中です")}>
          旅を保存
        </button>
      </div>

      {/* 2. 旅路 */}
      <div className="cp-hist" ref={histRef}>
        {path.map((p, i) => {
          const m = lookup(p.slug);
          return (
            <span key={`${i}:${p.slug}`} className="cp-hstep">
              {i > 0 && <span className="cp-hs" style={{ background: KIND_COLOR[p.kind ?? "back"] }} />}
              <button
                type="button"
                className={i === path.length - 1 ? "now" : undefined}
                aria-label={`${m?.title ?? p.slug}${i === path.length - 1 ? "(いまの中心)" : "へ戻る"}`}
                onClick={() => jumpBack(i)}
              >
                {m?.cover ? (
                  // eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク(images.unoptimized)
                  <img src={m.cover} alt="" className="bg-white" draggable={false} />
                ) : (
                  <span className="cp-noimg" />
                )}
              </button>
            </span>
          );
        })}
        {path.length > 0 && <span className="cp-hs cp-hs-q" />}
        <span className="cp-q">?</span>
      </div>

      {/* 3. 羅針盤 */}
      <div className="cp-stage">
        {curItem && !nb && (
          <div className={`cp-wait${failed ? " failed" : ""}`}>
            {!failed &&
              PLACEHOLDER_ANGLES.map((a) => {
                const t = (a * Math.PI) / 180;
                return (
                  <span
                    key={a}
                    className="cp-ph"
                    style={{ left: geom.CX + geom.rx * Math.cos(t) - NW / 2, top: geom.CY + geom.ry * Math.sin(t) - NH / 2 }}
                  />
                );
              })}
            <p className="cp-wait-text" style={{ top: geom.CY + CH / 2 + 14 }}>
              {failed ? "本番の索引が読めませんでした" : "星図を描いています…"}
            </p>
          </div>
        )}
        {!curItem && (
          <p className="cp-wait-text" style={{ top: geom.CY - 8 }}>
            {failed ? "本番の索引が読めませんでした" : "星図を描いています…"}
          </p>
        )}
        <div className="cp-world" style={worldStyle}>
          <svg className="cp-lines" width="1" height="1" aria-hidden="true">
            {drawnLines.map(({ l, s }) => {
              const len = Math.hypot(l.x2 - l.x1, l.y2 - l.y1);
              return (
                <g
                  key={l.key}
                  className={s.lineIn !== null ? "cp-linein" : undefined}
                  style={
                    s.lineIn !== null ? ({ "--len": `${len.toFixed(1)}px`, "--d": `${s.lineIn}ms` } as CSSProperties) : undefined
                  }
                >
                  <line
                    className={`cp-ln${l.sel ? " sel" : ""}`}
                    x1={l.x1}
                    y1={l.y1}
                    x2={l.x2}
                    y2={l.y2}
                    style={{
                      stroke: l.color,
                      strokeWidth: l.width,
                      opacity: l.opacity,
                      strokeDasharray: l.dash,
                    }}
                  />
                </g>
              );
            })}
            {spread?.ticks &&
              spread.axisY !== undefined &&
              spread.ticks.map((t) => {
                const x = cw.x + t.x - geom.CX;
                const y = cw.y + (spread.axisY as number) - geom.CY;
                return (
                  <g key={`t:${t.year}`} className="cp-tick">
                    <line x1={x} y1={y} x2={x} y2={y + 5} />
                    <text x={x} y={y + 16}>
                      {t.year}
                    </text>
                  </g>
                );
              })}
          </svg>
          {drawnNodes.map(({ n, s }) => {
            const m = lookup(n.slug);
            const cls = [
              "cp-nd",
              n.center && "center",
              n.small && "small",
              n.back && "back",
              n.pick && "pick",
              n.dim && "dim",
              (n.hidden || n.gone) && "off",
              s.spawn && "enter",
            ]
              .filter(Boolean)
              .join(" ");
            const style = {
              left: n.x - n.w / 2,
              top: n.y - n.h / 2,
              width: n.w,
              height: n.h,
              "--kc": n.color ?? "#ffffff",
              ...(s.spawn
                ? { "--fx": `${s.spawn.fx}px`, "--fy": `${s.spawn.fy}px`, "--fs": s.spawn.fs, "--d": `${s.spawn.d}ms` }
                : null),
            } as CSSProperties;
            return (
              <button
                key={n.slug}
                type="button"
                className={cls}
                style={style}
                tabIndex={n.hidden || n.gone ? -1 : 0}
                aria-hidden={n.hidden || n.gone ? true : undefined}
                aria-label={`${m?.title ?? n.slug}${n.center ? "(いまの中心)" : n.label ? ` — ${n.label}` : ""}`}
                onClick={() => tapNode(n.slug)}
              >
                {m?.cover ? (
                  // eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク(images.unoptimized)
                  <img src={m.cover} alt="" className="bg-white" draggable={false} decoding="async" />
                ) : (
                  <span className="cp-noimg" />
                )}
                {n.label && !n.small && (
                  <span className="cp-lb" style={{ color: n.color }}>
                    {n.label}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        {unit && (
          <div className="cp-spreads" role="group" aria-label="広げ方">
            {SPREADS.map((sp) => {
              const ok = allowedSpreads(unit.kind).includes(sp.key);
              const on = spreadOf(unit.kind) === sp.key;
              return (
                <button
                  key={sp.key}
                  type="button"
                  className={`cp-sp${on ? " on" : ""}`}
                  style={{ "--c": KIND_COLOR[unit.kind] } as CSSProperties}
                  aria-pressed={on}
                  disabled={!ok}
                  title={ok ? undefined : "同じ年の糸では年表を使えません(全部が1列に重なるため)"}
                  onClick={() => chooseSpread(unit.kind, sp.key)}
                >
                  <SpreadIcon k={sp.key} />
                  {sp.name}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. 広げる ▸ */}
      <div className="cp-units">
        {nb && !exp && <span className="cp-ul">広げる ▸</span>}
        {exp && (
          <button type="button" className="cp-uc cp-uc-x" onClick={() => openUnit(null)}>
            ✕ 閉じる
          </button>
        )}
        {nb?.units.map((u) => (
          <button
            key={u.key}
            type="button"
            className={`cp-uc${exp === u.key ? " on" : ""}`}
            style={{ "--c": KIND_COLOR[u.kind] } as CSSProperties}
            aria-pressed={exp === u.key}
            onClick={() => openUnit(u.key)}
          >
            {u.label}
            <i>{u.items.length}</i>
          </button>
        ))}
        {nb && !nb.units.length && <span className="cp-ul">この本から広げられる糸はありません</span>}
      </div>

      {/* 5. シート */}
      <div
        className={`cp-sheet${bump ? " bump" : ""}`}
        style={{ "--kc": sheetKind ? KIND_COLOR[sheetKind] : "#cfd6db" } as CSSProperties}
        aria-live="polite"
      >
        {sheetItem?.cover ? (
          // eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク(images.unoptimized)
          <img src={sheetItem.cover} alt="" className="bg-white" draggable={false} />
        ) : (
          <span className="cp-noimg cp-sheet-noimg" />
        )}
        <div className="cp-sheet-body">
          <div className="cp-sheet-head">
            <div className="cp-sheet-t">{sheetItem?.title ?? "魔法の書架"}</div>
            {sheetItem && (
              <CompassShelveButton
                slug={sheetItem.slug}
                open={shelveFor === sheetItem.slug}
                onToggle={() => {
                  setShelveMsg(null);
                  setShelveFor((v) => (v === sheetItem!.slug ? null : sheetItem!.slug));
                }}
              />
            )}
          </div>
          <div className="cp-sheet-w" style={{ color: sheetColor(sheetKind) }}>
            {shelveMsg ?? why}
          </div>
          {sheetItem && shelveFor === sheetItem.slug ? (
            <CompassShelvePanel
              item={sheetItem}
              onDone={(m) => {
                setShelveFor(null);
                setShelveMsg(m);
              }}
            />
          ) : (
            catchText && <div className="cp-sheet-c">{catchText}</div>
          )}
          {goLabel && sel && shelveFor !== sheetItem?.slug && (
            <button type="button" className="cp-go" onClick={() => go(sel)}>
              {goLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
