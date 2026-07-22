import { describe, expect, it } from "vitest";
import {
  applyFilters,
  authorKey,
  filtersFromSearchParams,
  filtersToSearchParams,
  authorsWithKana,
  emptyFilterState,
  matchText,
  uniqueAuthors,
  yearBounds,
} from "./filters";
import type { MangaListItem, MangaSearchItem } from "./schema";

// 検索索引アイテムの mock (= matchText 用)
const s = (over: Partial<MangaSearchItem> = {}): MangaSearchItem => ({
  slug: over.slug ?? "x",
  title: over.title ?? "ONE PIECE",
  title_kana: over.title_kana ?? "ワンピース",
  title_romaji: over.title_romaji ?? "one piece",
  alt: over.alt ?? [],
  au: over.au ?? ["尾田栄一郎"],
});

const m = (over: Partial<MangaListItem> = {}): MangaListItem => ({
  slug: over.slug ?? "x",
  title: over.title ?? "ONE PIECE",
  title_kana: over.title_kana ?? "ワンピース",
  cover: over.cover ?? null,
  year_started: over.year_started ?? 1997,
  year_ended: over.year_ended ?? null,
  status: over.status ?? "ongoing",
  authors: over.authors ?? [{ name: "尾田栄一郎", role: "writer_artist" }],
  original_authors: over.original_authors ?? [],
  publisher: over.publisher ?? "shueisha",
  publishers: over.publishers ?? ["shueisha"],
  magazine: over.magazine ?? "weekly-shonen-jump",
  demographic: over.demographic ?? "shounen",
  genres: over.genres ?? ["action", "adventure"],
  total_volumes: over.total_volumes ?? 1,
  max_edition_volumes: over.max_edition_volumes ?? 1,
});

describe("matchText", () => {
  const op = s();

  it("空クエリは常に true", () => {
    expect(matchText("", op)).toBe(true);
  });

  it("漢字タイトルの部分一致", () => {
    expect(matchText("PIECE", op)).toBe(true);
  });

  it("カナでヒット", () => {
    expect(matchText("ワン", op)).toBe(true);
  });

  it("ローマ字でヒット", () => {
    expect(matchText("one", op)).toBe(true);
  });

  it("カナタイトルをローマ字で検索しヒット", () => {
    expect(matchText("wanpi", s({ title_kana: "ワンピース", title_romaji: "ZZZ" }))).toBe(true);
  });

  it("長音符の有無を吸収する", () => {
    expect(matchText("ワンピス", s({ title_kana: "ワンピース" }))).toBe(true);
  });

  it("中黒(・)の有無を吸収する", () => {
    const sla = s({ title: "シャングリラ・フロンティア", title_kana: "シャングリラフロンティア" });
    expect(matchText("シャングリラフロンティア", sla)).toBe(true); // ・無で検索
    expect(matchText("シャングリラ・フロンティア", sla)).toBe(true); // ・有で検索
  });

  it("中黒(・)の位置揺れも吸収する", () => {
    const sla = s({ title: "シャングリラ・フロンティア", title_kana: "シャングリラフロンティア" });
    expect(matchText("シャングリ・ラフロンティア", sla)).toBe(true); // ・誤位置でも当たる
  });
});

describe("applyFilters", () => {
  const items: MangaListItem[] = [
    m({ slug: "a", year_started: 1990 }),
    m({ slug: "b", year_started: 2000, demographic: "seinen", genres: ["drama"] }),
    m({ slug: "c", year_started: 2015, genres: ["action", "drama"] }),
  ];

  it("年レンジで絞れる", () => {
    const r = applyFilters(items, { ...emptyFilterState(), yearMin: 1995, yearMax: 2010 });
    expect(r.map((x) => x.slug)).toEqual(["b"]);
  });

  it("分野フィルタ", () => {
    const r = applyFilters(items, { ...emptyFilterState(), demographics: ["seinen"] });
    expect(r.map((x) => x.slug)).toEqual(["b"]);
  });

  it("ジャンル OR で絞れる", () => {
    const r = applyFilters(items, { ...emptyFilterState(), genres: ["drama"], genreMode: "or" });
    expect(r.map((x) => x.slug).sort()).toEqual(["b", "c"]);
  });

  it("ジャンル AND は全条件を含むものだけ", () => {
    const r = applyFilters(items, {
      ...emptyFilterState(),
      genres: ["action", "drama"],
      genreMode: "and",
    });
    expect(r.map((x) => x.slug)).toEqual(["c"]);
  });

  it("複合フィルタは AND で結合", () => {
    const r = applyFilters(items, {
      ...emptyFilterState(),
      yearMin: 2010,
      genres: ["drama"],
    });
    expect(r.map((x) => x.slug)).toEqual(["c"]);
  });
});

describe("yearBounds と uniqueAuthors", () => {
  const items: MangaListItem[] = [
    m({ slug: "a", year_started: 1990, authors: [{ name: "A", role: "writer_artist" }] }),
    m({
      slug: "b",
      year_started: 2020,
      authors: [{ name: "B", role: "artist" }],
      original_authors: [{ name: "C" }],
    }),
  ];

  it("yearBounds は最小と最大", () => {
    expect(yearBounds(items)).toEqual([1990, 2020]);
  });

  it("uniqueAuthors は原作者を含めるオプション", () => {
    expect(uniqueAuthors(items, false)).toEqual(["A", "B"]);
    expect(uniqueAuthors(items, true).sort()).toEqual(["A", "B", "C"]);
  });
});

describe("authorKey 空白違いの同一人物統合(2026-07-21)", () => {
  const items: MangaListItem[] = [
    m({ slug: "x1", authors: [{ name: "蟹沢ちひろ", role: "writer_artist" }] }),
    m({ slug: "x2", authors: [{ name: "蟹沢 ちひろ", kana: "カニサワ チヒロ", role: "writer_artist" }] }),
    m({ slug: "x3", authors: [{ name: "Ark Performance", role: "writer_artist" }] }),
  ];
  it("uniqueAuthors が空白違いを1人に束ね無空白表示を選ぶ", () => {
    const names = uniqueAuthors(items);
    expect(names.filter((n) => authorKey(n) === "蟹沢ちひろ")).toEqual(["蟹沢ちひろ"]);
    expect(names).toContain("Ark Performance");
  });
  it("authorsWithKana も1エントリ(count=2)に統合", () => {
    const a = authorsWithKana(items).find((e) => authorKey(e.name) === "蟹沢ちひろ");
    expect(a?.count).toBe(2);
    expect(a?.name).toBe("蟹沢ちひろ");
  });
  it("著者フィルタが空白違いの頁も通す", () => {
    const st = { ...emptyFilterState(), authors: ["蟹沢ちひろ"] };
    expect(applyFilters(items, st).map((r) => r.slug).sort()).toEqual(["x1", "x2"]);
  });
});

describe("filtersToSearchParams ⇄ filtersFromSearchParams round-trip(2026-07-22)", () => {
  it("非デフォルト値が完全往復する", () => {
    const s = {
      ...emptyFilterState(),
      query: "うる星",
      yearMin: 1980,
      yearMax: 1999,
      launch: "1980s",
      publishers: ["shogakukan", "kodansha"],
      genres: ["romcom", "school"],
      genreMode: "and" as const,
      authors: ["高橋留美子"],
      statuses: ["completed" as const],
      anime: true,
      sort: "popularity" as const,
    };
    const p = filtersToSearchParams(s);
    const back = { ...emptyFilterState(), ...filtersFromSearchParams(p) };
    expect(back).toEqual(s);
  });
  it("デフォルト状態はparams空", () => {
    expect(filtersToSearchParams(emptyFilterState()).toString()).toBe("");
  });
  it("既存params(page等)を保持しつつフィルタキーだけ管理", () => {
    const base = new URLSearchParams("page=3&v=x");
    const p = filtersToSearchParams({ ...emptyFilterState(), genres: ["horror"] }, base);
    expect(p.get("page")).toBe("3");
    expect(p.get("genre")).toBe("horror");
  });
});
