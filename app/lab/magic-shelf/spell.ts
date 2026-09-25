import type { MangaListItem } from "@/lib/schema";
import { jaCollator } from "../../../lib/collator"; // 相対 = vitest(エイリアス設定なし)でも解決できる

/**
 * 魔法の書架(実験頁 /lab/magic-shelf)の「呪文」= 絞り込み条件の文字列。
 *
 * ★文字列が唯一の正本: チップを押しても呪文の文字列を書き換えるだけ(= コンソールに今の条件が
 *   そのまま見える・URL ?q= で共有できる)。ここは純関数だけ(DOM/React 無し)= テストで押さえる。
 * ★語の結合規則: ジャンル・題名語は「かつ」、年・巻数・状態は同じ種類どうし「または」
 *   (1980年代 と 1990年代 を両方押す = 1980〜1999)。先頭 - / ! は「除く」。
 */

export type Book = {
  slug: string;
  title: string;
  kana: string;
  cover: string | null;
  /** 連載開始年。不明(0/未設定)は null */
  year: number | null;
  /** 1巻の発売日(同年内の並びの決め手)。無ければ "" */
  first: string;
  /** 最大単一版の巻数(一覧表の「巻」と同じ = lib/listSort volCount) */
  vols: number;
  status: MangaListItem["status"];
  genres: string[];
  pop: number;
};

/** 索引 → 書架用の軽い形。slug 重複は先勝ち(view-transition-name が一意でないと遷移が壊れる)。 */
export function toBooks(items: MangaListItem[]): Book[] {
  const seen = new Set<string>();
  const out: Book[] = [];
  for (const m of items) {
    if (!m.slug || seen.has(m.slug)) continue;
    seen.add(m.slug);
    out.push({
      slug: m.slug,
      title: m.title,
      kana: m.title_kana ?? "",
      cover: m.cover ?? null,
      year: m.year_started > 0 ? m.year_started : null,
      first: m.first_volume_date ?? "",
      vols: m.max_edition_volumes ?? 0,
      status: m.status,
      genres: m.genres ?? [],
      pop: m.popularity ?? -1,
    });
  }
  return out;
}

// ─── 並び・集め ──────────────────────────────────────────────

export type SortId = "pop" | "old" | "new" | "vols" | "kana";
export type GroupId = "none" | "decade" | "status" | "vols";

export const SORTS: { id: SortId; token: string; label: string }[] = [
  { id: "pop", token: "人気順", label: "人気" },
  { id: "old", token: "古い順", label: "古い" },
  { id: "new", token: "新しい順", label: "新しい" },
  { id: "vols", token: "巻数順", label: "巻数" },
  { id: "kana", token: "50音順", label: "50音" },
];
export const GROUPS: { id: GroupId; token: string; label: string }[] = [
  { id: "none", token: "", label: "なし" },
  { id: "decade", token: "年代別", label: "年代" },
  { id: "status", token: "状態別", label: "完結/連載" },
  { id: "vols", token: "巻数別", label: "巻数帯" },
];
export const DEFAULT_SORT: SortId = "pop";

const SORT_ALIASES: Record<string, SortId> = {
  人気順: "pop", "sort:pop": "pop",
  古い順: "old", 年代順: "old", "sort:old": "old",
  新しい順: "new", 新着順: "new", "sort:new": "new",
  巻数順: "vols", 長い順: "vols", "sort:vols": "vols",
  "50音順": "kana", あいうえお順: "kana", "sort:kana": "kana",
};
const GROUP_ALIASES: Record<string, GroupId> = {
  年代別: "decade", "group:decade": "decade",
  状態別: "status", 完結別: "status", "group:status": "status",
  巻数別: "vols", "group:vols": "vols",
  集めない: "none", "group:none": "none",
};

// ─── 語の解釈 ────────────────────────────────────────────────

export type ClauseKind = "genre" | "year" | "vols" | "status" | "word";

export type Clause = {
  kind: ClauseKind;
  neg: boolean;
  /** 同じ意味の語は同じ key(= 90年代 と 1990年代)。チップの点灯/消灯はこれで照合する */
  key: string;
  label: string;
  test: (b: Book) => boolean;
};

export type Token =
  | { type: "clause"; clause: Clause }
  | { type: "sort"; sort: SortId }
  | { type: "group"; group: GroupId }
  | { type: "cmd"; cmd: "help" | "clear" };

export type Spell = {
  clauses: Clause[];
  sort: SortId;
  group: GroupId;
};

export type GenreDef = { key: string; name: string };

/** 入力の正規化(全角英数/全角空白/～ を半角へ・小文字化)。〜(波ダッシュ)は NFKC で残るので範囲記号として扱う。 */
export function normalizeInput(s: string): string {
  return s.normalize("NFKC").toLowerCase();
}

/** 語に割る(空白・全角空白・読点・カンマ)。正規化はしない = 入力欄の表記はそのまま残す(解釈は parseToken が正規化)。 */
export function splitTokens(text: string): string[] {
  return text.split(/[\s\u3000,，、]+/).filter(Boolean);
}

/** 題名照合用: 空白・中黒を落とし、カタカナ→ひらがな(題名ヨミはカタカナ、入力はひらがなでも当たる)。 */
export function foldForMatch(s: string): string {
  return normalizeInput(s)
    .replace(/[\s・･]/g, "")
    .replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60));
}

const RANGE = "[-~〜]";

function rangeClause(kind: "year" | "vols", min: number | null, max: number | null, label: string): Clause {
  const lo = min ?? -Infinity;
  const hi = max ?? Infinity;
  return {
    kind,
    neg: false,
    key: `${kind}:${min ?? ""}-${max ?? ""}`,
    label,
    test:
      kind === "year"
        ? (b) => b.year !== null && b.year >= lo && b.year <= hi
        : (b) => b.vols > 0 && b.vols >= lo && b.vols <= hi,
  };
}

function yearLabel(min: number | null, max: number | null): string {
  if (min !== null && max !== null && min === max) return `${min}年`;
  if (min !== null && max !== null && min % 10 === 0 && max === min + 9) return `${min}年代`;
  if (min !== null && max !== null) return `${min}〜${max}年`;
  if (min !== null) return `${min}年以降`;
  return `${max}年以前`;
}

function volsLabel(min: number | null, max: number | null): string {
  if (min !== null && max !== null && min === max) return `${min}巻`;
  if (min !== null && max !== null) return `${min}〜${max}巻`;
  if (min !== null) return `${min}巻以上`;
  return `${max}巻以下`;
}

function decadeStart(d: string): number | null {
  const n = Number(d);
  if (d.length === 2) return n % 10 === 0 ? (n >= 30 ? 1900 + n : 2000 + n) : null;
  return n % 10 === 0 && n >= 1900 && n < 2100 ? n : null;
}

function parseYear(t: string): Clause | null {
  let m: RegExpMatchArray | null;
  const mk = (a: number | null, b: number | null) => rangeClause("year", a, b, yearLabel(a, b));
  if ((m = t.match(/^(\d{2}|\d{4})(?:年代|s)$/))) {
    const s = decadeStart(m[1]);
    return s === null ? null : mk(s, s + 9);
  }
  const Y = "((?:19|20)\\d{2})";
  if ((m = t.match(new RegExp(`^${Y}年?$`)))) return mk(+m[1], +m[1]);
  if ((m = t.match(new RegExp(`^${Y}年?${RANGE}${Y}年?$`)))) {
    const a = +m[1], b = +m[2];
    return mk(Math.min(a, b), Math.max(a, b));
  }
  if ((m = t.match(new RegExp(`^${Y}(?:年?${RANGE}|年以降|年から)$`)))) return mk(+m[1], null);
  if ((m = t.match(new RegExp(`^(?:${RANGE}${Y}年?|${Y}年(?:以前|まで))$`)))) return mk(null, +(m[1] ?? m[2]));
  return null;
}

function parseVols(t: string): Clause | null {
  let m: RegExpMatchArray | null;
  const mk = (a: number | null, b: number | null) => rangeClause("vols", a, b, volsLabel(a, b));
  if ((m = t.match(/^全?(\d{1,4})巻$/))) return mk(+m[1], +m[1]);
  if ((m = t.match(new RegExp(`^(\\d{1,4})${RANGE}(\\d{1,4})巻$`)))) {
    const a = +m[1], b = +m[2];
    return mk(Math.min(a, b), Math.max(a, b));
  }
  if ((m = t.match(new RegExp(`^(\\d{1,4})(?:巻以上|${RANGE}巻|巻${RANGE})$`)))) return mk(+m[1], null);
  if ((m = t.match(new RegExp(`^(?:(\\d{1,4})巻(?:以下|まで)|${RANGE}(\\d{1,4})巻)$`)))) return mk(null, +(m[1] ?? m[2]));
  return null;
}

const STATUS_WORDS: Record<string, { s: Book["status"]; label: string }> = {
  完結: { s: "completed", label: "完結" },
  完結済: { s: "completed", label: "完結" },
  completed: { s: "completed", label: "完結" },
  連載中: { s: "ongoing", label: "連載中" },
  ongoing: { s: "ongoing", label: "連載中" },
  休載: { s: "hiatus", label: "休載中" },
  休載中: { s: "hiatus", label: "休載中" },
  hiatus: { s: "hiatus", label: "休載中" },
};

const HELP_WORDS = new Set(["?", "help", "ヘルプ", "呪文帳"]);
const CLEAR_WORDS = new Set(["clear", "消去", "リセット", "reset"]);

export type Spellbook = {
  parseToken: (raw: string) => Token | null;
  parse: (text: string) => Spell;
};

/** ジャンル辞書(data/genres.yml)を抱えた解釈器を作る。 */
export function makeSpellbook(genres: GenreDef[]): Spellbook {
  const genreByWord = new Map<string, GenreDef>();
  for (const g of genres) {
    genreByWord.set(normalizeInput(g.key), g);
    genreByWord.set(normalizeInput(g.name), g);
    const short = g.name.replace(/漫画$/, "");
    if (short && short !== g.name) genreByWord.set(normalizeInput(short), g);
  }

  function parsePositive(t: string): Clause | null {
    const g = genreByWord.get(t.replace(/^#/, ""));
    if (g) {
      const key = g.key;
      return { kind: "genre", neg: false, key: `genre:${key}`, label: g.name, test: (b) => b.genres.includes(key) };
    }
    const st = STATUS_WORDS[t];
    if (st) {
      const s = st.s;
      return { kind: "status", neg: false, key: `status:${s}`, label: st.label, test: (b) => b.status === s };
    }
    const y = parseYear(t);
    if (y) return y;
    const v = parseVols(t);
    if (v) return v;
    const needle = foldForMatch(t.replace(/^["「『]|["」』]$/g, ""));
    if (!needle) return null;
    return {
      kind: "word",
      neg: false,
      key: `word:${needle}`,
      label: `「${t}」`,
      test: (b) => hayOf(b).includes(needle),
    };
  }

  function parseToken(raw: string): Token | null {
    const t = normalizeInput(raw).trim();
    if (!t) return null;
    if (HELP_WORDS.has(t)) return { type: "cmd", cmd: "help" };
    if (CLEAR_WORDS.has(t)) return { type: "cmd", cmd: "clear" };
    if (t in SORT_ALIASES) return { type: "sort", sort: SORT_ALIASES[t] };
    if (t in GROUP_ALIASES) return { type: "group", group: GROUP_ALIASES[t] };
    const neg = /^[-!]/.test(t);
    const body = neg ? t.slice(1) : t;
    const c = parsePositive(body);
    if (!c) return null;
    if (!neg) return { type: "clause", clause: c };
    const inner = c.test;
    return { type: "clause", clause: { ...c, neg: true, label: `¬${c.label}`, test: (b) => !inner(b) } };
  }

  function parse(text: string): Spell {
    const spell: Spell = { clauses: [], sort: DEFAULT_SORT, group: "none" };
    for (const raw of splitTokens(text)) {
      const tok = parseToken(raw);
      if (!tok) continue;
      if (tok.type === "clause") spell.clauses.push(tok.clause);
      else if (tok.type === "sort") spell.sort = tok.sort;
      else if (tok.type === "group") spell.group = tok.group;
    }
    return spell;
  }

  return { parseToken, parse };
}

// 題名照合の下ごしらえ(本ごとに1回だけ)。本番 6.6万件でも最初の題名検索で一度払えば済む。
const _hay = new WeakMap<Book, string>();
function hayOf(b: Book): string {
  let h = _hay.get(b);
  if (h === undefined) {
    h = foldForMatch(b.title) + "\u0000" + foldForMatch(b.kana);
    _hay.set(b, h);
  }
  return h;
}

/** 呪文全体の合否判定: 否定語(test は反転済み)とジャンル・題名は「かつ」、年・巻数・状態は種類内「または」。 */
export function compileSpell(spell: Spell): (b: Book) => boolean {
  const ands = spell.clauses.filter((c) => c.neg || c.kind === "genre" || c.kind === "word").map((c) => c.test);
  const ors: ((b: Book) => boolean)[][] = [];
  for (const kind of ["year", "vols", "status"] as const) {
    const ts = spell.clauses.filter((c) => !c.neg && c.kind === kind).map((c) => c.test);
    if (ts.length) ors.push(ts);
  }
  return (b) => {
    for (const t of ands) if (!t(b)) return false;
    for (const group of ors) if (!group.some((t) => t(b))) return false;
    return true;
  };
}

// ─── 並べ替え(並び別に1回だけ作って使い回す = 呪文ごとの処理は O(n) の篩だけ) ─────────

function byKana(a: Book, b: Book): number {
  return jaCollator.compare(a.kana || a.title, b.kana || b.title);
}
const COMPARE: Record<SortId, (a: Book, b: Book) => number> = {
  pop: (a, b) => b.pop - a.pop || byKana(a, b),
  old: (a, b) =>
    (a.year ?? 9999) - (b.year ?? 9999) || (a.first || "9").localeCompare(b.first || "9") || byKana(a, b),
  new: (a, b) => (b.year ?? 0) - (a.year ?? 0) || b.first.localeCompare(a.first) || byKana(a, b),
  vols: (a, b) => b.vols - a.vols || b.pop - a.pop || byKana(a, b),
  kana: byKana,
};

const _sorted = new WeakMap<Book[], Map<SortId, Book[]>>();
export function sortedBooks(books: Book[], sort: SortId): Book[] {
  let m = _sorted.get(books);
  if (!m) _sorted.set(books, (m = new Map()));
  let s = m.get(sort);
  if (!s) m.set(sort, (s = [...books].sort(COMPARE[sort])));
  return s;
}

// ─── 集め(棚分け) ─────────────────────────────────────────────

const VOL_BANDS: { max: number; key: string; label: string }[] = [
  { max: 1, key: "v1", label: "1巻もの" },
  { max: 5, key: "v2", label: "2〜5巻" },
  { max: 20, key: "v6", label: "6〜20巻" },
  { max: 50, key: "v21", label: "21〜50巻" },
  { max: Infinity, key: "v51", label: "51巻以上" },
];
const STATUS_ORDER: Record<string, { rank: number; label: string }> = {
  ongoing: { rank: 0, label: "連載中" },
  completed: { rank: 1, label: "完結" },
  hiatus: { rank: 2, label: "休載中" },
};

type GroupSlot = { key: string; label: string; rank: number };

export function groupOf(b: Book, group: GroupId, sort: SortId): GroupSlot {
  switch (group) {
    case "decade": {
      if (b.year === null) return { key: "d?", label: "年不明", rank: 1e9 };
      const d = Math.floor(b.year / 10) * 10;
      return { key: `d${d}`, label: `${d}年代`, rank: sort === "new" ? -d : d };
    }
    case "status": {
      const s = STATUS_ORDER[b.status] ?? { rank: 9, label: "不明" };
      return { key: `s-${b.status}`, label: s.label, rank: s.rank };
    }
    case "vols": {
      if (b.vols <= 0) return { key: "v?", label: "巻数不明", rank: 1e9 };
      const i = VOL_BANDS.findIndex((x) => b.vols <= x.max);
      return { key: VOL_BANDS[i].key, label: VOL_BANDS[i].label, rank: sort === "vols" ? -i : i };
    }
    default:
      return { key: "all", label: "", rank: 0 };
  }
}

export type ShelfGroup = { key: string; label: string; total: number; books: Book[] };
export type CastResult = { matched: number; groups: ShelfGroup[] };

/**
 * 呪文を唱える = 篩って並べて棚分け。各棚は cap 冊まで(残りは total で数えるだけ)。
 * 描画する本を絞るのは view transition の撮影枚数を抑えるため(スマホで重くしない)。
 */
export function castSpell(
  books: Book[],
  spell: Spell,
  capOf: (groupKey: string) => number,
): CastResult {
  const pass = compileSpell(spell);
  const slots = new Map<string, ShelfGroup & { rank: number }>();
  let matched = 0;
  for (const b of sortedBooks(books, spell.sort)) {
    if (!pass(b)) continue;
    matched++;
    const g = groupOf(b, spell.group, spell.sort);
    let slot = slots.get(g.key);
    if (!slot) slots.set(g.key, (slot = { key: g.key, label: g.label, rank: g.rank, total: 0, books: [] }));
    slot.total++;
    if (slot.books.length < capOf(g.key)) slot.books.push(b);
  }
  const groups = [...slots.values()].sort((a, b) => a.rank - b.rank).map(({ rank: _r, ...g }) => g);
  return { matched, groups };
}

// ─── 呪文文字列の編集(チップ操作) ──────────────────────────────

/** key を持つ肯定語をすべて抜く(90年代 と 1990年代 のように書き方が違っても同じ key なら抜ける)。 */
export function removeClauseKey(text: string, key: string, book: Spellbook): string {
  return splitTokens(text)
    .filter((t) => {
      const tok = book.parseToken(t);
      return !(tok?.type === "clause" && !tok.clause.neg && tok.clause.key === key);
    })
    .join(" ");
}

/** チップの on/off: 点いていれば同じ key の語を全部抜く、消えていれば token を末尾に足す。 */
export function toggleClause(text: string, token: string, book: Spellbook): string {
  const tok = book.parseToken(token);
  if (tok?.type !== "clause") return text;
  const key = tok.clause.key;
  const has = book.parse(text).clauses.some((c) => !c.neg && c.key === key);
  if (has) return removeClauseKey(text, key, book);
  return [...splitTokens(text), token].join(" ");
}

/** 並び/集めは1つだけ: 同種の語を全部抜いてから(既定値でなければ)足す。 */
export function setExclusive(text: string, type: "sort" | "group", token: string, book: Spellbook): string {
  const kept = splitTokens(text).filter((t) => book.parseToken(t)?.type !== type);
  if (token) kept.push(token);
  return kept.join(" ");
}

/** コンソールに出す解釈文(条件の要約)。「かつ」=∧ / 種類内の「または」=∨ で結合規則をそのまま見せる。 */
export function describeSpell(spell: Spell): string {
  const pos = spell.clauses.filter((c) => !c.neg);
  const parts = pos.filter((c) => c.kind === "genre" || c.kind === "word").map((c) => c.label);
  for (const kind of ["year", "vols", "status"] as const) {
    const ls = pos.filter((c) => c.kind === kind).map((c) => c.label);
    if (ls.length) parts.push(ls.length > 1 ? `(${ls.join(" ∨ ")})` : ls[0]);
  }
  parts.push(...spell.clauses.filter((c) => c.neg).map((c) => c.label));
  const cond = parts.length ? parts.join(" ∧ ") : "(条件なし = 全冊)";
  const sort = SORTS.find((s) => s.id === spell.sort)!.token;
  const group = spell.group === "none" ? "" : ` ／ ${GROUPS.find((g) => g.id === spell.group)!.token}`;
  return `${cond} ／ ${sort}${group}`;
}
