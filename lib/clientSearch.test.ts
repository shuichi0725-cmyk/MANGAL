import { afterEach, describe, expect, it } from "vitest";
import { __setAltIndexForTest, searchSlugs } from "./clientSearch";
import type { MangaListItem } from "./schema";

// ★2026-07-19 実害の回帰テスト: 作家名が題に入る作家(高橋留美子劇場型)で
//   著者検索が沈黙しない(題名ヒットと著者ヒットが併走マージされる)こと。
// ★2026-07-21 追加: 複数語AND / かな⇄カナ畳み込み / alt常時マージ。
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

afterEach(() => {
  __setAltIndexForTest(null); // altを他テストへ漏らさない
});

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

describe("searchSlugs 複数語AND(2026-07-21)", () => {
  it("題名+著者の2語で絞れる(ワンピース 尾田型)", () => {
    expect(searchSlugs("高橋留美子 うる星", items)).toEqual(new Set(["urusei-yatsura"]));
  });
  it("語順を入れ替えても同じ", () => {
    expect(searchSlugs("うる星 高橋留美子", items)).toEqual(new Set(["urusei-yatsura"]));
  });
  it("両語を満たさない作品は出ない(AND)", () => {
    expect(searchSlugs("永野護 犬夜叉", items)).toEqual(new Set());
  });
  it("全角スペース区切りでも効く", () => {
    expect(searchSlugs("高橋留美子　うる星", items)).toEqual(new Set(["urusei-yatsura"]));
  });
});

describe("searchSlugs かな⇄カタカナ畳み込み(2026-07-21)", () => {
  it("ひらがなクエリがカタカナのよみに直接当たる", () => {
    expect(searchSlugs("うるせいやつら", items)).toEqual(new Set(["urusei-yatsura"]));
  });
  it("カタカナクエリがひらがな題に当たる", () => {
    expect(searchSlugs("ウルせいヤツラ", items)).toEqual(new Set(["urusei-yatsura"]));
  });
});

describe("searchSlugs alt(別名・英題)常時マージ(2026-07-21)", () => {
  it("altで引ける(英題略称型)", () => {
    __setAltIndexForTest({ "five-star-stories": ["FSS", "The Five Star Stories"] });
    expect(searchSlugs("fss", items)).toEqual(new Set(["five-star-stories"]));
  });
  it("題名ヒットが他にあってもaltがマージされる(旧: ヒット0の時だけの取りこぼし)", () => {
    __setAltIndexForTest({ "five-star-stories": ["犬夜叉ではない別名"] });
    const got = searchSlugs("犬夜叉", items);
    expect(got).toEqual(new Set(["inuyasha", "five-star-stories"]));
  });
  it("alt語+著者語のANDが成立する", () => {
    __setAltIndexForTest({ "five-star-stories": ["FSS"] });
    expect(searchSlugs("fss 永野", items)).toEqual(new Set(["five-star-stories"]));
  });
});
