import { describe, expect, it } from "vitest";
import { searchSlugs } from "./clientSearch";
import type { MangaListItem } from "./schema";

// ★2026-07-19 実害の回帰テスト: 作家名が題に入る作家(高橋留美子劇場型)で
//   著者検索が沈黙しない(題名ヒットと著者ヒットが併走マージされる)こと。
const items = [
  { slug: "takahashi-rumiko-gekijou", title: "高橋留美子劇場", title_kana: "タカハシルミコゲキジョウ",
    authors: [{ name: "高橋留美子", kana: "タカハシルミコ" }] },
  { slug: "urusei-yatsura", title: "うる星やつら", title_kana: "ウルセイヤツラ",
    authors: [{ name: "高橋留美子", kana: "タカハシルミコ" }] },
  { slug: "inuyasha", title: "犬夜叉", title_kana: "イヌヤシャ",
    authors: [{ name: "高橋留美子", kana: "タカハシルミコ" }] },
  { slug: "five-star-stories", title: "ファイブスター物語", title_kana: "ファイブスターストーリーズ",
    authors: [{ name: "永野護", kana: "ナガノマモル" }] },
] as unknown as MangaListItem[];

describe("searchSlugs 著者×題名の併走マージ", () => {
  it("題名に作家名が入る作家でも著者作品が全部出る(高橋留美子型)", () => {
    const got = searchSlugs("高橋留美子", items);
    expect(got).toEqual(new Set(["takahashi-rumiko-gekijou", "urusei-yatsura", "inuyasha"]));
  });
  it("題名ヒット0の作家は従来どおり著者で出る(永野護型)", () => {
    expect(searchSlugs("永野護", items)).toEqual(new Set(["five-star-stories"]));
  });
  it("著者かな入力でも引ける", () => {
    const got = searchSlugs("たかはしるみこ", items);
    expect(got.has("inuyasha")).toBe(true);
  });
  it("題名検索は従来どおり", () => {
    expect(searchSlugs("犬夜叉", items)).toEqual(new Set(["inuyasha"]));
  });
});
