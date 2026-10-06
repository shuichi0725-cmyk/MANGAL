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
  drawUnit,
  UNIT_MAX,
  type UnitKind,
  type UnitItem,
  RING_KINDS,
  rng,
  EMPTY_MIX,
  mixCounts,
  mixKey,
  mixSize,
  mixUnit,
  type Mix,
  EMPTY_REGENRE,
  islandPages,
  regenreKey,
  regenreKeys,
  regenreLabel,
  regenreUnit,
  themeIslands,
  type Regenre,
  narrowCounts,
  narrowUnit,
  threadEntrances,
  type Entrance,
  simThemeUnit,
} from "./compass";
import { Halftone } from "./halftone";
import { CompassShelveButton, CompassShelvePanel } from "./CompassShelve";
import KomaPage from "./KomaPage";

// ★テスト環境か(next.config.ts がビルド時の定数で埋める)。 本番は false = 下のテスト専用分岐ごと刈り取られる。
const PREVIEW = process.env.NEXT_PUBLIC_PREVIEW_FEATURES === "1";
// ★テスト環境だけ、本番の全件索引を読む(preview CI が本番の公開索引から public/prod-idx/ を作る。
//   テスト環境の索引は抜粋で糸がほぼ張れない)。 本番は基点を変えない = 本番の公開索引をそのまま読む(2026-10-03 本番化)。
//   頁のJSは水和より前に評価されるので、ここで基点を変えれば最初の読み込みから /prod-idx になる。
//   module キャッシュは全頁共有 → テスト環境ではこの頁から出る時は <a>(全頁読み込み)で出る(next/link を使わない)。
if (PREVIEW && typeof window !== "undefined") setIndexBase("/prod-idx");
// ★案C「掛け合わせて広げる」(2026-10-05): 要素・ジャンルをいくつでも選んで広げる引き出し。 いまはテスト環境だけ。
//   ★今の形(帯に要素の多い順4つ)に戻す = ここを false にするだけ。 本番にも出す = true にする。
const MIX = PREVIEW;
// ★「よく似たジャンル」の糸は「ジャンル ▾」(橙)と別物に見せる = 羅針盤マーク・同ジャンル検索と同じ黄(2026-10-05 ユーザ指示)。
//   帯の札・広げた本・糸・札の色だけ。 周りの本(ジャンル枠)と上のジャンルの札は橙のまま。 MIX と一緒に戻る。
const SIM_COLOR = "#d9f843";
// ★案2+3(2026-10-05): 「要素 ▾」= 星雲(要素ごとの本の島を押して重ねる)/「ジャンル ▾」= 組み替える(ホラー抜きのベルセルク)。
//   ★掛け合わせの引き出し(案C=要素もジャンルも同じ引き出し)に戻す = ここを false にするだけ。
const SPLIT = MIX;
// ★案6(2026-10-06): 何も選んでいない時に真ん中の本を押すと、その本の書誌が漫画の1ページ(コマ割り)になって重なる。
//   いまはテスト環境だけ。 出さない = false。
const KOMA = PREVIEW;
// ★案B(2026-10-06): 下の帯を無くし、周りの輪を「糸の入口」(書影付き)にする。 作者・雑誌・年・よく似たジャンル=押すと広がる /
//   要素・ジャンル=押して選ぶ(いくつでも重ねる)→ 真ん中の下の「広げる」。 入りきらない要素・ジャンルは「ほか ▸」の2段目。
//   ★今の形(周りの本+下の帯)に戻す = false。
const THREADS = PREVIEW;
/** 入口の大きさ(書影)と、帯が無い分の引き出しの位置 */
const EW = 54;
const EH = 76;
const BAND_H = THREADS ? 0 : 30;
/** 島の大きさ(書影3冊の束+名札) */
const IW = 66;
const IH = 86;
// ★似た要素(2026-10-06)= 要素(青)と区別する薄い水色
const SIMEL_COLOR = "#a8e4ff";
const unitColor = (u: { key: string; kind: UnitKind }) =>
  MIX && u.key === "genre" ? SIM_COLOR : u.key === "simel" ? SIMEL_COLOR : KIND_COLOR[u.kind];

const TOP = 100; // 糸の色チップ列 44 + 旅路 56
const SHEET = 96;
const NW = 58;
const NH = 81;
const CW = 92;
const CH = 128;
const STORE = "mangal.magicShelf.spreads.v1";
const PLACEHOLDER_ANGLES = [-90, -20, 20, 70, 110, 160, 200];
const FIRST = "\u0000first";

/** seed = その中央の周りの本のくじの種(戻った時・詳細から戻った時に同じ顔ぶれを出す) */
type Step = { slug: string; kind: ThreadKind | null; seed?: string };
const newSeed = () => Math.random().toString(36).slice(2, 10);
/** 詳細(作品頁)へ飛ぶ直前に旅の状態を書く = OS の戻るで帰ってきた時に復元する(2026-09-30 ユーザ要望) */
const RESUME_KEY = "mangal:compass:resume:v1";
type Resume = { path: Step[]; prev: string | null; backAng: number | null; sel: string | null; exp: string | null; drawn: { key: string; items: UnitItem[] } | null; mix?: Mix | null; re?: Regenre | null; narrow?: Mix | null; t: number };
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

export default function MagicCompass({
  magazines,
  genres = {},
  demographics = {},
}: {
  magazines: Record<string, string>;
  genres?: Record<string, string>;
  demographics?: Record<string, string>;
}) {
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
  const genreName = useCallback((k: string) => genres[k] ?? k, [genres]);
  const demoName = useCallback((k: string) => demographics[k] ?? k, [demographics]);
  // 真ん中の本のコマ割り(案6)が開いているか
  const [komaOpen, setKomaOpen] = useState(false);
  // 糸の入口の輪(案B)の「ほか ▸」= 2段目の一覧が開いているか
  const [moreOpen, setMoreOpen] = useState(false);

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
  const [off, setOff] = useState<Set<UnitKind>>(() => new Set());
  const [exp, setExp] = useState<string | null>(null);
  // 掛け合わせ(案C): 引き出しが開いているか / 引き出しで選んでいる組 / 広げた組(exp = mixKey(広げた組))
  const [mixOpen, setMixOpen] = useState(false);
  const [mix, setMix] = useState<Mix>(EMPTY_MIX);
  const [mixApplied, setMixApplied] = useState<Mix | null>(null);
  // 案2+3: 星雲が開いているか(頁) / 組み替えの引き出し・組み替え中の組・広げた組
  const [nebOpen, setNebOpen] = useState(false);
  const [nebPage, setNebPage] = useState(0);
  const [reOpen, setReOpen] = useState(false);
  const [re, setRe] = useState<Regenre>(EMPTY_REGENRE);
  const [reApplied, setReApplied] = useState<Regenre | null>(null);
  // 案4: 広げた後に「さらに絞る」(引き出しが開いているか / 選んでいる組 / 絞った組)
  const [narrowOpen, setNarrowOpen] = useState(false);
  const [narrow, setNarrow] = useState<Mix>(EMPTY_MIX);
  const [narrowApplied, setNarrowApplied] = useState<Mix | null>(null);
  const clearNarrow = useCallback(() => {
    setNarrowOpen(false);
    setNarrow(EMPTY_MIX);
    setNarrowApplied(null);
  }, []);
  // ★札(シート)の実際の高さ。 札は中身に合わせて伸びる(紹介文3行/選んでいる時は5行+進む)ので、
  //   「広げる」の帯を固定位置(下から98px)に置くと札の裏に潜って読めなくなった(2026-10-03 ユーザ指摘)。
  //   帯はいつも札のすぐ上に乗せる。 callback ref = 札が後から描かれても測れる。
  const [sheetH, setSheetH] = useState(SHEET);
  const sheetRo = useRef<ResizeObserver | null>(null);
  const sheetRef = useCallback((el: HTMLDivElement | null) => {
    sheetRo.current?.disconnect();
    sheetRo.current = null;
    if (!el) return;
    const ro = new ResizeObserver(() => setSheetH(Math.round(el.getBoundingClientRect().height)));
    ro.observe(el);
    sheetRo.current = ro;
  }, []);
  const [lays, setLays] = useState<Partial<Record<UnitKind, string>>>({});
  // 広げた糸のうち画面に出している24冊(くじ引きの結果・2026-09-30)
  const [drawn, setDrawn] = useState<{ key: string; items: UnitItem[] } | null>(null);
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
  // 書影を大きく見る(楽天の書影は 600px で取り直す=原本が大きい物は大きく出る)
  const [big, setBig] = useState<string | null>(null);
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
  const resumeDrawn = useRef<{ key: string; items: UnitItem[] } | null>(null);
  useEffect(() => {
    if (path.length || !index || !index.length) return;
    // 詳細(作品頁)から OS の戻るで帰ってきた = 飛ぶ前の旅をそのまま出す(1時間以内・1回だけ使う)
    try {
      const raw = window.sessionStorage.getItem(RESUME_KEY);
      if (raw) {
        window.sessionStorage.removeItem(RESUME_KEY);
        const r = JSON.parse(raw) as Resume;
        if (r && Array.isArray(r.path) && r.path.length && Date.now() - r.t < 3600_000) {
          resumeDrawn.current = r.drawn;
          setPath(r.path);
          setPrev(r.prev);
          setBackAng(r.backAng);
          setSel(r.sel);
          setExp(r.exp);
          if (r.mix) {
            setMix(r.mix);
            setMixApplied(r.mix);
          }
          if (r.re) {
            setRe(r.re);
            setReApplied(r.re);
          }
          if (r.narrow) {
            setNarrow(r.narrow);
            setNarrowApplied(r.narrow);
          }
          return;
        }
      }
    } catch {
      /* 読めなければ普通に始める */
    }
    const full = isFullIndexLoaded();
    const from = new URLSearchParams(window.location.search).get("from");
    if (from) {
      if (index.some((m) => m.slug === from)) {
        setPath([{ slug: from, kind: null, seed: newSeed() }]);
        return;
      }
      if (!full) return; // 先頭100件に無い = 全件を待つ
    }
    const pool = (full ? [...index].sort((a, b) => (b.popularity ?? 0) - (a.popularity ?? 0)).slice(0, 100) : index).filter(
      (m) => m.cover,
    );
    if (!pool.length) return;
    setPath([{ slug: pool[Math.floor(Math.random() * pool.length)].slug, kind: null, seed: newSeed() }]);
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
  // ★周りの本も くじ(近いほど当たりやすい・人気は使わない)。 旅で辿った本は外す(2026-09-30)
  const pathRef = useRef(path);
  pathRef.current = path;
  const visitedSet = () => new Set(pathRef.current.map((p) => p.slug));
  const nb = useMemo(
    () => (graph && curItem ? neighborhood(graph, curItem, magName, {
            rand: rng(`${curItem.slug}:${pathRef.current[pathRef.current.length - 1]?.seed ?? ""}`),
            visited: visitedSet(),
            genreName,
          }) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [graph, curItem, magName, genreName],
  );
  const placed = useMemo(() => (nb ? placeRing(nb.ring, prev, backAng, geom.rx, geom.ry) : []), [nb, prev, backAng, geom]);
  const mixFull = useMemo(
    () => (graph && curItem && mixApplied ? mixUnit(graph, curItem, mixApplied, genreName) : null),
    [graph, curItem, mixApplied, genreName],
  );
  const reFull = useMemo(
    () => (SPLIT && graph && curItem && reApplied ? regenreUnit(graph, curItem, reApplied, genreName) : null),
    [graph, curItem, reApplied, genreName],
  );
  // 似た要素(糸の入口の輪だけ・中心の要素が5つ以上の時だけ)
  const simelFull = useMemo(() => (THREADS && graph && curItem ? simThemeUnit(graph, curItem) : null), [graph, curItem]);
  const baseFull = useMemo(
    () =>
      exp && nb
        ? mixFull?.key === exp
          ? mixFull
          : reFull?.key === exp
            ? reFull
            : simelFull?.key === exp
              ? simelFull
              : (nb.units.find((u) => u.key === exp) ?? null)
        : null,
    [exp, nb, mixFull, reFull, simelFull],
  );
  // 「さらに絞る」を掛けた後の単位(何も絞っていなければ元のまま)
  const unitFull = useMemo(
    () => (baseFull && graph && SPLIT && narrowApplied ? (narrowUnit(graph, baseFull, narrowApplied, genreName) ?? baseFull) : baseFull),
    [baseFull, graph, narrowApplied, genreName],
  );
  const narrowInfo = useMemo(
    () => (SPLIT && narrowOpen && baseFull && graph && curItem ? narrowCounts(graph, baseFull, curItem, narrow) : null),
    [narrowOpen, baseFull, graph, curItem, narrow],
  );
  // 星雲の島(中心の本の要素ごと)と、組み替えの引き出しの冊数
  const islands = useMemo(() => (SPLIT && graph && curItem ? islandPages(themeIslands(graph, curItem)) : null), [graph, curItem]);
  // 糸の入口(案B): 輪に出す入口と「ほか」に回す入口
  const entrances = useMemo(
    () => (THREADS && graph && curItem && nb ? threadEntrances(graph, curItem, nb.units, genreName, 10, simelFull) : null),
    [graph, curItem, nb, genreName, simelFull],
  );
  const reDraft = useMemo(
    () => (SPLIT && reOpen && graph && curItem ? regenreUnit(graph, curItem, re, genreName) : null),
    [reOpen, graph, curItem, re, genreName],
  );
  // 引き出しの札(中心の本の要素・ジャンル全部・冊数の多い順)と冊数
  const mixBase = useMemo(() => (MIX && graph && curItem ? mixCounts(graph, curItem, EMPTY_MIX) : null), [graph, curItem]);
  const mixInfo = useMemo(() => {
    if (!mixBase || !graph || !curItem) return null;
    const c = mixSize(mix) ? mixCounts(graph, curItem, mix) : mixBase;
    const byN = (m: Map<string, number>) => [...m.keys()].sort((a, b) => (m.get(b) ?? 0) - (m.get(a) ?? 0));
    return { c, themes: byN(mixBase.themes), genres: byN(mixBase.genres) };
  }, [mixBase, graph, curItem, mix]);
  // 帯に出す単位: 掛け合わせの時は要素の単位(多い順4つ)を出さない = 引き出しから選ぶ
  const bandUnits = useMemo(() => (nb ? (MIX ? nb.units.filter((u) => u.kind !== "elem") : nb.units) : []), [nb]);
  // 開くたびに候補全体から24冊をくじで引く(引き直しは直前の24冊を外して引く)
  useEffect(() => {
    if (!unitFull) {
      setDrawn(null);
      return;
    }
    const r = resumeDrawn.current;
    resumeDrawn.current = null;
    if (r && r.key === unitFull.key) {
      setDrawn(r);
      return;
    }
    setDrawn({ key: unitFull.key, items: drawUnit(unitFull, Math.random, visitedSet()) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unitFull]);
  const unit = useMemo(
    () => (unitFull && drawn && drawn.key === unitFull.key ? { ...unitFull, items: drawn.items } : null),
    [unitFull, drawn],
  );
  const redraw = useCallback(() => {
    if (!unitFull || !drawn || busy.current) return;
    setSel(null);
    setDrawn({ key: unitFull.key, items: drawUnit(unitFull, Math.random, visitedSet(), new Set(drawn.items.map((i) => i.slug))) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unitFull, drawn]);
  const spreadOf = useCallback((k: UnitKind) => resolveSpread(k, lays[k]), [lays]);
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
    // 網点の出方の表示は見比べ用 = テスト環境だけ(2026-10-04 ユーザ指示「本番はいらない」)
    if (PREVIEW) h.onTone = (name) => showToast(`網点の出方: ${name}`);
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
        setMixOpen(false);
        setMix(EMPTY_MIX);
        setMixApplied(null);
        setNebOpen(false);
        setNebPage(0);
        setReOpen(false);
        setRe(EMPTY_REGENRE);
        setReApplied(null);
        setNarrowOpen(false);
        setNarrow(EMPTY_MIX);
        setNarrowApplied(null);
        setKomaOpen(false);
        setMoreOpen(false);
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
          (ps) => [...ps, { slug, kind: unit.kind, seed: newSeed() }],
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
      travel(slug, { x: o.dx, y: o.dy, w: NW, h: NH, small: false }, kind, (ps) => [...ps, { slug, kind, seed: newSeed() }]);
    },
    [unit, spread, placed, path, geom, travel, jumpBack],
  );

  const tapNode = useCallback(
    (slug: string) => {
      if (busy.current) return;
      if (slug === cur) {
        // 何も選んでいない時に真ん中を押す = その本のコマ割り(案6)。 選んでいる時は今までどおり選択を外すだけ
        if (KOMA && !sel) setKomaOpen(true);
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
    (k: UnitKind) => {
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
      setMixOpen(false);
      setNebOpen(false);
      setReOpen(false);
      clearNarrow();
      setMoreOpen(false);
      setExp((e) => (!key || key === e ? null : key));
      bumpSheet();
    },
    [bumpSheet, clearNarrow],
  );

  // 掛け合わせ: 札を押すたび 選ぶ/外す。 「広げる」で今の組を広げる(同じ組をもう一度でも引き直す)
  const toggleMix = useCallback((part: "themes" | "genres", v: string) => {
    setMix((m) => ({ ...m, [part]: m[part].includes(v) ? m[part].filter((x) => x !== v) : [...m[part], v] }));
  }, []);
  const applyMix = useCallback(() => {
    if (busy.current || !mixSize(mix)) return;
    setSel(null);
    setGrowFor(null);
    setMixOpen(false);
    setNebOpen(false);
    setMoreOpen(false);
    clearNarrow();
    setMixApplied({ themes: [...mix.themes], genres: [...mix.genres] });
    setExp(mixKey(mix));
    bumpSheet();
  }, [mix, bumpSheet, clearNarrow]);

  // 星雲: 開くと周りの本が退いて要素の島が浮かぶ(広げている糸は閉じる)
  const toggleNeb = useCallback(() => {
    if (busy.current) return;
    setSel(null);
    setReOpen(false);
    setNarrowOpen(false);
    setNebOpen((o) => {
      if (!o) setExp(null);
      return !o;
    });
  }, []);
  // 組み替え: 中心のジャンルは押すと外す/戻す、ほかのジャンルは押すと足す/やめる
  const toggleRe = useCallback((k: string, own: boolean) => {
    setRe((r) =>
      own
        ? { ...r, drop: r.drop.includes(k) ? r.drop.filter((x) => x !== k) : [...r.drop, k] }
        : { ...r, add: r.add.includes(k) ? r.add.filter((x) => x !== k) : [...r.add, k] },
    );
  }, []);
  const toggleReOpen = useCallback(() => {
    if (busy.current) return;
    setNebOpen(false);
    setNarrowOpen(false);
    setReOpen((o) => !o);
  }, []);
  const applyRe = useCallback(() => {
    if (busy.current || (!re.drop.length && !re.add.length)) return;
    setSel(null);
    setGrowFor(null);
    setReOpen(false);
    clearNarrow();
    setReApplied({ drop: [...re.drop], add: [...re.add] });
    setExp(regenreKey(re));
    bumpSheet();
  }, [re, bumpSheet, clearNarrow]);

  // さらに絞る: 札を押すたび選ぶ/外す →「〜に絞る」で掛ける(何も選ばずに押せば絞りを外す)
  const toggleNarrow = useCallback((part: "themes" | "genres", v: string) => {
    setNarrow((m) => ({ ...m, [part]: m[part].includes(v) ? m[part].filter((x) => x !== v) : [...m[part], v] }));
  }, []);
  const applyNarrow = useCallback(() => {
    if (busy.current) return;
    setSel(null);
    setNarrowOpen(false);
    setNarrowApplied(mixSize(narrow) ? { themes: [...narrow.themes], genres: [...narrow.genres] } : null);
    bumpSheet();
  }, [narrow, bumpSheet]);

  const chooseSpread = useCallback((k: UnitKind, s: Spread) => {
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
      if (komaOpen) setKomaOpen(false);
      else if (moreOpen) setMoreOpen(false);
      else if (mixOpen) setMixOpen(false);
      else if (nebOpen) setNebOpen(false);
      else if (reOpen) setReOpen(false);
      else if (narrowOpen) setNarrowOpen(false);
      else if (sel) setSel(null);
      else if (exp) setExp(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sel, exp, mixOpen, nebOpen, reOpen, narrowOpen, komaOpen, moreOpen]);

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
        hidden: !!xs || nebOpen || THREADS || (!o.back && off.has(o.kind as UnitKind)),
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
          color: unitColor(unit),
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
  }, [cur, curItem, cw, geom, pan, spread, unit, placed, off, sel, firstRing, nebOpen]);

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
        L.push({ key: "axis", x1: a.x, y1: a.y, x2: b.x, y2: b.y, color: unitColor(unit), width: 1, opacity: 0.6 });
        const c1 = toW(spread.center.x, spread.center.y + spread.center.h / 2 + 4);
        L.push({ key: "cdot", x1: c1.x, y1: c1.y, x2: c1.x, y2: a.y, color: "#ffffff88", width: 1, opacity: 1, dash: "3 4" });
      } else if (sel) {
        const p = spread.P.find((x) => x.slug === sel);
        if (p) {
          const t = toW(p.x, p.y);
          L.push({ key: `x:${sel}`, x1: cw.x, y1: cw.y, x2: t.x, y2: t.y, color: unitColor(unit), width: 2.6, opacity: 0.9, sel: true });
        }
      }
      return L;
    }
    return placed
      .filter((o) => o.slug !== cur)
      .map((o) => {
        const hidden = !o.back && off.has(o.kind as UnitKind);
        const isSel = sel === o.slug;
        return {
          key: `l:${o.slug}`,
          x1: cw.x,
          y1: cw.y,
          x2: cw.x + o.dx,
          y2: cw.y + o.dy,
          color: KIND_COLOR[o.back ? "back" : o.kind],
          width: isSel ? 3.4 : sel ? 1.2 : o.back ? 1.4 : 2.2,
          opacity: hidden || nebOpen || THREADS ? 0 : o.back ? 0.7 : 0.9,
          dash: o.back && !isSel ? "3 5" : undefined,
          sel: isSel,
          lineIn: !o.back && (growFor === cur || growFor === FIRST),
        };
      });
  }, [cur, curItem, cw, geom, pan, spread, unit, placed, off, sel, growFor, nebOpen]);

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
    why = failed ? "索引が読めませんでした" : "星図を描いています…";
  } else if (!nb) {
    why = failed ? "索引が読めませんでした" : "いまの中心 ・ 星図を描いています…";
  } else if (unit) {
    sheetKind = unit.kind;
    if (sel) {
      const it = unit.items.find((i) => i.slug === sel);
      sheetItem = lookup(sel) ?? curItem;
      why = `${KIND_NAME[unit.kind]} — ${unit.label}${it?.shared ? ` ・ 共通の要素${it.shared}つ` : ""}`;
      goLabel = `〈${unit.label}〉の糸で進む →`;
    } else {
      why = `「${unit.label}」の糸を広げています(候補${(unitFull?.items.length ?? unit.items.length).toLocaleString()}冊から${unit.items.length}冊) ・ ${unit.note ? `${unit.note} ・ ` : ""}本に触れて選ぶ`;
    }
  } else {
    const o = sel ? placed.find((x) => x.slug === sel) : null;
    if (o) {
      sheetItem = lookup(o.slug) ?? curItem;
      sheetKind = o.back ? "back" : o.kind;
      why = o.back ? "来た道" : `${KIND_NAME[o.kind]} — ${o.label}`;
      goLabel = o.back ? "来た道を戻る ←" : `〈${KIND_NAME[o.kind]}〉の糸で進む →`;
    } else {
      why = !THREADS
        ? "いまの中心 ・ 周りの本に触れるか、下の「広げる」から糸を選ぶ"
        : mixSize(mix)
          ? `「${[...mix.themes, ...mix.genres.map(genreName)].join("×")}」を選択中 ・ ほかの要素・ジャンルを押すと重なる`
          : "いまの中心 ・ 周りの書影=糸の入口。押すと広がる(要素・ジャンルは押して重ねる)";
    }
  }
  const catchText = sheetItem?.catch || (catchReady ? "(紹介文はまだありません)" : "");

  // ★詳細 = 作品頁。 テスト環境は作品頁が17作だけなので本番サイトの頁へ(公開slugは本番と同じ)
  const detailHref = (slug: string) =>
    typeof window !== "undefined" && window.location.hostname !== "mangal-db.com"
      ? `https://mangal-db.com/manga/${encodeURIComponent(slug)}`
      : `/manga/${encodeURIComponent(slug)}`;
  const saveResume = () => {
    try {
      const r: Resume = { path, prev, backAng, sel, exp, drawn, mix: exp && mixFull?.key === exp ? mixApplied : null, re: exp && reFull?.key === exp ? reApplied : null, narrow: exp ? narrowApplied : null, t: Date.now() };
      window.sessionStorage.setItem(RESUME_KEY, JSON.stringify(r));
    } catch {
      /* 書けなくても飛ぶ(戻った時は新しい旅) */
    }
  };

  // ★選んだ本へ舞台ごと寄る(2026-10-03 ユーザ裁定=案D): 周りの本は約58pxで書影が見えづらかった。
  //   選んだ本が舞台の中ほどで幅約130pxになるよう、世界(本+糸+ラベル)をまとめて拡大する。
  //   位置関係は崩れない(他の本・糸も一緒に大きくなる)。 進む(pan)中はやめる= 手繰る動きと同時に引く。
  //   ★寄った後の大きさは本によらず同じ(2026-10-03 ユーザ指摘): 星屑の本は3段の大きさ・年表は34px・
  //   周りの本は58pxと元が違う。旧は倍率を2〜4倍で頭打ちにしていたので、小さい本は小さく大きい本は大きく残った。
  //   = 同じ枠(幅 tw × 高さ tw*1.4)にちょうど収まる倍率を本ごとに出す(上限・下限なし)。
  const zoom = useMemo(() => {
    if (!sel || pan) return null;
    const n = nodes.find((x) => x.slug === sel && !x.center);
    if (!n) return null;
    const stageH = Math.max(240, vp.h - TOP - SHEET);
    const tw = Math.min(vp.w * 0.36, 150);
    const s = Math.min(tw / n.w, (tw * 1.4) / n.h);
    // 選ぶとシートが伸びて舞台の下を覆うので、狙う高さは舞台の真ん中より少し上
    return { s, tx: -s * n.x, ty: stageH * 0.44 - geom.CY - s * n.y };
  }, [sel, pan, nodes, vp, geom.CY]);
  const worldStyle: CSSProperties = {
    left: geom.CX,
    top: geom.CY,
    transform: zoom
      ? `translate(${zoom.tx}px, ${zoom.ty}px) scale(${zoom.s})`
      : `translate(${-cam.x}px, ${-cam.y}px) scale(1)`,
  };

  // 掛け合わせの入口: 要素 ▾ / ジャンル ▾(どちらも同じ引き出しを開く)。 広げた組の札は「✕ 閉じる」の隣(押すと引き出しで組み直す)
  const mixShown = exp && mixFull?.key === exp ? mixFull : null;
  const reShown = exp && reFull?.key === exp ? reFull : null;
  const toggleMixOpen = () => {
    if (busy.current) return;
    setMixOpen((o) => !o);
  };
  const mixChips = () => {
    if (!mixInfo) return null;
    // 案2+3: 要素 = 星雲 / ジャンル = 組み替え。 SPLIT=false なら両方とも掛け合わせの引き出し
    const eOpen = SPLIT ? nebOpen : mixOpen;
    const gOpen = SPLIT ? reOpen : mixOpen;
    return (
      <>
        {mixInfo.themes.length > 0 && (
          <button
            type="button"
            className={`cp-uc${SPLIT && eOpen ? " on" : ""}`}
            style={{ "--c": KIND_COLOR.elem } as CSSProperties}
            aria-expanded={eOpen}
            onClick={SPLIT ? toggleNeb : toggleMixOpen}
          >
            要素<i>{mixInfo.themes.length}</i> {eOpen ? "▴" : "▾"}
          </button>
        )}
        {mixInfo.genres.length > 0 && (
          <button
            type="button"
            className={`cp-uc${SPLIT && gOpen ? " on" : ""}`}
            style={{ "--c": KIND_COLOR.genre } as CSSProperties}
            aria-expanded={gOpen}
            onClick={SPLIT ? toggleReOpen : toggleMixOpen}
          >
            ジャンル<i>{mixInfo.genres.length}</i> {gOpen ? "▴" : "▾"}
          </button>
        )}
      </>
    );
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
        {RING_KINDS.map((k) => (
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
      </div>
      {/* ★案D(2026-09-30): 旅を保存は旅の操作なので旅路の段の右端(上の列は糸5つ) */}
      <button type="button" className="cp-save" onClick={() => showToast("旅の保存は準備中です")}>
        旅を保存
      </button>

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
      {/* ★何もない所を押したら選択を外す(2026-09-30 ユーザ要望)。 本・年表ボタンなど button を押した時は各自の動き */}
      <div
        className={`cp-stage${zoom ? " zoom" : ""}`}
        onClick={(e) => {
          if ((e.target as HTMLElement).closest("button, a")) return;
          if (busy.current) return;
          // ★何もない所を押す = 1段ずつ取り消す(2026-10-06 ユーザ「関係ないところを押してもキャンセル」):
          //   選んだ本 → 「ほか」の一覧 → 広げた糸(= ✕ 閉じる と同じ) → 選んだ要素・ジャンル
          if (sel) setSel(null);
          else if (THREADS && moreOpen) setMoreOpen(false);
          else if (THREADS && exp) openUnit(null);
          else if (THREADS && mixSize(mix)) setMix(EMPTY_MIX);
        }}
      >
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
              {failed ? "索引が読めませんでした" : "星図を描いています…"}
            </p>
          </div>
        )}
        {!curItem && (
          <p className="cp-wait-text" style={{ top: geom.CY - 8 }}>
            {failed ? "索引が読めませんでした" : "星図を描いています…"}
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
        {/* ★広げ方は「星屑」が基本・切り替えは「年表」だけ(2026-09-30 ユーザ裁定)。 同じ年の糸では年表を使えないので出さない。
            右に「引き直す」= 同じ糸の別の24冊をくじで引く(候補が24冊より多い時だけ) */}
        {unit && (
          <div className="cp-spreads" role="group" aria-label="広げ方">
            {/* 案B: 帯が無いので「閉じる」はここ */}
            {THREADS && (
              <button type="button" className="cp-sp" style={{ "--c": "#e6ecf0" } as CSSProperties} onClick={() => openUnit(null)}>
                ✕ 閉じる
              </button>
            )}
            {allowedSpreads(unit.kind).includes("time") &&
              (() => {
                const on = spreadOf(unit.kind) === "time";
                return (
                  <button
                    type="button"
                    className={`cp-sp${on ? " on" : ""}`}
                    style={{ "--c": unitColor(unit) } as CSSProperties}
                    aria-pressed={on}
                    title={on ? "星屑に戻す" : "連載開始の年で並べる"}
                    onClick={() => chooseSpread(unit.kind, on ? "dust" : "time")}
                  >
                    <SpreadIcon k="time" />
                    年表
                  </button>
                );
              })()}
            {(unitFull?.items.length ?? 0) > UNIT_MAX && (
              <button
                type="button"
                className="cp-sp"
                style={{ "--c": unitColor(unit) } as CSSProperties}
                title="同じ糸の別の本をくじで引き直す"
                onClick={redraw}
              >
                ↻ 引き直す
              </button>
            )}
            {/* 案B: 「⚗ さらに絞る」も帯からここへ */}
            {THREADS && baseFull && (
              <button
                type="button"
                className={`cp-sp cp-sp-nar${narrowApplied || narrowOpen ? " on" : ""}`}
                style={{ "--c": "#e6ecf0" } as CSSProperties}
                aria-expanded={narrowOpen}
                onClick={() => {
                  if (busy.current) return;
                  setReOpen(false);
                  setNarrow(narrowApplied ?? EMPTY_MIX);
                  setNarrowOpen((o) => !o);
                }}
              >
                ⚗ {narrowApplied ? [...narrowApplied.themes, ...narrowApplied.genres.map(genreName)].join("×") : "さらに絞る"}
              </button>
            )}
          </div>
        )}
        {/* 案B: 糸の入口の輪(広げていない時) */}
        {THREADS && entrances && mixInfo && !unit && !pan && (
          <div className="cp-ents">
            {(() => {
              const shown = entrances.ring.filter((e) => !off.has(e.kind === "sim" ? "genre" : e.kind === "simel" ? "elem" : e.kind));
              // 「ほか ▸」は似た要素・要素の前(無ければ年の前)= 輪の下側。 似た要素は「ほか」の左隣
              let at = shown.findIndex((e) => e.kind === "simel" || e.kind === "elem");
              if (at < 0) at = shown.findIndex((e) => e.kind === "year");
              if (at < 0) at = shown.length;
              const all: (Entrance | "more")[] = entrances.more.length ? [...shown.slice(0, at), "more", ...shown.slice(at)] : shown;
              const n = all.length;
              const any = mixSize(mix) > 0;
              const pts = all.map((_, k) => {
                const a = ((-90 + (k * 360) / Math.max(1, n)) * Math.PI) / 180;
                return { x: geom.CX + geom.rx * Math.cos(a), y: geom.CY + geom.ry * Math.sin(a) };
              });
              // ★線は書影の縁から縁まで(2026-10-06 ユーザ指摘「線が書影をつきぬけてる」: 入口の線は中心の本より上の層にある)
              const edgeLine = (x1: number, y1: number, x2: number, y2: number) => {
                const dx = x2 - x1;
                const dy = y2 - y1;
                const cut = (hw: number, hh: number) => Math.min(dx ? hw / Math.abs(dx) : Infinity, dy ? hh / Math.abs(dy) : Infinity);
                const a = cut(CW / 2 + 3, CH / 2 + 3);
                const b = 1 - cut(EW / 2 + 2, EH / 2 + 2);
                return { x1: x1 + dx * a, y1: y1 + dy * a, x2: x1 + dx * Math.max(a, b), y2: y1 + dy * Math.max(a, b) };
              };
              const colorOf = (e: Entrance | "more") =>
                e === "more" ? "#8a96a0" : e.kind === "sim" ? SIM_COLOR : e.kind === "simel" ? SIMEL_COLOR : KIND_COLOR[e.kind as UnitKind];
              return (
                <>
                  <svg className="cp-ent-ln" width={geom.W} height={geom.H} aria-hidden="true">
                    {all.map((e, k) => {
                      const on = e !== "more" && (e.kind === "elem" || e.kind === "genre") && mix[e.kind === "elem" ? "themes" : "genres"].includes(e.value);
                      return (
                        <line
                          key={k}
                          {...edgeLine(geom.CX, geom.CY, pts[k].x, pts[k].y)}
                          style={{
                            stroke: colorOf(e),
                            strokeWidth: on ? 3.4 : e === "more" ? 1.4 : 2,
                            opacity: any && !on ? 0.35 : 0.85,
                            strokeDasharray: e === "more" ? "3 4" : undefined,
                          }}
                        />
                      );
                    })}
                  </svg>
                  {all.map((e, k) => {
                    const { x, y } = pts[k];
                    if (e === "more") {
                      const stack = entrances.more.slice(0, 3);
                      const nE = entrances.more.filter((m) => m.kind === "elem").length;
                      const nG = entrances.more.length - nE;
                      return (
                        <button
                          key="more"
                          type="button"
                          className="cp-ent more"
                          style={{ left: x - EW / 2, top: y - EH / 2 }}
                          onClick={() => {
                            if (busy.current) return;
                            setReOpen(false);
                            setMoreOpen((o) => !o);
                          }}
                        >
                          <span className="cp-ent-stk">
                            {stack.map((m, i) =>
                              m.cover ? (
                                // eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク(images.unoptimized)
                                <img key={m.key} src={m.cover} alt="" className="bg-white" draggable={false} style={{ left: i * 8, top: 6 - i * 4 }} />
                              ) : null,
                            )}
                          </span>
                          <b>
                            {[nE ? `要素 ほか${nE}` : "", nG ? `ジャンル ほか${nG}` : ""].filter(Boolean).join("・")} ▸
                          </b>
                        </button>
                      );
                    }
                    const ent: Entrance = e; // ★クロージャの中でも絞り込みが効くよう、ここで固定する
                    const pick = e.kind === "elem" || e.kind === "genre";
                    const part = e.kind === "elem" ? "themes" : "genres";
                    const on = pick && mix[part].includes(e.value);
                    // 要素・ジャンルの冊数 = 近い本の段の数(何も選んでいない時もその札だけの近い本の数)。 全体の冊数は出さない
                    const cnt = pick ? (mixInfo.c[part].get(e.value) ?? 0) : e.count;
                    return (
                      <button
                        key={e.key}
                        type="button"
                        className={`cp-ent${on ? " on" : ""}${!pick && any ? " quiet" : ""}`}
                        style={{ left: x - EW / 2, top: y - EH / 2, "--c": colorOf(e) } as CSSProperties}
                        aria-pressed={pick ? on : undefined}
                        disabled={pick && !on && any && cnt === 0}
                        onClick={() => {
                          if (busy.current) return;
                          if ("unitKey" in ent) openUnit(ent.unitKey);
                          // ★選んである入口をもう一度押す = 広げる(2026-10-06 ユーザ指示。 下の「広げる」ボタンと同じ)
                          else if (on) {
                            if (mixInfo.c.total) applyMix();
                          } else toggleMix(part, ent.value);
                        }}
                      >
                        {e.cover ? (
                          // eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク(images.unoptimized)
                          <img src={e.cover} alt="" className="bg-white" draggable={false} />
                        ) : (
                          <span className="cp-noimg" />
                        )}
                        <b>
                          {e.label}
                          {!on && <i>{pick && any ? `→${cnt.toLocaleString()}` : cnt.toLocaleString()}</i>}
                        </b>
                      </button>
                    );
                  })}
                  {any && (
                    <div className="cp-neb-foot" style={{ top: geom.CY + CH / 2 + 10 }}>
                      <button type="button" className="cp-neb-go" disabled={!mixInfo.c.total} onClick={applyMix}>
                        <span className="cp-neb-go-t">{[...mix.themes, ...mix.genres.map(genreName)].join(" × ")}</span>
                        <b>{mixInfo.c.total.toLocaleString()}冊</b>を広げる ›
                      </button>
                    </div>
                  )}
                </>
              );
            })()}
          </div>
        )}
        {/* 案2+3: 要素の星雲 = 周りの本が退き、要素ごとの本の束(島)が中心を囲む。 島を押して重ね、下の札で広げる */}
        {SPLIT && nebOpen && islands && mixInfo && !pan && (
          <div className="cp-neb">
            {(() => {
              const page = islands[Math.min(nebPage, islands.length - 1)] ?? [];
              const any = mix.themes.length > 0;
              return page.map((isl, k) => {
                // 島が偶数なら半歩ずらす = 真下(下の札・広げるボタンの所)に島を置かない
                const start = page.length % 2 ? -90 : -90 + 180 / page.length;
                const a = ((start + (k * 360) / page.length) * Math.PI) / 180;
                const x = geom.CX + geom.rx * Math.cos(a);
                const y = geom.CY + geom.ry * Math.sin(a);
                const on = mix.themes.includes(isl.theme);
                const n = any ? (mixInfo.c.themes.get(isl.theme) ?? 0) : isl.count;
                return (
                  <button
                    key={isl.theme}
                    type="button"
                    className={`cp-isl${on ? " on" : ""}`}
                    style={{ left: x - IW / 2, top: y - IH / 2, width: IW, height: IH }}
                    aria-pressed={on}
                    disabled={!on && any && n === 0}
                    onClick={() => toggleMix("themes", isl.theme)}
                  >
                    <span className="cp-isl-stk">
                      {isl.covers.map((slug, i) => {
                        const m = lookup(slug);
                        return m?.cover ? (
                          // eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク(images.unoptimized)
                          <img key={slug} src={m.cover} alt="" className="bg-white" draggable={false} style={{ left: i * 12, top: 8 - i * 4 }} />
                        ) : null;
                      })}
                    </span>
                    <b>
                      {isl.theme}
                      {!on && <i>{any ? `→${n.toLocaleString()}` : n.toLocaleString()}</i>}
                    </b>
                  </button>
                );
              });
            })()}
            <div className="cp-neb-foot" style={{ top: geom.CY + CH / 2 + 10 }}>
              {mix.themes.length ? (
                <button type="button" className="cp-neb-go" disabled={!mixInfo.c.total} onClick={applyMix}>
                  <span className="cp-neb-go-t">{mix.themes.join(" × ")}</span>
                  <b>{mixInfo.c.total.toLocaleString()}冊</b>を広げる ›
                </button>
              ) : (
                <span className="cp-neb-hint">要素の島を押して重ねる</span>
              )}
            </div>
            {islands.length > 1 && (
              <button type="button" className="cp-neb-page" onClick={() => setNebPage((p) => (p + 1) % islands.length)}>
                ほかの島 {Math.min(nebPage, islands.length - 1) + 1}/{islands.length} ▸
              </button>
            )}
            {mix.themes.length > 0 && (
              <button type="button" className="cp-neb-clr" onClick={() => setMix(EMPTY_MIX)}>
                選び直す
              </button>
            )}
          </div>
        )}
      </div>

      {/* 4. 広げる ▸(案Bでは出さない = 糸の入口は周りの輪) */}
      {!THREADS && (
      <div className="cp-units" style={{ bottom: Math.max(SHEET + 2, sheetH + 2) }}>
        {nb && !exp && <span className="cp-ul">広げる ▸</span>}
        {exp && (
          <button type="button" className="cp-uc cp-uc-x" onClick={() => openUnit(null)}>
            ✕ 閉じる
          </button>
        )}
        {MIX && mixShown && (
          <button
            type="button"
            className="cp-uc on"
            style={{ "--c": KIND_COLOR[mixShown.kind] } as CSSProperties}
            aria-pressed
            title="組み直す"
            onClick={SPLIT ? toggleNeb : toggleMixOpen}
          >
            {mixShown.label}
            <i>{mixShown.items.length}</i>
          </button>
        )}
        {SPLIT && reShown && (
          <button
            type="button"
            className="cp-uc on"
            style={{ "--c": KIND_COLOR.genre } as CSSProperties}
            aria-pressed
            title="組み替え直す"
            onClick={toggleReOpen}
          >
            {reShown.label}
            <i>{reShown.items.length}</i>
          </button>
        )}
        {/* 案4: どの糸で広げた後でも「⚗ さらに絞る」(絞った後は 絞った組+冊数) */}
        {SPLIT && exp && baseFull && (
          <button
            type="button"
            className={`cp-uc cp-uc-nar${narrowApplied || narrowOpen ? " on" : ""}`}
            aria-expanded={narrowOpen}
            onClick={() => {
              if (busy.current) return;
              setNebOpen(false);
              setReOpen(false);
              setNarrow(narrowApplied ?? EMPTY_MIX);
              setNarrowOpen((o) => !o);
            }}
          >
            ⚗ {narrowApplied ? [...narrowApplied.themes, ...narrowApplied.genres.map(genreName)].join("×") : "さらに絞る"}
            {narrowApplied && unitFull && <i>{unitFull.items.length}</i>} {narrowOpen ? "▴" : "▾"}
          </button>
        )}
        {bandUnits.map((u) => (
          <span key={u.key} className="cp-ucw">
            {/* 掛け合わせの入口(要素 ▾ / ジャンル ▾)は「似たジャンル」の前に置く */}
            {MIX && u.kind === "genre" && mixChips()}
            <button
              type="button"
              className={`cp-uc${exp === u.key ? " on" : ""}`}
              style={{ "--c": unitColor(u) } as CSSProperties}
              aria-pressed={exp === u.key}
              onClick={() => openUnit(u.key)}
            >
              {u.label}
              <i>{u.items.length}</i>
            </button>
          </span>
        ))}
        {MIX && !bandUnits.some((u) => u.kind === "genre") && mixChips()}
        {nb && !nb.units.length && !(mixInfo && (mixInfo.themes.length || mixInfo.genres.length)) && (
          <span className="cp-ul">この本から広げられる糸はありません</span>
        )}
      </div>
      )}

      {/* 4b. 掛け合わせの引き出し(案C・テスト環境だけ) */}
      {MIX && mixOpen && mixInfo && (
        <div className="cp-mix" style={{ bottom: Math.max(SHEET + 2, sheetH + 2) + BAND_H }} role="dialog" aria-label="掛け合わせて広げる">
          <div className="cp-mix-h">
            <span>掛け合わせる ・ いくつでも選べる</span>
            {mixSize(mix) > 0 && (
              <button type="button" className="cp-mix-clr" onClick={() => setMix(EMPTY_MIX)}>
                選び直す
              </button>
            )}
            <button type="button" className="cp-mix-x" aria-label="閉じる" onClick={() => setMixOpen(false)}>
              ✕
            </button>
          </div>
          <div className="cp-mix-body">
            {(["themes", "genres"] as const).map((part) => {
              const keys = mixInfo[part];
              if (!keys.length) return null;
              const kind = part === "themes" ? "elem" : "genre";
              const counts = mixInfo.c[part];
              const any = mixSize(mix) > 0;
              return (
                <div key={part}>
                  <div className="cp-mix-sec">{part === "themes" ? "要素" : "ジャンル"}</div>
                  <div className="cp-mix-tags">
                    {keys.map((k) => {
                      const on = mix[part].includes(k);
                      const n = counts.get(k) ?? 0;
                      return (
                        <button
                          key={k}
                          type="button"
                          className={`cp-mt${on ? " on" : ""}`}
                          style={{ "--c": KIND_COLOR[kind] } as CSSProperties}
                          aria-pressed={on}
                          disabled={!on && n === 0}
                          onClick={() => toggleMix(part, k)}
                        >
                          {part === "genres" ? genreName(k) : k}
                          {!on && <i>{any ? `→${n.toLocaleString()}` : n.toLocaleString()}</i>}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
          <button
            type="button"
            className="cp-mix-go"
            style={{ "--c": KIND_COLOR[mix.themes.length ? "elem" : "genre"] } as CSSProperties}
            disabled={!mixSize(mix) || !mixInfo.c.total}
            onClick={applyMix}
          >
            {mixSize(mix) ? (
              <>
                {[...mix.themes, ...mix.genres.map(genreName)].join(" × ")} で広げる <b>{mixInfo.c.total.toLocaleString()}冊</b>
              </>
            ) : (
              "要素・ジャンルを選ぶ"
            )}
          </button>
        </div>
      )}

      {/* 4c. ジャンルを組み替える(案2) */}
      {SPLIT && reOpen && curItem && (
        <div
          className="cp-mix cp-re"
          style={{ bottom: Math.max(SHEET + 2, sheetH + 2) + BAND_H }}
          role="dialog"
          aria-label="ジャンルを組み替える"
        >
          <div className="cp-mix-h">
            <span>ジャンルを組み替える</span>
            {(re.drop.length > 0 || re.add.length > 0) && (
              <button type="button" className="cp-mix-clr" onClick={() => setRe(EMPTY_REGENRE)}>
                元に戻す
              </button>
            )}
            <button type="button" className="cp-mix-x" aria-label="閉じる" onClick={() => setReOpen(false)}>
              ✕
            </button>
          </div>
          <div className="cp-mix-body">
            <div className="cp-mix-sec">{curItem.title}のジャンル(押すと外す)</div>
            <div className="cp-mix-tags">
              {[...new Set(curItem.genres ?? [])].map((k) => {
                const ng = re.drop.includes(k);
                return (
                  <button
                    key={k}
                    type="button"
                    className={`cp-mt${ng ? " ng" : " on"}`}
                    style={{ "--c": KIND_COLOR.genre } as CSSProperties}
                    aria-pressed={!ng}
                    onClick={() => toggleRe(k, true)}
                  >
                    {ng ? "✕ " : ""}
                    {genreName(k)}
                  </button>
                );
              })}
            </div>
            <div className="cp-mix-sec">足してみる</div>
            <div className="cp-mix-tags">
              {Object.keys(genres)
                .filter((k) => !(curItem.genres ?? []).includes(k))
                .map((k) => {
                  const on = re.add.includes(k);
                  return (
                    <button
                      key={k}
                      type="button"
                      className={`cp-mt add${on ? " on" : ""}`}
                      style={{ "--c": KIND_COLOR.genre } as CSSProperties}
                      aria-pressed={on}
                      onClick={() => toggleRe(k, false)}
                    >
                      ＋{genreName(k)}
                    </button>
                  );
                })}
            </div>
          </div>
          <button
            type="button"
            className="cp-mix-go"
            style={{ "--c": KIND_COLOR.genre } as CSSProperties}
            disabled={!reDraft}
            onClick={applyRe}
          >
            {!re.drop.length && !re.add.length ? (
              "外すか足すと、その本に似た本を探す"
            ) : !regenreKeys(curItem, re).length ? (
              "ジャンルが1つも残っていません"
            ) : reDraft ? (
              <>
                {regenreLabel(re, genreName)}の{curItem.title}に似た本 <b>{reDraft.items.length.toLocaleString()}冊</b>
                {reDraft.note && <span className="cp-mix-note">{reDraft.note}</span>}
              </>
            ) : (
              "似た本が見つかりません"
            )}
          </button>
        </div>
      )}

      {/* 4e. さらに絞る(案4): いま広げている本を、中心の本の要素・ジャンルで絞る */}
      {SPLIT && narrowOpen && narrowInfo && baseFull && (
        <div
          className="cp-mix cp-nar"
          style={{ bottom: Math.max(SHEET + 2, sheetH + 2) + BAND_H }}
          role="dialog"
          aria-label="さらに絞る"
        >
          <div className="cp-mix-h">
            <span>さらに絞る ・ いま広げている{baseFull.items.length.toLocaleString()}冊から</span>
            {mixSize(narrow) > 0 && (
              <button type="button" className="cp-mix-clr" onClick={() => setNarrow(EMPTY_MIX)}>
                選び直す
              </button>
            )}
            <button type="button" className="cp-mix-x" aria-label="閉じる" onClick={() => setNarrowOpen(false)}>
              ✕
            </button>
          </div>
          <div className="cp-mix-body">
            {(["genres", "themes"] as const).map((part) => {
              const kind = part === "themes" ? "elem" : "genre";
              // 全部の本が持っている札(絞っても変わらない)は出さない。 選んだ札は残す
              const keys = [...narrowInfo[part].keys()].filter((k) => (narrowInfo[part].get(k) ?? 0) < narrowInfo.total);
              const shown = [...narrow[part], ...keys.sort((a, b) => (narrowInfo[part].get(b) ?? 0) - (narrowInfo[part].get(a) ?? 0))];
              if (!shown.length) return null;
              return (
                <div key={part}>
                  <div className="cp-mix-sec">{part === "themes" ? "要素" : "ジャンル"}</div>
                  <div className="cp-mix-tags">
                    {shown.map((k) => {
                      const on = narrow[part].includes(k);
                      const n = narrowInfo[part].get(k) ?? 0;
                      return (
                        <button
                          key={k}
                          type="button"
                          className={`cp-mt${on ? " on" : ""}`}
                          style={{ "--c": KIND_COLOR[kind] } as CSSProperties}
                          aria-pressed={on}
                          disabled={!on && n === 0}
                          onClick={() => toggleNarrow(part, k)}
                        >
                          {part === "genres" ? genreName(k) : k}
                          {!on && <i>→{n.toLocaleString()}</i>}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
          <button type="button" className="cp-mix-go cp-nar-go" disabled={mixSize(narrow) > 0 && !narrowInfo.total} onClick={applyNarrow}>
            {mixSize(narrow) ? (
              <>
                {[...narrow.themes, ...narrow.genres.map(genreName)].join(" × ")} <b>{narrowInfo.total.toLocaleString()}冊</b> に絞る
              </>
            ) : narrowApplied ? (
              "絞りを外す"
            ) : (
              "要素・ジャンルを選ぶ"
            )}
          </button>
        </div>
      )}

      {/* 4f. 案B「ほか ▸」= 輪に入らなかった要素・ジャンル(書影つきのタイル・押して重ねる) */}
      {THREADS && moreOpen && entrances && mixInfo && !unit && (
        <div className="cp-mix cp-more" style={{ bottom: Math.max(SHEET + 2, sheetH + 2) + BAND_H }} role="dialog" aria-label="残りの糸から重ねる">
          <div className="cp-mix-h">
            <span>残りの糸から重ねる</span>
            {mixSize(mix) > 0 && (
              <button type="button" className="cp-mix-clr" onClick={() => setMix(EMPTY_MIX)}>
                選び直す
              </button>
            )}
            <button type="button" className="cp-mix-x" aria-label="閉じる" onClick={() => setMoreOpen(false)}>
              ✕
            </button>
          </div>
          <div className="cp-mix-body">
            {(["elem", "genre"] as const).map((kind) => {
              const xs = entrances.more.filter((e) => e.kind === kind);
              if (!xs.length && kind === "elem") return null;
              const any = mixSize(mix) > 0;
              return (
                <div key={kind}>
                  <div className="cp-mix-sec cp-more-sec">
                    <span>{kind === "elem" ? `要素(輪に出ていない${xs.length})` : `ジャンル${xs.length ? `(輪に出ていない${xs.length})` : ""}`}</span>
                    {kind === "genre" && SPLIT && (
                      <button
                        type="button"
                        className="cp-more-re"
                        onClick={() => {
                          setMoreOpen(false);
                          setReOpen(true);
                        }}
                      >
                        ⇄ ジャンルを組み替える
                      </button>
                    )}
                  </div>
                  <div className="cp-tiles">
                    {xs.map((e) => {
                      if (e.kind !== "elem" && e.kind !== "genre") return null;
                      const part = e.kind === "elem" ? "themes" : "genres";
                      const on = mix[part].includes(e.value);
                      const cnt = mixInfo.c[part].get(e.value) ?? 0;
                      return (
                        <button
                          key={e.key}
                          type="button"
                          className={`cp-tile${on ? " on" : ""}`}
                          style={{ "--c": KIND_COLOR[e.kind] } as CSSProperties}
                          aria-pressed={on}
                          disabled={!on && any && cnt === 0}
                          onClick={() => toggleMix(part, e.value)}
                        >
                          {e.cover ? (
                            // eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク(images.unoptimized)
                            <img src={e.cover} alt="" className="bg-white" draggable={false} />
                          ) : (
                            <span className="cp-noimg" />
                          )}
                          <b>{e.value && e.kind === "genre" ? genreName(e.value) : e.value}</b>
                          {!on && <i>{any ? `→${cnt.toLocaleString()}` : cnt.toLocaleString()}</i>}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
          {mixSize(mix) > 0 && (
            <button type="button" className="cp-mix-go" style={{ "--c": KIND_COLOR[mix.themes.length ? "elem" : "genre"] } as CSSProperties} disabled={!mixInfo.c.total} onClick={applyMix}>
              {[...mix.themes, ...mix.genres.map(genreName)].join(" × ")} を広げる <b>{mixInfo.c.total.toLocaleString()}冊</b>
            </button>
          )}
        </div>
      )}

      {/* 5. シート */}
      <div
        ref={sheetRef}
        className={`cp-sheet${bump ? " bump" : ""}${goLabel && sel && shelveFor !== sheetItem?.slug ? " has-go" : ""}`}
        // ★札の色 = いま辿っている糸の色(何も選んでいない時は白)。 上端の太線・状態の小札・詳細・進むがこの1色(2026-10-03 案B3+D2)
        style={{ "--kc": unit ? unitColor(unit) : sheetKind ? KIND_COLOR[sheetKind] : "#e6ecf0" } as CSSProperties}
        aria-live="polite"
      >
        {/* 左の列 = 書影(押すと大きく)+その下に「詳細」(文章の欄を1行空けてキャッチを多く出す・2026-09-30) */}
        <div className="cp-sheet-left">
          {sheetItem?.cover ? (
            <button type="button" className="cp-sheet-cov" aria-label={`${sheetItem.title} の書影を大きく見る`} onClick={() => setBig(sheetItem.cover)}>
              {/* eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク(images.unoptimized) */}
              <img src={sheetItem.cover} alt="" className="bg-white" draggable={false} />
            </button>
          ) : (
            <span className="cp-noimg cp-sheet-noimg" />
          )}
          {sheetItem && (
            <a className="cp-detail" href={detailHref(sheetItem.slug)} onClick={saveResume}>
              詳細 ›
            </a>
          )}
        </div>
        <div className="cp-sheet-body">
          <div className="cp-sheet-head">
            <div className="cp-sheet-t">{sheetItem?.title ?? "羅針盤"}</div>
            {/* ★「しまう」= 本棚へ入れる。 本棚はまだテスト環境のみなので、本番では出さない(2026-10-03 ユーザ裁定) */}
            {PREVIEW && sheetItem && (
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
          {/* 状態 = 前半を糸の色の小札、「 ・ 」より後ろは灰色の補足(2026-10-03 案B3) */}
          <div className="cp-sheet-w">
            {(() => {
              const [head, ...rest] = (shelveMsg ?? why).split(" ・ ");
              return (
                <>
                  {head && <span className="cp-sheet-wt">{head}</span>}
                  {rest.length > 0 && <span className="cp-sheet-wr">{rest.join(" ・ ")}</span>}
                </>
              );
            })()}
          </div>
          {PREVIEW && sheetItem && shelveFor === sheetItem.slug ? (
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
      {KOMA && komaOpen && curItem && (
        <KomaPage
          item={curItem}
          magName={magName}
          genreName={genreName}
          demoName={demoName}
          href={detailHref(curItem.slug)}
          onDetail={saveResume}
          onClose={() => setKomaOpen(false)}
        />
      )}
      {big && (
        <button type="button" className="cp-big" aria-label="閉じる" onClick={() => setBig(null)}>
          {/* eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク(images.unoptimized) */}
          <img src={big.includes("thumbnail.image.rakuten.co.jp") ? big.replace(/\?_ex=\d+x\d+$/, "") + "?_ex=600x600" : big} alt="" className="bg-white" />
          <span>閉じる ✕</span>
        </button>
      )}
    </div>
  );
}
