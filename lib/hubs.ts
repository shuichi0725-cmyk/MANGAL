import { loadListBundle } from "./loadData";
import type { MangaListItem } from "./schema";

/**
 * ★ハブ面(2026-09-04 SEO): 雑誌別 / 出版社別 / 連載開始年別 の静的一覧と、ジャンル×(完結/年代)の下位面。
 *
 * 目的:
 *  (1) 「週刊少年ジャンプ 連載作品 一覧」「2005年 漫画」「完結済み ファンタジー漫画」型の検索語に着地面を作る。
 *  (2) 作品頁66k枚へ静的な内部リンクを張る(= 孤児頁の発見経路)。年別は「年を持つ全作品」を必ず載せる。
 *
 * 源 = 一覧索引(loadListBundle)。 閾値(HUB_MIN)未満のキーは頁を作らない(= 薄い頁を撒かない)。
 * 頁割り = HUB_PAGE_SIZE 件ずつ(/magazine/<key> が1頁目、/magazine/<key>/2 以降が続き)。
 * ★sitemap は build 成果物 out/ の実在HTMLから拾う(scripts/_gen-sitemap.py)ので、ここの閾値を Python に
 *   二重実装しない(= titles-pages と同じ「単一ソース」原則)。
 * ★作品頁のチップ(出版社/連載誌/出版年)は hubHrefIfExists で「頁が在る時だけ」ハブへ向ける。
 */

export type HubKind = "magazine" | "publisher" | "year";
export const HUB_PAGE_SIZE = 300;
export const HUB_MIN: Record<HubKind, number> = { magazine: 3, publisher: 50, year: 5 };
export const HUB_LABEL: Record<HubKind, string> = {
  magazine: "雑誌別",
  publisher: "出版社別",
  year: "連載開始年別",
};

export type HubDef = {
  kind: HubKind;
  key: string;
  name: string;
  count: number;
  completed: number;
  pages: number;
  /** magazine → 出版社key */
  publisher?: string;
  /** magazine → 分野key */
  demographic?: string;
};

type HubIndex = {
  defs: HubDef[];
  byKey: Map<string, HubDef>;
  items: Map<string, MangaListItem[]>;
};

const _hub: Partial<Record<HubKind, HubIndex>> = {};
const coll = new Intl.Collator("ja");

export function pop(m: MangaListItem): number {
  return m.popularity ?? 0;
}

/** 人気順(AniList popularity → score → ヨミ)。 ジャンル面と同じ規則 */
export function byPopularity(a: MangaListItem, b: MangaListItem): number {
  return (
    pop(b) - pop(a) ||
    (b.score ?? 0) - (a.score ?? 0) ||
    coll.compare(a.title_kana || a.title, b.title_kana || b.title)
  );
}

/** 連載開始年順(雑誌面 = 連載史として読める並び) */
export function byYearStarted(a: MangaListItem, b: MangaListItem): number {
  return (a.year_started || 9999) - (b.year_started || 9999) || byPopularity(a, b);
}

function keyOf(kind: HubKind, m: MangaListItem): string | null {
  if (kind === "magazine") return m.magazine || null;
  if (kind === "publisher") return m.publisher || null;
  return m.year_started > 0 ? String(m.year_started) : null;
}

export function hubIndex(kind: HubKind): HubIndex {
  const cached = _hub[kind];
  if (cached) return cached;
  const data = loadListBundle();
  const groups = new Map<string, MangaListItem[]>();
  for (const m of data.manga) {
    const k = keyOf(kind, m);
    if (!k) continue;
    let g = groups.get(k);
    if (!g) groups.set(k, (g = []));
    g.push(m);
  }
  const defs: HubDef[] = [];
  const items = new Map<string, MangaListItem[]>();
  for (const [key, arr] of groups) {
    if (arr.length < HUB_MIN[kind]) continue;
    let name = key;
    let extra: Pick<HubDef, "publisher" | "demographic"> = {};
    if (kind === "magazine") {
      const mg = data.magazines.find((x) => x.key === key);
      if (!mg) continue; // master 外のキー = 作品頁でもチップが出ない → ハブも作らない
      name = mg.name;
      extra = { publisher: mg.publisher, demographic: mg.demographic };
    } else if (kind === "publisher") {
      name = data.publishers.find((x) => x.key === key)?.name ?? key;
    } else {
      name = `${key}年`;
    }
    arr.sort(kind === "magazine" ? byYearStarted : byPopularity);
    defs.push({
      kind,
      key,
      name,
      count: arr.length,
      completed: arr.filter((m) => m.status === "completed").length,
      pages: Math.ceil(arr.length / HUB_PAGE_SIZE),
      ...extra,
    });
    items.set(key, arr);
  }
  defs.sort(
    kind === "year"
      ? (a, b) => Number(a.key) - Number(b.key)
      : (a, b) => b.count - a.count || coll.compare(a.name, b.name),
  );
  const idx: HubIndex = { defs, byKey: new Map(defs.map((d) => [d.key, d])), items };
  _hub[kind] = idx;
  return idx;
}

export function hubDefs(kind: HubKind): HubDef[] {
  return hubIndex(kind).defs;
}

export function hubDef(kind: HubKind, key: string): HubDef | null {
  return hubIndex(kind).byKey.get(key) ?? null;
}

export function hubHref(kind: HubKind, key: string, page = 1): string {
  return page > 1 ? `/${kind}/${key}/${page}` : `/${kind}/${key}`;
}

/** 作品頁チップ用: ハブ頁が実在する時だけ href を返す(無ければ null = 従来の /browse? へフォールバック) */
export function hubHrefIfExists(kind: HubKind, key: string | number | null | undefined): string | null {
  if (key === null || key === undefined || key === "" || key === 0) return null;
  const k = String(key);
  return hubDef(kind, k) ? hubHref(kind, k) : null;
}

export function hubItems(kind: HubKind, key: string): MangaListItem[] {
  return hubIndex(kind).items.get(key) ?? [];
}

export function hubRows(kind: HubKind, key: string, page: number): MangaListItem[] {
  return hubItems(kind, key).slice((page - 1) * HUB_PAGE_SIZE, page * HUB_PAGE_SIZE);
}

/** 代表作(人気上位N) = description 用 */
export function hubTop(kind: HubKind, key: string, n = 3): MangaListItem[] {
  return [...hubItems(kind, key)].sort(byPopularity).filter((m) => pop(m) > 0).slice(0, n);
}

/** URL parts(catch-all) → {key,page}。 純粋関数(テスト対象)。
 *  /magazine/x/1 のような「1頁目の明示URL」は canonical 重複になるので不正扱い(null)。 */
export function parseHubParts(parts: string[] | undefined): { key: string; page: number } | null {
  if (!parts || parts.length < 1 || parts.length > 2) return null;
  const key = parts[0];
  if (!key || key === "_empty") return null;
  if (parts.length === 1) return { key, page: 1 };
  if (!/^\d+$/.test(parts[1])) return null;
  const page = Number(parts[1]);
  if (page < 2) return null;
  return { key, page };
}

export function resolveHubParts(kind: HubKind, parts: string[] | undefined): { def: HubDef; page: number } | null {
  const p = parseHubParts(parts);
  if (!p) return null;
  const def = hubDef(kind, p.key);
  if (!def || p.page > def.pages) return null;
  return { def, page: p.page };
}

/** generateStaticParams 用(catch-all)。 ★空ガード: output:export は params 0件で落ちるので placeholder */
export function hubStaticParams(kind: HubKind): { parts: string[] }[] {
  const out: { parts: string[] }[] = [];
  for (const d of hubDefs(kind)) {
    out.push({ parts: [d.key] });
    for (let p = 2; p <= d.pages; p++) out.push({ parts: [d.key, String(p)] });
  }
  return out.length > 0 ? out : [{ parts: ["_empty"] }];
}

// ---- master 名の解決(行の付随情報用・小さなキャッシュ) ----
let _names: { magazine: Map<string, string>; publisher: Map<string, string>; demographic: Map<string, string> } | null = null;
function names() {
  if (_names) return _names;
  const d = loadListBundle();
  _names = {
    magazine: new Map(d.magazines.map((x) => [x.key, x.name])),
    publisher: new Map(d.publishers.map((x) => [x.key, x.name])),
    demographic: new Map(d.demographics.map((x) => [x.key, x.name])),
  };
  return _names;
}
export function magazineName(key: string | null | undefined): string | null {
  return key ? (names().magazine.get(key) ?? null) : null;
}
export function publisherName(key: string | null | undefined): string | null {
  return key ? (names().publisher.get(key) ?? null) : null;
}
export function demographicName(key: string | null | undefined): string | null {
  return key ? (names().demographic.get(key) ?? null) : null;
}

/** description の代表作名: 長題は途中で切らず「…」を付ける(『僕のヒーローアカデミアチームアップミッシ』型の
 *  中途半端な切れ方を避ける。 preview実測 2026-09-04) */
export function repTitle(t: string, max = 22): string {
  return t.length > max ? `${t.slice(0, max)}…` : t;
}

/** 見出し・title・description(ハブ種別ごとの文言を1か所に) */
export function hubHeading(def: HubDef): string {
  if (def.kind === "magazine") return `${def.name} 連載作品一覧`;
  if (def.kind === "publisher") return `${def.name}の漫画`;
  return `${def.key}年の漫画`;
}

export function hubMeta(def: HubDef, page: number): { title: string; description: string } {
  const n = def.count.toLocaleString();
  const c = def.completed.toLocaleString();
  const pageSfx = page > 1 ? `（${page}/${def.pages}ページ）` : "";
  const rep = hubTop(def.kind, def.key, 3).map((m) => repTitle(m.title));
  const repText = rep.length > 0 ? `『${rep.join("』『")}』など。` : "";
  const tail = "各作品の全巻一覧・発売日・ISBN・購入リンクつき。";
  if (def.kind === "magazine") {
    const pub = publisherName(def.publisher);
    return {
      title: `${def.name} 連載作品一覧（${n}作品・連載開始順）${pageSfx}`,
      description: `${def.name}${pub ? `（${pub}）` : ""}に連載・掲載された漫画${n}作品を連載開始年順に掲載。${repText}${tail}`,
    };
  }
  if (def.kind === "publisher") {
    return {
      title: `${def.name}の漫画 一覧（人気順・${n}作品）${pageSfx}`,
      description: `${def.name}が刊行した漫画${n}作品を人気順に掲載（完結${c}作）。${repText}${tail}`,
    };
  }
  return {
    title: `${def.key}年の漫画 一覧（連載開始・${n}作品）${pageSfx}`,
    description: `${def.key}年に連載・刊行が始まった漫画${n}作品を人気順に掲載（完結${c}作）。${repText}${tail}`,
  };
}

// ---- ジャンル面(/genre/[key]) と 下位面(/genre/[key]/[sub]) ----

export const GENRE_SUB_MIN = 10;
export type GenreSub = { sub: string; label: string; count: number };

const _genreItems = new Map<string, MangaListItem[]>();
/** ジャンルの全作品(人気順)。 ジャンル面・下位面・metadata で共有 */
export function genreItems(key: string): MangaListItem[] {
  const c = _genreItems.get(key);
  if (c) return c;
  const items = loadListBundle()
    .manga.filter((m) => (m.genres || []).includes(key))
    .sort(byPopularity);
  _genreItems.set(key, items);
  return items;
}

export function decadeOf(year: number): number {
  return Math.floor(year / 10) * 10;
}

/** sub 文字列 → 表示ラベル("completed" / "1990s")。 不正なら null */
export function subLabel(sub: string): string | null {
  if (sub === "completed") return "完結済み";
  const m = /^(\d{4})s$/.exec(sub);
  return m ? `${m[1]}年代` : null;
}

export function genreSubItems(key: string, sub: string): MangaListItem[] | null {
  const items = genreItems(key);
  if (sub === "completed") return items.filter((m) => m.status === "completed");
  const m = /^(\d{4})s$/.exec(sub);
  if (!m) return null;
  const dec = Number(m[1]);
  return items.filter((x) => x.year_started > 0 && decadeOf(x.year_started) === dec);
}

const _genreSubs = new Map<string, GenreSub[]>();
/** ジャンルの下位面一覧(閾値以上のみ): 完結済み + 年代(古い順) */
export function genreSubs(key: string): GenreSub[] {
  const c = _genreSubs.get(key);
  if (c) return c;
  const items = genreItems(key);
  const out: GenreSub[] = [];
  const completed = items.filter((m) => m.status === "completed").length;
  if (completed >= GENRE_SUB_MIN) out.push({ sub: "completed", label: "完結済み", count: completed });
  const decs = new Map<number, number>();
  for (const m of items) {
    if (m.year_started > 0) {
      const d = decadeOf(m.year_started);
      decs.set(d, (decs.get(d) ?? 0) + 1);
    }
  }
  for (const [d, n] of [...decs].sort((a, b) => a[0] - b[0])) {
    if (n >= GENRE_SUB_MIN) out.push({ sub: `${d}s`, label: `${d}年代`, count: n });
  }
  _genreSubs.set(key, out);
  return out;
}

export function hasGenreSub(key: string, sub: string): boolean {
  return genreSubs(key).some((s) => s.sub === sub);
}

export function genreSubStaticParams(): { key: string; sub: string }[] {
  const out: { key: string; sub: string }[] = [];
  for (const g of loadListBundle().genres) {
    for (const s of genreSubs(g.key)) out.push({ key: g.key, sub: s.sub });
  }
  return out.length > 0 ? out : [{ key: "_empty", sub: "_empty" }];
}

/** ジャンル内の主要掲載誌(ハブ頁が在る誌だけ・作品数順) = ジャンル面⇄雑誌面の横リンク */
export function genreMagazines(key: string, limit = 8): { def: HubDef; count: number }[] {
  const cnt = new Map<string, number>();
  for (const m of genreItems(key)) if (m.magazine) cnt.set(m.magazine, (cnt.get(m.magazine) ?? 0) + 1);
  const out: { def: HubDef; count: number }[] = [];
  for (const [k, n] of cnt) {
    const def = hubDef("magazine", k);
    if (def) out.push({ def, count: n });
  }
  return out.sort((a, b) => b.count - a.count).slice(0, limit);
}
