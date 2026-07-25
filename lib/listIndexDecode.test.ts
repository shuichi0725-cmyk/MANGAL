import { describe, expect, it } from "vitest";
import { decodeListIndex } from "./listIndexDecode";
import { searchSlugs } from "./clientSearch";
import type { MangaListItem } from "./schema";

// ★索引v2(2026-07-14)の恒久ガード: fl展開・authorsパック復元・cover復元・検索2段の等価性

const F = ["slug", "title", "title_kana", "subtitle", "cover", "authors", "original_authors", "fl", "_slugfix_new", "popularity"];

function row(over: Record<string, unknown>): unknown[] {
  const base: Record<string, unknown> = {
    slug: "s", title: "t", title_kana: "タイトル", subtitle: null, cover: null,
    authors: [], original_authors: [], fl: null, _slugfix_new: null, popularity: 1,
  };
  return F.map((k) => (k in over ? over[k] : base[k]));
}

describe("decodeListIndex", () => {
  it("flビットフィールドを個別booleanに展開する", () => {
    const [m] = decodeListIndex({ f: F, d: [row({ fl: 1 | 4 | 16 })] });
    expect(m.solo_nonfirst).toBe(true);
    expect(m.cover_gap).toBe(true);
    expect(m._slugfix).toBe(true);
    expect(m.vol_gap).toBeUndefined();
    expect(m._anthology).toBeUndefined();
    expect((m as unknown as { fl?: number }).fl).toBeUndefined();
  });

  it("authorsパック文字列(name\\tkana)を復元する(旧オブジェクト形式も互換)", () => {
    const [m] = decodeListIndex({
      f: F,
      d: [row({ authors: ["石ノ森章太郎\tイシノモリショウタロウ", "名無し"], original_authors: [{ name: "旧形式", kana: "キュウ" }] })],
    });
    expect(m.authors[0]).toEqual({ name: "石ノ森章太郎", kana: "イシノモリショウタロウ" });
    expect(m.authors[1]).toEqual({ name: "名無し" });
    expect(m.original_authors[0]).toEqual({ name: "旧形式", kana: "キュウ" });
  });

  it("cover slim形をフルURLに復元する(300x300統一)", () => {
    const [m] = decodeListIndex({ f: F, d: [row({ cover: "book/cabinet/1234/9784001.jpg" })] });
    expect(m.cover).toBe("https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/1234/9784001.jpg?_ex=300x300");
  });
});

describe("searchSlugs(検索v2)", () => {
  const items = decodeListIndex({
    f: F,
    d: [
      row({ slug: "one-piece", title: "ONE PIECE", title_kana: "ワンピース", authors: ["尾田栄一郎\tオダエイイチロウ"] }),
      row({ slug: "chainsaw-man", title: "チェンソーマン", title_kana: "チェンソーマン", authors: ["藤本タツキ\tフジモトタツキ"] }),
      row({ slug: "tsure-utsu", title: "ツレがうつになりまして。", title_kana: "ツレガウツニナリマシテ", authors: ["細川貂々\tホソカワテンテン"] }),
    ],
  }) as MangaListItem[];

  it("題名(かな)の部分一致", () => {
    expect([...searchSlugs("チェンソー", items)]).toEqual(["chainsaw-man"]);
  });
  it("ローマ字クエリ→かな照合(romaji列なし)", () => {
    expect(searchSlugs("wanpi-su", items).has("one-piece")).toBe(true);
  });
  it("著者照合(題名と併走マージ 2026-07-19)", () => {
    expect(searchSlugs("尾田栄一郎", items).has("one-piece")).toBe(true);
    expect(searchSlugs("ほそかわ", items).has("tsure-utsu")).toBe(true); // ★著者ひらがな入力=ローマ字経由で対応(旧: 未対応)
  });
  it("逐次絞り込みが結果を壊さない(延長→短縮)", () => {
    expect(searchSlugs("ワン", items).has("one-piece")).toBe(true);
    expect(searchSlugs("ワンピ", items).has("one-piece")).toBe(true);
    expect([...searchSlugs("チェンソー", items)]).toEqual(["chainsaw-man"]);
  });
});
