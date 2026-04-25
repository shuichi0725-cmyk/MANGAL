import { describe, expect, it } from "vitest";
import {
  applyFilters,
  emptyFilterState,
  matchText,
  uniqueAuthors,
  yearBounds,
} from "./filters";
import type { Manga } from "./schema";

const m = (over: Partial<Manga> = {}): Manga => ({
  slug: over.slug ?? "x",
  title: over.title ?? "ONE PIECE",
  title_kana: over.title_kana ?? "ワンピース",
  title_romaji: over.title_romaji ?? "one piece",
  year_started: over.year_started ?? 1997,
  year_ended: over.year_ended ?? null,
  status: over.status ?? "ongoing",
  authors: over.authors ?? [{ name: "尾田栄一郎", role: "writer_artist" }],
  original_authors: over.original_authors ?? [],
  publisher: over.publisher ?? "shueisha",
  magazine: over.magazine ?? "weekly-shonen-jump",
  demographic: over.demographic ?? "shounen",
  genres: over.genres ?? ["action", "adventure"],
  synopsis: over.synopsis ?? "",
  volume_1: over.volume_1 ?? {},
});

describe("matchText", () => {
  const op = m();

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
    expect(matchText("wanpi", m({ title_kana: "ワンピース", title_romaji: "ZZZ" }))).toBe(true);
  });

  it("長音符の有無を吸収する", () => {
    expect(matchText("ワンピス", m({ title_kana: "ワンピース" }))).toBe(true);
  });
});

describe("applyFilters", () => {
  const items: Manga[] = [
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
  const items: Manga[] = [
    m({ slug: "a", year_started: 1990, authors: [{ name: "A", role: "writer_artist" }] }),
    m({
      slug: "b",
      year_started: 2020,
      authors: [{ name: "B", role: "artist" }],
      original_authors: [{ name: "C", role: "writer" }],
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
