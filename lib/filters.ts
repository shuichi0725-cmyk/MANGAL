import type { ArtBook, MangaListItem, MangaSearchItem, StatusT } from "./schema";
import { kanaToRomaji, normalizeForSearch, romajiToHiragana } from "./romaji";

export type SortKey =
  | "default"
  | "year-desc"
  | "year-asc"
  | "title"
  | "volumes"
  | "popularity";

export type FilterState = {
  query: string;
  yearMin: number | null;
  yearMax: number | null;
  /** ★創刊ドリルダウン(2026-07-07 Q3-A): "1990s"(年代) | "1994"(年) | "1994-07"(月)。first_volume_date前方一致 */
  launch: string | null;
  demographics: string[];        // 空配列 = 全て
  publishers: string[];
  magazines: string[];
  authors: string[];             // 表示名で比較
  originalAuthors: string[];
  genres: string[];
  genreMode: "and" | "or";
  themes: string[];              // 要素タグ(表示文字列で比較)。 空配列 = 全て
  themeMode: "and" | "or";
  // 新規 (2026-05-07): カテゴリハブ + 拡張フィルタ
  anime: boolean;                // true = アニメ化作品のみ
  hasAwards: boolean;            // true = 受賞作品のみ
  statuses: StatusT[];           // 空配列 = 全て、 完結/連載中/休載 のサブセット
  sort: SortKey;                 // ソートキー
  // ★画集モード: true = 一覧を漫画でなく画集(別カテゴリ)に切替。 ジャンル欄の
  //   「画集」チップで toggle。 他の漫画用フィルタは画集には適用しない(query/年のみ)。
  artBooks: boolean;
};

export const emptyFilterState = (): FilterState => ({
  query: "",
  yearMin: null,
  yearMax: null,
  launch: null,
  demographics: [],
  publishers: [],
  magazines: [],
  authors: [],
  originalAuthors: [],
  genres: [],
  genreMode: "or",
  themes: [],
  themeMode: "or",
  anime: false,
  hasAwards: false,
  statuses: [],
  sort: "default",
  artBooks: false,
});

/**
 * 検索クエリにマッチするか。タイトル・よみがな・ローマ字いずれかで部分一致。
 * かな⇄ローマ字の双方向変換も試す。
 */
export function matchText(query: string, item: MangaSearchItem): boolean {
  if (!query) return true;
  const q = normalizeForSearch(query);
  if (!q) return true;

  const altTitles = item.alt.map((t) => normalizeForSearch(t));
  // 人物名(著者/原作/credits)も検索対象 (= 検索索引で au[] に統合済)。
  const people = item.au.map((n) => normalizeForSearch(n));

  const haystacks = [
    normalizeForSearch(item.title),
    normalizeForSearch(item.title_kana),
    normalizeForSearch(item.title_romaji),
    normalizeForSearch(kanaToRomaji(item.title_kana)),
    ...altTitles,
    ...people,
  ];
  if (haystacks.some((h) => h && h.includes(q))) return true;

  // クエリがローマ字 → かなに変換して title_kana と照合
  const asKana = normalizeForSearch(romajiToHiragana(q));
  if (asKana && asKana !== q) {
    const kanaHay = normalizeForSearch(romajiToHiragana(kanaToRomaji(item.title_kana)));
    if (kanaHay.includes(asKana)) return true;
  }

  // クエリがかな → ローマ字に変換して title_romaji と照合
  const asRomaji = normalizeForSearch(kanaToRomaji(q));
  if (asRomaji && asRomaji !== q) {
    const romajiHay = normalizeForSearch(item.title_romaji);
    if (romajiHay.includes(asRomaji)) return true;
  }

  return false;
}

/** 検索索引 全体から query にマッチする slug 集合を返す (= 一覧 filter と AND 合成して使う)。 */
export function searchMatches(query: string, searchIndex: MangaSearchItem[]): Set<string> {
  const set = new Set<string>();
  if (!query) return set;
  for (const it of searchIndex) if (matchText(query, it)) set.add(it.slug);
  return set;
}

function inRange(value: number, min: number | null, max: number | null): boolean {
  if (min !== null && value < min) return false;
  if (max !== null && value > max) return false;
  return true;
}

function intersects<T>(needles: T[], haystack: T[]): boolean {
  if (needles.length === 0) return true;
  return needles.some((n) => haystack.includes(n));
}

function containsAll<T>(needles: T[], haystack: T[]): boolean {
  if (needles.length === 0) return true;
  return needles.every((n) => haystack.includes(n));
}

function totalVolumes(m: MangaListItem): number {
  return m.total_volumes;
}

function sortItems(items: MangaListItem[], sort: SortKey): MangaListItem[] {
  switch (sort) {
    case "year-desc":
      return [...items].sort((a, b) => b.year_started - a.year_started);
    case "year-asc":
      return [...items].sort((a, b) => a.year_started - b.year_started);
    case "title":
      return [...items].sort((a, b) =>
        a.title_kana.localeCompare(b.title_kana, "ja"),
      );
    case "volumes":
      return [...items].sort((a, b) => totalVolumes(b) - totalVolumes(a));
    case "popularity":
      // AniList人気度の降順。 同値はスコア降順 → 年降順でタイブレーク。
      return [...items].sort(
        (a, b) =>
          (b.popularity ?? 0) - (a.popularity ?? 0) ||
          (b.score ?? 0) - (a.score ?? 0) ||
          b.year_started - a.year_started,
      );
    case "default":
    default:
      return items;
  }
}

/** 既定ソート=人気順(2026-07-11 ユーザ仕様: 検索前のデフォルトから人気順。手動選択があればそれを尊重) */
export function effectiveSort(state: FilterState): SortKey {
  if (state.sort === "default") return "popularity";
  return state.sort;
}

/**
 * 一覧フィルタ。 ★検索(query)は別索引(検索索引)で事前計算した matchedSlugs を渡す
 *  (= 一覧索引は検索フィールドを持たない)。 query 有 + matchedSlugs 無(=検索索引未ロード)
 *  の間は空 = 呼び出し側で loading 表示。
 */
export function applyFilters(
  items: MangaListItem[],
  state: FilterState,
  matchedSlugs: Set<string> | null = null,
): MangaListItem[] {
  const filtered = items.filter((m) => {
    if (state.query && (!matchedSlugs || !matchedSlugs.has(m.slug))) return false;
    if (!inRange(m.year_started, state.yearMin, state.yearMax)) return false;
    if (state.launch) {
      const fvd = m.first_volume_date || (m.year_started ? String(m.year_started) : "");
      if (state.launch.endsWith("s")) {
        const dec = Number(state.launch.slice(0, 4));
        const y = Number(fvd.slice(0, 4));
        if (!(y >= dec && y < dec + 10)) return false;
      } else if (!fvd.startsWith(state.launch)) return false;
    }
    if (state.demographics.length && (!m.demographic || !state.demographics.includes(m.demographic))) return false;
    // 複数社作品対応: 選択キーが「どれかの版の出版社」に一致すればヒット (m.publishers 集合)
    if (state.publishers.length) {
      const pubs = m.publishers.length ? m.publishers : [m.publisher];
      if (!state.publishers.some((p) => pubs.includes(p))) return false;
    }
    if (state.magazines.length) {
      if (!m.magazine || !state.magazines.includes(m.magazine)) return false;
    }
    if (state.authors.length) {
      // ★authorKey照合(空白違いの同一人物を通す)
      if (!intersects(state.authors.map(authorKey), m.authors.map((a) => authorKey(a.name)))) return false;
    }
    if (state.originalAuthors.length) {
      if (!intersects(state.originalAuthors.map(authorKey), m.original_authors.map((a) => authorKey(a.name)))) return false;
    }
    if (state.genres.length) {
      const ok = state.genreMode === "and"
        ? containsAll(state.genres, m.genres)
        : intersects(state.genres, m.genres);
      if (!ok) return false;
    }
    if (state.themes.length) {
      const ts = m.themes ?? [];
      const ok = state.themeMode === "and"
        ? containsAll(state.themes, ts)
        : intersects(state.themes, ts);
      if (!ok) return false;
    }
    if (state.anime && !m.anime_adapted) return false;
    if (state.hasAwards && (!m.awards || m.awards.length === 0)) return false;
    if (state.statuses.length && !state.statuses.includes(m.status)) return false;
    return true;
  });
  return sortItems(filtered, effectiveSort(state));
}

/**
 * 画集フィルタ (= 画集モード時の一覧)。 漫画用 filter は適用せず、 query(題/よみ/作画家)
 * と出版年、 sort のみ効かせる。 既定は loader の作画家50音順。
 */
export function applyArtBookFilters(items: ArtBook[], state: FilterState): ArtBook[] {
  let out = items;
  const q = normalizeForSearch(state.query);
  if (q) {
    out = out.filter((a) => {
      const hay = [a.title, a.title_kana, a.title_romaji, a.artist].map(normalizeForSearch);
      return hay.some((h) => h && h.includes(q));
    });
  }
  if (state.yearMin !== null || state.yearMax !== null) {
    out = out.filter((a) => a.year != null && inRange(a.year, state.yearMin, state.yearMax));
  }
  switch (state.sort) {
    case "year-desc":
      return [...out].sort((a, b) => (b.year ?? 0) - (a.year ?? 0));
    case "year-asc":
      return [...out].sort((a, b) => (a.year ?? 0) - (b.year ?? 0));
    case "title":
      return [...out].sort((a, b) => a.title_kana.localeCompare(b.title_kana, "ja"));
    case "volumes":
      return [...out].sort((a, b) => b.volumes.length - a.volumes.length);
    default:
      return out;
  }
}

/** ★著者名の照合キー(2026-07-21): 空白(半角/全角)を無視して同一人物を束ねる。
 *  「蟹沢ちひろ」(MADB系無空白)と「蟹沢 ちひろ」(楽天2026新刊系)が別著者に分裂する実害の吸収。
 *  表記自体は触らない(ユズキ カズ/欧文名など空白が公式のケースを壊さないため=ユーザ裁定の推奨案)。 */
export function authorKey(name: string): string {
  return name.replace(/[\s　]+/g, "");
}

export function uniqueAuthors(items: MangaListItem[], includeOriginal = false): string[] {
  const map = new Map<string, string>(); // authorKey → 表示名(無空白形を優先)
  const add = (name: string) => {
    const k = authorKey(name);
    const prev = map.get(k);
    if (prev === undefined || (prev !== k && name === k)) map.set(k, name);
  };
  for (const m of items) {
    for (const a of m.authors) add(a.name);
    if (includeOriginal) for (const a of m.original_authors) add(a.name);
  }
  return Array.from(map.values()).sort((a, b) => a.localeCompare(b, "ja"));
}

/** 著者名 → 読み(カタカナ)の一覧 (= 50音索引用)。 重複排除、 kana有る方を優先採用。 */
export function authorsWithKana(
  items: MangaListItem[],
  includeOriginal = false,
): { name: string; kana: string; count: number }[] {
  // ★authorKeyで空白違いの同一人物を1エントリに統合(表示名は無空白形を優先=本体67kの慣行)
  const map = new Map<string, { name: string; kana: string; count: number }>();
  const add = (name: string, kana?: string) => {
    const k = authorKey(name);
    const prev = map.get(k);
    if (prev === undefined) map.set(k, { name, kana: (kana ?? "").replace(/[\s　]+/g, ""), count: 1 });
    else {
      prev.count += 1;
      if (prev.name !== k && name === k) prev.name = name;
      if (!prev.kana && kana) prev.kana = kana.replace(/[\s　]+/g, "");
    }
  };
  for (const m of items) {
    for (const a of m.authors) add(a.name, a.kana);
    if (includeOriginal) for (const a of m.original_authors) add(a.name, a.kana);
  }
  return Array.from(map.values()).sort((a, b) =>
    (a.kana || a.name).localeCompare(b.kana || b.name, "ja"),
  );
}

export function yearBounds(items: MangaListItem[]): [number, number] {
  if (items.length === 0) return [1950, new Date().getFullYear()];
  let min = items[0].year_started;
  let max = items[0].year_started;
  for (const m of items) {
    if (m.year_started < min) min = m.year_started;
    if (m.year_started > max) max = m.year_started;
  }
  return [min, max];
}

type ParamsLike = { get(key: string): string | null };

/**
 * URL の検索パラメータ（?publisher=A&genre=action,drama 等）から
 * フィルタ状態を復元する。指定の無い項目は触らない。
 */
/** ★フィルタ状態→URL params(2026-07-22): filtersFromSearchParams と完全対称のエンコーダ。
 *  非デフォルト値だけを書く。詳細→戻るでフィルタが消える問題の恒久修正
 *  (URLがsource of truthなのにFilterPanel変更がURLに書かれていなかった)。 */
export function filtersToSearchParams(s: FilterState, base?: URLSearchParams): URLSearchParams {
  const p = base ?? new URLSearchParams();
  const setList = (key: string, v: string[]) => {
    if (v.length) p.set(key, v.join(","));
    else p.delete(key);
  };
  const setIf = (key: string, cond: boolean, val: string) => {
    if (cond) p.set(key, val);
    else p.delete(key);
  };
  setIf("q", !!s.query, s.query);
  setIf("launch", !!s.launch, s.launch ?? "");
  setIf("yearMin", s.yearMin !== null, String(s.yearMin));
  setIf("yearMax", s.yearMax !== null, String(s.yearMax));
  setList("publisher", s.publishers);
  setList("magazine", s.magazines);
  setList("demographic", s.demographics);
  setList("author", s.authors);
  setList("originalAuthor", s.originalAuthors);
  setList("genre", s.genres);
  setIf("genreMode", s.genreMode !== "or", s.genreMode);
  setList("theme", s.themes);
  setIf("themeMode", s.themeMode !== "or", s.themeMode);
  setIf("anime", s.anime, "true");
  setIf("artBooks", s.artBooks, "true");
  setIf("hasAwards", s.hasAwards, "true");
  setList("status", s.statuses);
  setIf("sort", s.sort !== "default", s.sort);
  return p;
}

export function filtersFromSearchParams(p: ParamsLike | null | undefined): Partial<FilterState> {
  if (!p) return {};
  const out: Partial<FilterState> = {};
  const pickList = (key: string) => {
    const v = p.get(key);
    if (!v) return undefined;
    return v.split(",").map((x) => x.trim()).filter(Boolean);
  };
  const launch = p.get("launch");
  if (launch) out.launch = launch;
  const yearMin = p.get("yearMin");
  const yearMax = p.get("yearMax");
  if (yearMin) out.yearMin = Number(yearMin);
  if (yearMax) out.yearMax = Number(yearMax);
  const q = p.get("q");
  if (q) out.query = q;
  const publishers = pickList("publisher");
  if (publishers) out.publishers = publishers;
  const magazines = pickList("magazine");
  if (magazines) out.magazines = magazines;
  const demographics = pickList("demographic");
  if (demographics) out.demographics = demographics;
  const authors = pickList("author");
  if (authors) out.authors = authors;
  const originalAuthors = pickList("originalAuthor");
  if (originalAuthors) out.originalAuthors = originalAuthors;
  const genres = pickList("genre");
  if (genres) out.genres = genres;
  const genreMode = p.get("genreMode");
  if (genreMode === "and" || genreMode === "or") out.genreMode = genreMode;
  const themes = pickList("theme");
  if (themes) out.themes = themes;
  const themeMode = p.get("themeMode");
  if (themeMode === "and" || themeMode === "or") out.themeMode = themeMode;
  // 新規 params (2026-05-07)
  const anime = p.get("anime");
  if (anime === "true") out.anime = true;
  const artBooks = p.get("artBooks");
  if (artBooks === "true") out.artBooks = true;
  const hasAwards = p.get("hasAwards");
  if (hasAwards === "true") out.hasAwards = true;
  const statuses = pickList("status");
  if (statuses) {
    const valid = statuses.filter(
      (s): s is StatusT => s === "ongoing" || s === "completed" || s === "hiatus",
    );
    if (valid.length > 0) out.statuses = valid;
  }
  const sort = p.get("sort");
  if (
    sort === "year-desc" ||
    sort === "year-asc" ||
    sort === "title" ||
    sort === "volumes" ||
    sort === "popularity" ||
    sort === "default"
  ) {
    out.sort = sort;
  }
  return out;
}
