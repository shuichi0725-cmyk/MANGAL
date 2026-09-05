import { describe, expect, it } from "vitest";
import {
  applyFilters,
  authorKey,
  volumeBucket,
  filtersFromSearchParams,
  filtersToSearchParams,
  authorsWithKana,
  emptyFilterState,
  uniqueAuthors,
  yearBounds,
} from "./filters";
import type { MangaListItem } from "./schema";

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

// (旧 matchText のテスト群は 2026-08-03 の検索索引廃止で削除。
//  長音符・中黒などの正規化吸収は現行検索の実体 lib/clientSearch.ts +
//  検索スナップショットゲート(searchSnapshot.test.ts)側で担保。)

// ★matchedSlugs は「渡されたら常に効く」(2026-09-05)。 一覧表(/list)は検索語を FilterState に
//   写さない設計なので、state.query に依存させると渡しても無視され、フィルターの件数だけが
//   全件基準になる(= 実際そうなっていた)。
describe("matchedSlugs(検索の一致集合)", () => {
  const items: MangaListItem[] = [
    m({ slug: "hit" }),
    m({ slug: "miss" }),
  ];

  it("query が空でも matchedSlugs だけで絞れる(/list の経路)", () => {
    const r = applyFilters(items, emptyFilterState(), new Set(["hit"]));
    expect(r.map((x) => x.slug)).toEqual(["hit"]);
  });

  it("query 有り + matchedSlugs で絞れる(/browse の経路)", () => {
    const r = applyFilters(items, { ...emptyFilterState(), query: "x" }, new Set(["hit"]));
    expect(r.map((x) => x.slug)).toEqual(["hit"]);
  });

  it("query 有り + 一致集合が未着(null)は空 = 0件と断言しないため", () => {
    expect(applyFilters(items, { ...emptyFilterState(), query: "x" }, null)).toEqual([]);
  });

  it("どちらも無ければ全件", () => {
    expect(applyFilters(items, emptyFilterState()).length).toBe(2);
  });
});

// ★巻数バケツ(2026-09-05 ユーザ裁定)。 基準は max_edition_volumes(= 一番巻数の多い版1本)。
//   total_volumes(全版合算)ではない = 文庫版/完全版を足した数で分類しないための番人。
describe("巻数バケツ", () => {
  it("境界が 1 / 2-5 / 6-10 / 11-15 / 16-20 / 21+ になっている", () => {
    const b = (n: number) => volumeBucket(m({ max_edition_volumes: n, total_volumes: n }));
    expect([1, 2, 5, 6, 10, 11, 15, 16, 20, 21, 110].map(b)).toEqual([
      "1", "2-5", "2-5", "6-10", "6-10", "11-15", "11-15", "16-20", "16-20", "21+", "21+",
    ]);
  });

  it("巻数が取れない(0)頁はどのバケツにも入らない", () => {
    expect(volumeBucket(m({ max_edition_volumes: 0, total_volumes: 0 }))).toBeNull();
  });

  it("全版合算(total_volumes)ではなく max_edition_volumes で分類する", () => {
    // SLAM DUNK型: 通常31 + 完全版24 + 新装再編20 → total=75 だが 巻数は31 = 21+
    const slam = m({ slug: "slam", max_edition_volumes: 31, total_volumes: 75 });
    // 文庫版で水増しされた単巻: total=4 でも 巻数は2 = 2-5
    const solo = m({ slug: "solo", max_edition_volumes: 2, total_volumes: 4 });
    expect(volumeBucket(slam)).toBe("21+");
    expect(volumeBucket(solo)).toBe("2-5");
    const r = applyFilters([slam, solo], { ...emptyFilterState(), volumes: ["21+"] });
    expect(r.map((x) => x.slug)).toEqual(["slam"]);
  });

  it("複数バケツの選択は OR", () => {
    const items = [
      m({ slug: "one", max_edition_volumes: 1 }),
      m({ slug: "mid", max_edition_volumes: 8 }),
      m({ slug: "long", max_edition_volumes: 40 }),
    ];
    const r = applyFilters(items, { ...emptyFilterState(), volumes: ["1", "21+"] });
    expect(r.map((x) => x.slug).sort()).toEqual(["long", "one"]);
  });

  it("URL params と往復できる", () => {
    const st = { ...emptyFilterState(), volumes: ["2-5", "21+"] };
    const p = filtersToSearchParams(st);
    expect(p.get("volume")).toBe("2-5,21+");
    expect(filtersFromSearchParams(p).volumes).toEqual(["2-5", "21+"]);
    // master 外のキーは捨てる
    expect(filtersFromSearchParams(new URLSearchParams("volume=999")).volumes).toBeUndefined();
  });

  it("並び順「巻数」は max_edition_volumes 降順(全版合算ではない)", () => {
    const items = [
      m({ slug: "sum", max_edition_volumes: 10, total_volumes: 99 }),
      m({ slug: "real", max_edition_volumes: 40, total_volumes: 40 }),
    ];
    const r = applyFilters(items, { ...emptyFilterState(), sort: "volumes" });
    expect(r.map((x) => x.slug)).toEqual(["real", "sum"]);
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
      genreMode: "or" as const,
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
