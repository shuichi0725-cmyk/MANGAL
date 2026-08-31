import { describe, expect, it } from "vitest";
import { computeRelated } from "./related";
import type { Manga } from "./schema";

/** computeRelated の穴埋め層(2026-08-31 SEO)の回帰テスト:
 *  孤立頁(強シグナル0件)が同誌/同ジャンル×近い年で充填され、作品間リンク網に入ること。 */

const mk = (over: Partial<Manga>): Manga =>
  ({
    slug: "x",
    title: "作品X",
    authors: [{ name: "著者X" }],
    original_authors: [],
    year_started: 2000,
    magazine: null,
    genres: [],
    ...over,
  }) as unknown as Manga;

describe("computeRelated 穴埋め(同誌/同ジャンル)", () => {
  it("孤立頁(同作者・シリーズ0件)が同誌→同ジャンルで充填される", () => {
    const target = mk({ slug: "target", title: "ぽつん", authors: [{ name: "単発作家" }] as never, magazine: "shonen-jump", genres: ["action"], year_started: 1990 });
    const all = [
      target,
      mk({ slug: "mag-near", title: "別作A", authors: [{ name: "別人A" }] as never, magazine: "shonen-jump", year_started: 1991 }),
      mk({ slug: "mag-far", title: "別作B", authors: [{ name: "別人B" }] as never, magazine: "shonen-jump", year_started: 2020 }),
      mk({ slug: "genre-near", title: "別作C", authors: [{ name: "別人C" }] as never, genres: ["action"], year_started: 1989 }),
      mk({ slug: "other", title: "無関係", authors: [{ name: "別人D" }] as never, magazine: "ribon", genres: ["romance"], year_started: 1990 }),
    ];
    const r = computeRelated(target, all);
    const slugs = r.map((s) => s.m.slug);
    expect(slugs).toContain("mag-near");
    expect(slugs).toContain("genre-near");
    expect(slugs).not.toContain("target"); // 自分自身は出ない
    expect(slugs).not.toContain("other"); // 誌もジャンルも違う作品は出ない
    // 同誌が先・近い年が先
    expect(slugs.indexOf("mag-near")).toBeLessThan(slugs.indexOf("mag-far"));
    expect(r.find((s) => s.m.slug === "mag-near")?.why).toBe("同誌");
    expect(r.find((s) => s.m.slug === "genre-near")?.why).toBe("同ジャンル");
  });

  it("強シグナル(同作者)が先頭を保ち、重複充填しない", () => {
    const target = mk({ slug: "t2", title: "ながい題名の本編", authors: [{ name: "共著者" }] as never, magazine: "big-comic", genres: ["drama"], year_started: 2005 });
    const sameAuthor = mk({ slug: "same-author", title: "全然違う題", authors: [{ name: "共著者" }] as never, magazine: "big-comic", year_started: 2006 });
    const all = [target, sameAuthor,
      mk({ slug: "mag-1", title: "別作", authors: [{ name: "他人" }] as never, magazine: "big-comic", year_started: 2005 })];
    const r = computeRelated(target, all);
    const slugs = r.map((s) => s.m.slug);
    expect(slugs[0]).toBe("same-author");
    expect(r[0].why).toBe("同作者");
    expect(slugs.filter((s) => s === "same-author")).toHaveLength(1); // 充填で二重に出ない
    expect(slugs).toContain("mag-1");
  });

  it("充填は8件で止まる", () => {
    const target = mk({ slug: "t3", title: "単発", authors: [{ name: "孤独" }] as never, magazine: "m", year_started: 2000 });
    const all = [target, ...Array.from({ length: 20 }, (_, i) =>
      mk({ slug: `f${i}`, title: `埋め${i}`, authors: [{ name: `人${i}` }] as never, magazine: "m", year_started: 1990 + i }))];
    expect(computeRelated(target, all).length).toBe(8);
  });
});
