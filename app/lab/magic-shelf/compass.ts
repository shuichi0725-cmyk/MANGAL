// ★魔法の書架 = 旅路つき羅針盤 の純関数 (依頼書 docs/cloud-briefs/magic-shelf-compass.md)。
//   つながりの計算・広げる単位・4つの広げ方の座標・網点の出方の順番 v をここに集め、
//   compass.test.ts で固定する。 DOM/React に触らない(vitest で素のまま読めるよう相対 import のみ)。
import type { MangaListItem } from "../../../lib/schema";

export type Kind = "author" | "mag" | "year" | "elem";
export type ThreadKind = Kind | "back";

export const KINDS: readonly Kind[] = ["author", "mag", "year", "elem"];

export const KIND_COLOR: Record<ThreadKind, string> = {
  author: "#f2c14e",
  mag: "#4fc28e",
  year: "#c792ff",
  elem: "#6ea8ff",
  back: "#8a96a0",
};

export const KIND_NAME: Record<ThreadKind, string> = {
  author: "作者",
  mag: "同じ雑誌",
  year: "同じ年",
  elem: "要素",
  back: "来た道",
};

/** 周りの本の方角(度・0=東・時計回り)。 作者の2冊目は上限1のため使わないが、試作の枠として残す。 */
export const RING_ANGLES: Record<Kind, readonly number[]> = {
  author: [-90, -70],
  mag: [-20, 20],
  year: [70, 110],
  elem: [160, 200],
};
export const RING_CAP: Record<Kind, number> = {
  author: 1,
  mag: 2,
  year: 2,
  elem: 2,
};
export const UNIT_MAX = 24;
export const ELEM_POP_MIN = 3000;

// ───────────────────────── 逆引き表 ─────────────────────────

/** 索引が届いた時に1回だけ作る逆引き表。 対象(items)は書影とキャッチがある作品だけ。 */
export type Graph = {
  items: MangaListItem[];
  /** 全作品(対象外も)。 中央・来た道の本を引くため。 */
  all: Map<string, MangaListItem>;
  byAuthor: Map<string, number[]>;
  byMag: Map<string, number[]>;
  byYear: Map<number, number[]>;
  byTheme: Map<string, number[]>;
};

function uniq<T>(xs: readonly T[]): T[] {
  return [...new Set(xs)];
}

/** authors の名前部分(重複・空を除く)。 original_authors は数えない(依頼書どおり)。 */
export function authorNames(m: Pick<MangaListItem, "authors">): string[] {
  return uniq(
    (m.authors ?? []).map((a) => (a?.name ?? "").trim()).filter(Boolean),
  );
}

function push<K>(map: Map<K, number[]>, k: K, i: number): void {
  const a = map.get(k);
  if (a) a.push(i);
  else map.set(k, [i]);
}

export function isEligible(m: MangaListItem): boolean {
  return !!m.cover && !!m.catch;
}

export function buildGraph(list: readonly MangaListItem[]): Graph {
  const g: Graph = {
    items: [],
    all: new Map(),
    byAuthor: new Map(),
    byMag: new Map(),
    byYear: new Map(),
    byTheme: new Map(),
  };
  for (const m of list) {
    g.all.set(m.slug, m);
    if (!isEligible(m)) continue;
    const i = g.items.length;
    g.items.push(m);
    for (const n of authorNames(m)) push(g.byAuthor, n, i);
    if (m.magazine) push(g.byMag, m.magazine, i);
    if (m.year_started) push(g.byYear, m.year_started, i);
    for (const t of uniq(m.themes ?? [])) push(g.byTheme, t, i);
  }
  return g;
}

// ───────────────────────── 中央ごとの計算(周り+広げる単位を1回で) ─────────────────────────

export type RingEntry = {
  slug: string;
  kind: Kind;
  label: string;
  shared: number;
};
export type UnitItem = { slug: string; shared: number; year: number | null };
export type Unit = {
  key: string;
  kind: Kind;
  label: string;
  items: UnitItem[];
};
export type Neighborhood = { ring: RingEntry[]; units: Unit[] };

export function neighborhood(
  g: Graph,
  center: MangaListItem,
  magName: (key: string) => string = (k) => k,
): Neighborhood {
  const self = center.slug;
  const cThemes = uniq(center.themes ?? []);
  const shared = new Map<number, number>();
  for (const t of cThemes)
    for (const i of g.byTheme.get(t) ?? [])
      shared.set(i, (shared.get(i) ?? 0) + 1);
  const sh = (i: number) => shared.get(i) ?? 0;
  const pop = (i: number) => g.items[i].popularity ?? 0;
  // 並び順 = 共通の要素の数(多い順)→ popularity(多い順)。 同点は slug で固定(毎回同じ並び)。
  const cmp = (a: number, b: number) =>
    sh(b) - sh(a) ||
    pop(b) - pop(a) ||
    (g.items[a].slug < g.items[b].slug
      ? -1
      : g.items[a].slug > g.items[b].slug
        ? 1
        : 0);
  const notSelf = (i: number) => g.items[i].slug !== self;
  const sharedThemes = (i: number) => {
    const ts = new Set(g.items[i].themes ?? []);
    return cThemes.filter((t) => ts.has(t));
  };

  const names = authorNames(center);
  const authorSet = new Set<number>();
  for (const n of names)
    for (const i of g.byAuthor.get(n) ?? []) if (notSelf(i)) authorSet.add(i);
  const magList = center.magazine
    ? (g.byMag.get(center.magazine) ?? []).filter(notSelf)
    : [];
  const yearList = center.year_started
    ? (g.byYear.get(center.year_started) ?? []).filter(notSelf)
    : [];

  // ── 周りの本: 1冊は最初に当てはまった種類1つにだけ入る(作者 > 同じ雑誌 > 同じ年 > 要素) ──
  const taken = new Set<number>();
  const ring: RingEntry[] = [];
  // 各種類 上限+1冊まで持つ(+1 = 前の中央がその枠にいた時の控え。 上限は placeRing で掛ける)
  const take = (cands: number[], kind: Kind, label: (i: number) => string) => {
    cands.sort(cmp);
    for (const i of cands) taken.add(i);
    for (const i of cands.slice(0, RING_CAP[kind] + 1))
      ring.push({
        slug: g.items[i].slug,
        kind,
        label: label(i),
        shared: sh(i),
      });
  };
  take([...authorSet], "author", (i) => {
    const theirs = new Set(authorNames(g.items[i]));
    return `作者 ${names.find((n) => theirs.has(n)) ?? names[0]}`;
  });
  take(
    magList.filter((i) => !taken.has(i) && sh(i) >= 2),
    "mag",
    () => magName(center.magazine as string),
  );
  take(
    yearList.filter((i) => !taken.has(i) && sh(i) >= 2),
    "year",
    () => `${center.year_started}年に開始`,
  );
  take(
    [...shared.keys()].filter(
      (i) => notSelf(i) && !taken.has(i) && sh(i) >= 3 && pop(i) > ELEM_POP_MIN,
    ),
    "elem",
    (i) => sharedThemes(i).slice(0, 2).join("・"),
  );

  // ── 広げる単位(各最大24冊・並び順は同じ) ──
  const units: Unit[] = [];
  const unit = (key: string, kind: Kind, label: string, cands: number[]) => {
    const items = cands
      .sort(cmp)
      .slice(0, UNIT_MAX)
      .map((i) => ({
        slug: g.items[i].slug,
        shared: sh(i),
        year: g.items[i].year_started || null,
      }));
    if (items.length) units.push({ key, kind, label, items });
  };
  for (const n of names)
    unit(`author:${n}`, "author", n, (g.byAuthor.get(n) ?? []).filter(notSelf));
  if (center.magazine)
    unit(
      `mag:${center.magazine}`,
      "mag",
      magName(center.magazine),
      magList.filter((i) => sh(i) >= 1),
    );
  if (center.year_started)
    unit(
      `year:${center.year_started}`,
      "year",
      `${center.year_started}年`,
      yearList.filter((i) => sh(i) >= 1),
    );
  const topThemes = [...cThemes]
    .sort(
      (a, b) =>
        (g.byTheme.get(b)?.length ?? 0) - (g.byTheme.get(a)?.length ?? 0),
    )
    .slice(0, 4);
  for (const t of topThemes)
    unit(`elem:${t}`, "elem", t, (g.byTheme.get(t) ?? []).filter(notSelf));

  return { ring, units };
}

// ───────────────────────── 羅針盤の配置 ─────────────────────────

export type Geom = {
  /** 羅針盤の舞台(旅路の下〜シートの上)の幅・高さ */
  W: number;
  H: number;
  CX: number;
  CY: number;
  /** 周りの本の楕円 */
  rx: number;
  ry: number;
  /** 舞台の上端に取る「広げ方」切替の帯 / 下端の「広げる ▸」帯 */
  top: number;
  bottom: number;
};

export function stageGeom(W: number, H: number): Geom {
  const CX = W / 2;
  const CY = H / 2;
  return {
    W,
    H,
    CX,
    CY,
    rx: Math.max(80, Math.min(128, CX - 40)),
    ry: Math.max(80, Math.min(165, CY - 100)),
    top: 34,
    bottom: 32,
  };
}

/** 2つの角度(度)の差 0..180。 */
export function angleGap(a: number, b: number): number {
  return Math.abs(((((a - b) % 360) + 540) % 360) - 180);
}

/** b から見た a の向き(度・-180..180)。 */
function angleDelta(a: number, b: number): number {
  return ((((a - b) % 360) + 540) % 360) - 180;
}

/** 本どうしが重なって見える距離(横=本の幅+α・縦=本の高さ+ラベル少し) */
export const RING_GAP = { w: 62, h: 88 };
/** 重なりをよける時、周りの本が自分の方角から動いてよい角度 */
const RING_MAX_SHIFT = 45;

export type RingPlaced = {
  slug: string;
  kind: ThreadKind;
  label: string;
  shared: number;
  ang: number;
  dx: number;
  dy: number;
  back: boolean;
};

/** 周りの本の置き場所(中央からの相対座標)。
 *  ★前の中央(prev)は「来た方向の反対側」(= すべり終えた位置)に来た道として残す。
 *   前の中央が周りの本の条件にも当てはまる時(作者の糸で来た時はほぼ必ず)でもその枠は使わず、
 *   枠は同じ種類の次の本で埋める(=試作のように来た道が中央を突っ切って北へ戻る動きをさせない)。
 *   来た道と周りの本が重なる時は、周りの本の方を自分の方角から少し(最大45°)ずらしてよける。 */
export function placeRing(
  ring: readonly RingEntry[],
  prev: string | null,
  backAng: number | null,
  rx: number,
  ry: number,
): RingPlaced[] {
  const used: Record<Kind, number> = { author: 0, mag: 0, year: 0, elem: 0 };
  const out: RingPlaced[] = [];
  const base: number[] = [];
  for (const e of ring) {
    if (e.slug === prev || used[e.kind] >= RING_CAP[e.kind]) continue;
    const a = RING_ANGLES[e.kind][used[e.kind]++];
    out.push({ ...e, ang: a, dx: 0, dy: 0, back: false });
    base.push(a);
  }
  if (prev) {
    out.push({
      slug: prev,
      kind: "back",
      label: "来た道",
      shared: 0,
      ang: backAng ?? 135,
      dx: 0,
      dy: 0,
      back: true,
    });
    base.push(backAng ?? 135);
  }
  const pos = (a: number): [number, number] => {
    const t = (a * Math.PI) / 180;
    return [rx * Math.cos(t), ry * Math.sin(t)];
  };
  const hit = (a: number, b: number) => {
    const [ax, ay] = pos(a);
    const [bx, by] = pos(b);
    return Math.abs(ax - bx) < RING_GAP.w && Math.abs(ay - by) < RING_GAP.h;
  };
  // 重なりをほどく(来た道は動かさない・周りの本は自分の方角から RING_MAX_SHIFT まで)
  for (let it = 0; it < 80; it++) {
    let moved = false;
    for (let i = 0; i < out.length; i++)
      for (let j = i + 1; j < out.length; j++) {
        if (!hit(out[i].ang, out[j].ang)) continue;
        const d = angleDelta(out[j].ang, out[i].ang);
        const dir = d > 0 || (d === 0 && j > i) ? 1 : -1;
        for (const [k, sgn] of [
          [i, -dir],
          [j, dir],
        ] as const) {
          if (out[k].back) continue;
          const next = out[k].ang + sgn * 2;
          if (Math.abs(angleDelta(next, base[k])) <= RING_MAX_SHIFT) {
            out[k].ang = next;
            moved = true;
          }
        }
      }
    if (!moved) break;
  }
  for (const o of out) [o.dx, o.dy] = pos(o.ang);
  return out;
}

// ───────────────────────── 糸を広げる: 4つの広げ方 ─────────────────────────

export type Spread = "fan" | "ring" | "time" | "dust";
export const SPREADS: readonly { key: Spread; name: string }[] = [
  { key: "fan", name: "方角に扇" },
  { key: "ring", name: "同心円" },
  { key: "time", name: "年表" },
  { key: "dust", name: "星屑" },
];

/** ★同じ年の糸では年表を選べない(全部同じ年=1列に潰れて7冊しか出ない)。 */
export function allowedSpreads(kind: Kind): Spread[] {
  return SPREADS.map((s) => s.key).filter(
    (k) => !(kind === "year" && k === "time"),
  );
}

export function defaultSpread(kind: Kind): Spread {
  return kind === "year" ? "ring" : kind === "elem" ? "fan" : "time";
}

/** 端末に覚えた広げ方(不正・使えない値なら既定)。 */
export function resolveSpread(kind: Kind, stored: unknown): Spread {
  return typeof stored === "string" &&
    (allowedSpreads(kind) as string[]).includes(stored)
    ? (stored as Spread)
    : defaultSpread(kind);
}

export type Box = { x: number; y: number; w: number; h: number };
export type SpreadResult = {
  P: (Box & { slug: string })[];
  center: Box;
  ticks?: { year: number; x: number }[];
  axisY?: number;
};

// ★2026-09-29 ユーザ「全体的に画像を大きく」= 約1.25倍(旧 34×48 / 30×42 / 26×36・中央 60×84)
const SZ: readonly [number, number][] = [
  [44, 62],
  [38, 54],
  [33, 46],
];
/** 広げている間の中央の本 */
export const SPREAD_CENTER = { w: 72, h: 100 };
const DIR: Record<Kind, number> = { author: -90, mag: 0, year: 90, elem: 180 };

/** 決まった種の乱数(試作と同じ式)。 */
export function rng(seed: string): () => number {
  let a = 0;
  for (const c of seed) a = (a * 31 + c.charCodeAt(0)) | 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** 広げた本の座標(舞台の座標)。 items は近い順(共通の要素が多い順)。 */
export function spreadPositions(
  kind: Kind,
  items: readonly { slug: string; year: number | null }[],
  spread: Spread,
  geom: Geom,
  centerYear: number | null,
  seedKey: string,
): SpreadResult {
  const { W, H, CX, CY, top, bottom } = geom;
  const P: SpreadResult["P"] = [];
  const midCenter: Box = { x: CX, y: CY, ...SPREAD_CENTER };
  if (spread === "time" && kind === "year") spread = defaultSpread(kind);

  if (spread === "fan" || spread === "ring") {
    // ★2026-09-29 書影を大きくしたら固定座標(弧ごとの冊数を決め打ち)では重なった(旧も扇で6〜10か所重なっていた)。
    //   → 近い本から順に、内側の弧から外へ「重ならず・画面からはみ出さない」最初の場所へ置く。
    //   扇 = 糸の方角を真ん中に左右交互に探す(方角のまわりに寄る)/ 同心円 = 真上から時計回り。
    const fx = Math.min(0.85, (CX - 26) / 200);
    const fy = Math.max(
      0.6,
      Math.min(1.1, (CY - top - 32) / 200, (H - bottom - CY - 32) / 200),
    );
    const yMin = top + 4;
    const yMax = H - bottom - 6;
    const GAP = 5;
    const free = (x: number, y: number, w: number, h: number) =>
      x - w / 2 >= 4 &&
      x + w / 2 <= W - 4 &&
      y - h / 2 >= yMin &&
      y + h / 2 <= yMax &&
      !(
        Math.abs(x - CX) < (SPREAD_CENTER.w + w) / 2 + GAP &&
        Math.abs(y - CY) < (SPREAD_CENTER.h + h) / 2 + GAP
      ) &&
      !P.some(
        (q) =>
          Math.abs(q.x - x) < (q.w + w) / 2 + GAP &&
          Math.abs(q.y - y) < (q.h + h) / 2 + GAP,
      );
    // 扇は2段: まず方角の左右80°の中だけで詰め、入りきらなければ残りを方角から遠い側(80〜180°)へ続けて置く
    //   (大きな書影で半面の扇に24冊は入らない=360×504で14冊止まりだった)。
    const phases: number[][] = [];
    if (spread === "fan") {
      const near = [DIR[kind]];
      for (let d = 3; d <= 80; d += 3) near.push(DIR[kind] - d, DIR[kind] + d);
      const far: number[] = [];
      for (let d = 83; d <= 180; d += 3) far.push(DIR[kind] - d, DIR[kind] + d);
      phases.push(near, far);
    } else {
      const all: number[] = [];
      for (let d = 0; d < 360; d += 3) all.push(-90 + d);
      phases.push(all);
    }
    let k = 0;
    for (const AS of phases) {
      let R = 96;
      while (k < items.length && R <= 330) {
        const [w, h] = SZ[k < 8 ? 0 : k < 16 ? 1 : 2];
        let placedAny = false;
        for (const a of AS) {
          if (k >= items.length) break;
          const t = (a * Math.PI) / 180;
          const x = CX + R * fx * Math.cos(t);
          const y = CY + R * fy * Math.sin(t);
          const [ww, hh] = SZ[k < 8 ? 0 : k < 16 ? 1 : 2];
          if (!free(x, y, ww, hh)) continue;
          P.push({ slug: items[k].slug, x, y, w: ww, h: hh });
          k++;
          placedAny = true;
        }
        R += placedAny ? Math.max(w, h) * 0.55 : 12;
      }
    }
    return { P, center: midCenter };
  }

  if (spread === "dust") {
    const r = rng(seedKey);
    const bands = [
      [90, 132],
      [132, 170],
      [170, 215],
    ];
    const yMin = top + 4;
    const yMax = H - bottom - 6;
    items.forEach((it, i) => {
      const b = i < 8 ? 0 : i < 16 ? 1 : 2;
      const [w, h] = SZ[b];
      for (let tries = 0; tries < 300; tries++) {
        const a = r() * Math.PI * 2;
        const rr = bands[b][0] + r() * (bands[b][1] - bands[b][0]);
        const px = CX + rr * 0.82 * Math.cos(a);
        const py = CY + rr * 1.12 * Math.sin(a);
        if (
          px - w / 2 < 4 ||
          px + w / 2 > W - 4 ||
          py - h / 2 < yMin ||
          py + h / 2 > yMax
        )
          continue;
        if (
          P.some(
            (q) =>
              Math.abs(q.x - px) < (q.w + w) / 2 + 4 &&
              Math.abs(q.y - py) < (q.h + h) / 2 + 4,
          )
        )
          continue;
        // 中央の本(60×84)とも重ねない
        if (
          Math.abs(px - CX) < (SPREAD_CENTER.w + w) / 2 + 4 &&
          Math.abs(py - CY) < (SPREAD_CENTER.h + h) / 2 + 4
        )
          continue;
        P.push({ slug: it.slug, x: px, y: py, w, h });
        break;
      }
    });
    return { P, center: midCenter };
  }

  // 年表: 横軸 = year_started(左が古い)・同じ列は下から積む(下ほど近い)
  const ys = items
    .map((x) => x.year)
    .concat([centerYear])
    .filter((y): y is number => !!y);
  const lo = ys.length ? Math.min(...ys) : 0;
  const hi = ys.length ? Math.max(...ys) : 0;
  const span = W - 48;
  const X = (y: number) => 24 + (hi === lo ? 0.5 : (y - lo) / (hi - lo)) * span;
  const axisY = H - 64;
  const base = axisY - 28;
  const center: Box = {
    x: centerYear ? X(centerYear) : CX,
    y: top + 46,
    w: 54,
    h: 76,
  };
  const maxRows = Math.max(
    1,
    Math.min(
      7,
      Math.floor((base - 24 - (center.y + center.h / 2 + 8)) / 56) + 1,
    ),
  );
  const maxCol = Math.floor(span / 37);
  const cols = new Map<number, number>();
  for (const it of items) {
    if (!it.year) continue;
    const c = Math.min(maxCol, Math.round((X(it.year) - 24) / 37));
    const n = cols.get(c) ?? 0;
    cols.set(c, n + 1);
    if (n >= maxRows) continue;
    P.push({ slug: it.slug, x: 24 + c * 37, y: base - n * 56, w: 34, h: 48 });
  }
  const ticks: { year: number; x: number }[] = [];
  if (ys.length) {
    const step = Math.max(1, Math.ceil((hi - lo) / 5));
    for (let y = lo; y <= hi; y += step) ticks.push({ year: y, x: X(y) });
  }
  return { P, center, ticks, axisY };
}

// ───────────────────────── 網点の出方 ─────────────────────────

export type ToneKey =
  | "inner"
  | "outer"
  | "outerSpin"
  | "innerSpin"
  | "scatter"
  | "radar"
  | "radarCcw"
  | "diagonal"
  | "diagTR"
  | "diagBL"
  | "diagBR";

export const TONES: readonly { key: ToneKey; name: string }[] = [
  { key: "inner", name: "内周から" },
  { key: "outer", name: "外周から" },
  { key: "outerSpin", name: "外周から回る" },
  { key: "innerSpin", name: "内周から回る" },
  { key: "scatter", name: "ばらばら" },
  { key: "radar", name: "時計回り" },
  { key: "radarCcw", name: "反時計回り" },
  { key: "diagonal", name: "左上から" },
  { key: "diagTR", name: "右上から" },
  { key: "diagBL", name: "左下から" },
  { key: "diagBR", name: "右下から" },
];

export const TONE_STEP = 6;
export const TONE_R = 2.35;
export const TONE_MS = 1000;
/** 1つの点が入れ替わるのにかかる時間(全体に対する割合) */
export const TONE_SPAN = 0.32;

/** 各点が入れ替わり始める順番 v (0..1)。 cx,cy = 羅針盤の中央(点の列・行の単位)。 */
export function toneOrder(
  key: ToneKey,
  W: number,
  H: number,
  cx: number,
  cy: number,
  rand: () => number = Math.random,
): Float32Array {
  const o = new Float32Array(W * H);
  let maxD = 0;
  for (const [i, j] of [
    [0, 0],
    [W - 1, 0],
    [0, H - 1],
    [W - 1, H - 1],
  ])
    maxD = Math.max(maxD, Math.hypot(i - cx, j - cy));
  maxD = maxD || 1;
  const TAU = Math.PI * 2;
  for (let j = 0; j < H; j++)
    for (let i = 0; i < W; i++) {
      const d = Math.min(1, Math.hypot(i - cx, j - cy) / maxD);
      // 真上を0として時計回り(画面は y が下向きなので atan2 の角度がそのまま時計回り)
      const a =
        (((Math.atan2(j - cy, i - cx) + Math.PI / 2 + TAU * 2) % TAU) / TAU) %
        1;
      let v: number;
      switch (key) {
        case "inner":
          v = d;
          break;
        case "outer":
          v = 1 - d;
          break;
        case "outerSpin":
          v = ((1 - d) * 3 + a) / 4;
          break;
        case "innerSpin":
          v = (d * 3 + a) / 4;
          break;
        case "scatter":
          v = rand();
          break;
        case "radar":
          v = a;
          break;
        case "radarCcw":
          v = a === 0 ? 0 : 1 - a;
          break;
        case "diagTR":
          v = ((W - 1 - i) / W + j / H) / 2;
          break;
        case "diagBL":
          v = (i / W + (H - 1 - j) / H) / 2;
          break;
        case "diagBR":
          v = ((W - 1 - i) / W + (H - 1 - j) / H) / 2;
          break;
        default:
          v = (i / W + j / H) / 2; // 左上から
      }
      o[j * W + i] = Math.min(1, Math.max(0, v));
    }
  return o;
}

/** 点 k の進み q(0..1・なめらかな加減速)。 p = 全体の進み、v = その点の順番。 */
export function toneQ(p: number, v: number): number {
  let q = (p - v * (1 - TONE_SPAN)) / TONE_SPAN;
  q = q < 0 ? 0 : q > 1 ? 1 : q;
  return q * q * (3 - 2 * q);
}

/** 出方をランダムに1つ(同じ出方を2回続けない)。 */
export function pickTone(
  last: ToneKey | null,
  rand: () => number = Math.random,
): ToneKey {
  const ks = TONES.map((t) => t.key).filter((k) => k !== last);
  return ks[Math.min(ks.length - 1, Math.floor(rand() * ks.length))];
}

export function toneName(key: ToneKey): string {
  return TONES.find((t) => t.key === key)?.name ?? key;
}
