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
  demographics: string[];        // 空配列 = 全て
  publishers: string[];
  magazines: string[];
  authors: string[];             // 表示名で比較
  originalAuthors: string[];
  genres: string[];
  genreMode: "and" | "or";
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
  demographics: [],
  publishers: [],
  magazines: [],
  authors: [],
  originalAuthors: [],
  genres: [],
  genreMode: "or",
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
    if (state.demographics.length && !state.demographics.includes(m.demographic)) return false;
    // 複数社作品対応: 選択キーが「どれかの版の出版社」に一致すればヒット (m.publishers 集合)
    if (state.publishers.length) {
      const pubs = m.publishers.length ? m.publishers : [m.publisher];
      if (!state.publishers.some((p) => pubs.includes(p))) return false;
    }
    if (state.magazines.length) {
      if (!m.magazine || !state.magazines.includes(m.magazine)) return false;
    }
    if (state.authors.length) {
      if (!intersects(state.authors, m.authors.map((a) => a.name))) return false;
    }
    if (state.originalAuthors.length) {
      if (!intersects(state.originalAuthors, m.original_authors.map((a) => a.name))) return false;
    }
    if (state.genres.length) {
      const ok = state.genreMode === "and"
        ? containsAll(state.genres, m.genres)
        : intersects(state.genres, m.genres);
      if (!ok) return false;
    }
    if (state.anime && !m.anime_adapted) return false;
    if (state.hasAwards && (!m.awards || m.awards.length === 0)) return false;
    if (state.statuses.length && !state.statuses.includes(m.status)) return false;
    return true;
  });
  return sortItems(filtered, state.sort);
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

export function uniqueAuthors(items: MangaListItem[], includeOriginal = false): string[] {
  const set = new Set<string>();
  for (const m of items) {
    for (const a of m.authors) set.add(a.name);
    if (includeOriginal) for (const a of m.original_authors) set.add(a.name);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b, "ja"));
}

/** 著者名 → 読み(カタカナ)の一覧 (= 50音索引用)。 重複排除、 kana有る方を優先採用。 */
export function authorsWithKana(
  items: MangaListItem[],
  includeOriginal = false,
): { name: string; kana: string }[] {
  const map = new Map<string, string>();
  const add = (name: string, kana?: string) => {
    const prev = map.get(name);
    if (prev === undefined || (!prev && kana)) map.set(name, kana ?? "");
  };
  for (const m of items) {
    for (const a of m.authors) add(a.name, a.kana);
    if (includeOriginal) for (const a of m.original_authors) add(a.name, a.kana);
  }
  return Array.from(map, ([name, kana]) => ({ name, kana })).sort((a, b) =>
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
export function filtersFromSearchParams(p: ParamsLike | null | undefined): Partial<FilterState> {
  if (!p) return {};
  const out: Partial<FilterState> = {};
  const pickList = (key: string) => {
    const v = p.get(key);
    if (!v) return undefined;
    return v.split(",").map((x) => x.trim()).filter(Boolean);
  };
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
