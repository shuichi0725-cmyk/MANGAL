import { describe, expect, it } from "vitest";
import {
  type Book,
  castSpell,
  describeSpell,
  makeSpellbook,
  setExclusive,
  toggleClause,
  type Sample,
  sampleToBooks,
} from "./spell";
import sampleFile from "./sample-books.json";

const GENRES = [
  { key: "fantasy", name: "ファンタジー" },
  { key: "horror", name: "ホラー" },
  { key: "4-koma", name: "4コマ漫画" },
  { key: "sci-fi", name: "SF" },
];
const book = makeSpellbook(GENRES);

function b(p: Partial<Book> & { slug: string }): Book {
  return { title: p.slug, kana: "", cover: null, year: 2000, first: "", vols: 10, status: "completed", genres: [], pop: 0, ...p };
}

const SHELF: Book[] = [
  b({ slug: "a", title: "ワンピース", kana: "ワンピース", year: 1997, vols: 110, status: "ongoing", genres: ["fantasy"], pop: 100 }),
  b({ slug: "b", title: "寄生獣", kana: "キセイジュウ", year: 1988, vols: 10, genres: ["horror", "sci-fi"], pop: 50 }),
  b({ slug: "c", title: "よつばと!", kana: "ヨツバト", year: 2003, vols: 15, status: "ongoing", genres: ["4-koma"], pop: 70 }),
  b({ slug: "d", title: "短編集", kana: "タンペンシュウ", year: 1995, vols: 1, genres: ["fantasy", "horror"], pop: 10 }),
  b({ slug: "e", title: "年不明", kana: "ネンフメイ", year: null, vols: 0, genres: [], pop: 5 }),
];

const slugs = (text: string, cap = 99) =>
  castSpell(SHELF, book.parse(text), () => cap).groups.flatMap((g) => g.books.map((x) => x.slug));

describe("呪文の解釈", () => {
  it("ジャンルは表示名・key・# 付き・全角でも同じ key", () => {
    for (const t of ["ファンタジー", "fantasy", "#ファンタジー", "ＦＡＮＴＡＳＹ"]) {
      const tok = book.parseToken(t);
      expect(tok?.type === "clause" && tok.clause.key).toBe("genre:fantasy");
    }
    const k = book.parseToken("4コマ");
    expect(k?.type === "clause" && k.clause.key).toBe("genre:4-koma");
  });

  it("年代の書き方ゆれ(90年代/1990年代/1990s)は同じ key", () => {
    const keys = ["90年代", "1990年代", "1990s", "1990〜1999"].map((t) => {
      const tok = book.parseToken(t);
      return tok?.type === "clause" ? tok.clause.key : null;
    });
    expect(new Set(keys)).toEqual(new Set(["year:1990-1999"]));
    const t20 = book.parseToken("20年代");
    expect(t20?.type === "clause" && t20.clause.key).toBe("year:2020-2029");
  });

  it("巻数: 以上/以下/範囲/ちょうど", () => {
    expect(slugs("50巻以上")).toEqual(["a"]);
    expect(slugs("1巻")).toEqual(["d"]);
    expect(slugs("10-15巻")).toEqual(["c", "b"]);
    expect(slugs("5巻以下")).toEqual(["d"]);
  });

  it("ジャンル=かつ / 年代=または / 否定", () => {
    expect(slugs("ファンタジー ホラー")).toEqual(["d"]);
    expect(slugs("1980年代 1990年代")).toEqual(["a", "b", "d"]);
    expect(slugs("-ホラー")).toEqual(["a", "c", "e"]);
    expect(slugs("完結 -1巻")).toEqual(["b", "e"]);
  });

  it("未知の語は題名照合(ひらがなでもカタカナ題に当たる)", () => {
    expect(slugs("わんぴ")).toEqual(["a"]);
    expect(slugs("「寄生」")).toEqual(["b"]);
  });

  it("並びと集め", () => {
    expect(slugs("古い順")).toEqual(["b", "d", "a", "c", "e"]);
    expect(slugs("巻数順")[0]).toBe("a");
    const r = castSpell(SHELF, book.parse("状態別"), () => 99);
    expect(r.groups.map((g) => g.label)).toEqual(["連載中", "完結"]);
    const d = castSpell(SHELF, book.parse("年代別 新しい順"), () => 99);
    expect(d.groups.map((g) => g.label)).toEqual(["2000年代", "1990年代", "1980年代", "年不明"]);
  });

  it("棚ごとの上限: 描くのは cap 冊・total は全数", () => {
    const r = castSpell(SHELF, book.parse(""), () => 2);
    expect(r.matched).toBe(5);
    expect(r.groups[0].total).toBe(5);
    expect(r.groups[0].books).toHaveLength(2);
  });

  it("解釈文は ∧ と ∨ で結合規則を見せる", () => {
    expect(describeSpell(book.parse("ホラー 80年代 90年代 -完結"))).toBe(
      "ホラー ∧ (1980年代 ∨ 1990年代) ∧ ¬完結 ／ 人気順",
    );
  });
});

describe("呪文文字列の編集(チップ)", () => {
  it("点いているチップは書き方が違っても消せる・表記は残す", () => {
    expect(toggleClause("ONE 90年代", "1990年代", book)).toBe("ONE");
    expect(toggleClause("ONE", "1990年代", book)).toBe("ONE 1990年代");
  });
  it("並びは1つだけ(既定の人気順は語を置かない)", () => {
    expect(setExclusive("ホラー 古い順", "sort", "巻数順", book)).toBe("ホラー 巻数順");
    expect(setExclusive("ホラー 古い順", "sort", "", book)).toBe("ホラー");
  });
});

describe("見本データから書架へ", () => {
  const sample = (d: unknown[][], f: string[] = ["slug", "title", "kana", "cover", "year", "first", "vols", "status", "genres", "pop"]) =>
    ({ src: "t", n: d.length, f, d }) as Sample;

  it("slug 重複は先勝ち・年0は不明扱い・書影は full URL に戻す", () => {
    const row = (slug: string, y: number) => [slug, slug, "", "book/cabinet/1/2.jpg", y, "", 1, "ongoing", [], 0];
    const out = sampleToBooks(sample([row("x", 0), row("x", 2000), row("y", 1999)]));
    expect(out.map((o) => [o.slug, o.year])).toEqual([["x", null], ["y", 1999]]);
    expect(out[0].cover).toBe("https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/1/2.jpg?_ex=300x300");
  });

  it("列順が生成スクリプトとずれていたら黙って化けずに止まる", () => {
    expect(() => sampleToBooks(sample([], ["title", "slug"]))).toThrow(/列順/);
  });

  it("同梱の見本(sample-books.json)は1,500作前後・全作に書影・人気の降順・slug 一意", () => {
    const books = sampleToBooks(sampleFile as unknown as Sample);
    expect(books.length).toBe((sampleFile as unknown as Sample).n);
    expect(books.length).toBeGreaterThanOrEqual(1000);
    expect(books.every((x) => x.cover?.startsWith("http"))).toBe(true);
    expect(books.every((x, i) => i === 0 || books[i - 1].pop >= x.pop)).toBe(true);
    const genreKeys = new Set(books.flatMap((x) => x.genres));
    expect([...genreKeys].every((k) => /^[a-z0-9-]+$/.test(k))).toBe(true);
  });
});
