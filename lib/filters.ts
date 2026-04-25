import type { Manga } from "./schema";
import { kanaToRomaji, normalizeForSearch, romajiToHiragana } from "./romaji";

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
});

/**
 * 検索クエリにマッチするか。タイトル・よみがな・ローマ字いずれかで部分一致。
 * かな⇄ローマ字の双方向変換も試す。
 */
export function matchText(query: string, manga: Manga): boolean {
  if (!query) return true;
  const q = normalizeForSearch(query);
  if (!q) return true;

  const haystacks = [
    normalizeForSearch(manga.title),
    normalizeForSearch(manga.title_kana),
    normalizeForSearch(manga.title_romaji),
    normalizeForSearch(kanaToRomaji(manga.title_kana)),
  ];
  if (haystacks.some((h) => h && h.includes(q))) return true;

  // クエリがローマ字 → かなに変換して title_kana と照合
  const asKana = normalizeForSearch(romajiToHiragana(q));
  if (asKana && asKana !== q) {
    const kanaHay = normalizeForSearch(romajiToHiragana(kanaToRomaji(manga.title_kana)));
    if (kanaHay.includes(asKana)) return true;
  }

  // クエリがかな → ローマ字に変換して title_romaji と照合
  const asRomaji = normalizeForSearch(kanaToRomaji(q));
  if (asRomaji && asRomaji !== q) {
    const romajiHay = normalizeForSearch(manga.title_romaji);
    if (romajiHay.includes(asRomaji)) return true;
  }

  return false;
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

export function applyFilters(items: Manga[], state: FilterState): Manga[] {
  return items.filter((m) => {
    if (!matchText(state.query, m)) return false;
    if (!inRange(m.year_started, state.yearMin, state.yearMax)) return false;
    if (state.demographics.length && !state.demographics.includes(m.demographic)) return false;
    if (state.publishers.length && !state.publishers.includes(m.publisher)) return false;
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
    return true;
  });
}

export function uniqueAuthors(items: Manga[], includeOriginal = false): string[] {
  const set = new Set<string>();
  for (const m of items) {
    for (const a of m.authors) set.add(a.name);
    if (includeOriginal) for (const a of m.original_authors) set.add(a.name);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b, "ja"));
}

export function yearBounds(items: Manga[]): [number, number] {
  if (items.length === 0) return [1950, new Date().getFullYear()];
  let min = items[0].year_started;
  let max = items[0].year_started;
  for (const m of items) {
    if (m.year_started < min) min = m.year_started;
    if (m.year_started > max) max = m.year_started;
  }
  return [min, max];
}
