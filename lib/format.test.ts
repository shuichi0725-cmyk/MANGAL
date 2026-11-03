import { describe, expect, it } from "vitest";
import { creditNames, formatReleaseDate, kanaSameAsTitle, yearStatusLabel } from "./format";
import type { Manga } from "./schema";

const base: Manga = {
  slug: "x",
  title: "X",
  title_kana: "X",
  title_romaji: "x",
  year_started: 1997,
  year_ended: null,
  status: "ongoing",
  authors: [{ name: "A", role: "writer_artist" }],
  original_authors: [],
  credits: [],
  publisher: "shueisha",
  publishers: ["shueisha"],
  magazine: null,
  demographic: "shounen",
  genres: ["action"],
  synopsis: "",
  editions: [{ type: "standard", label: "通常版", volumes: [{ number: 1 }] }],
};

describe("yearStatusLabel", () => {
  it("連載中は終端なしで '連載中'", () => {
    expect(yearStatusLabel({ ...base, status: "ongoing" })).toBe("1997〜 連載中");
  });
  it("完結は終了年と '完結'", () => {
    expect(
      yearStatusLabel({ ...base, status: "completed", year_ended: 2014 }),
    ).toBe("1997〜2014 完結");
  });
  it("休載中は終了年が無くてもラベル表示", () => {
    expect(yearStatusLabel({ ...base, status: "hiatus" })).toBe("1997〜 休載中");
  });
  it("始めと終わりが同じ年は年を1つだけ('1997〜1997 完結'にしない)", () => {
    expect(yearStatusLabel({ ...base, status: "completed", year_ended: 1997 })).toBe("1997 完結");
    expect(yearStatusLabel({ ...base, status: "hiatus", year_ended: 1997 })).toBe("1997 休載中");
  });
});

describe("kanaSameAsTitle", () => {
  it.each([
    ["ベルセルク", "ベルセルク"],
    ["あしたのジョー", "アシタノジョー"],
    ["タンク・タンクロー", "タンクタンクロー"],
    ["ビバ!バレーボール", "ビババレーボール"],
    ["ｶﾀｶﾅ", "カタカナ"],
  ])("%s / %s は同じ読み=出さない", (t, k) => {
    expect(kanaSameAsTitle(t, k)).toBe(true);
  });
  it.each([
    ["ONE PIECE", "ワンピース"],
    ["進撃の巨人", "シンゲキノキョジン"],
    ["こんにちは", "コンニチワ"],
    ["ゲームセンターあらし", "ゲームセンターアラシー"],
  ])("%s / %s は読みが違う=出す", (t, k) => {
    expect(kanaSameAsTitle(t, k)).toBe(false);
  });
  it("空なら false(=従来どおりの扱い)", () => {
    expect(kanaSameAsTitle("X", "")).toBe(false);
    expect(kanaSameAsTitle(null, "X")).toBe(false);
  });
});

describe("creditNames", () => {
  it("原作者 → 作画 の順", () => {
    expect(creditNames({ authors: [{ name: "村田雄介" }], original_authors: [{ name: "ONE" }] })).toEqual(["ONE", "村田雄介"]);
  });
  it("原作者が居なければ作画だけ(従来と同じ)", () => {
    expect(creditNames({ authors: [{ name: "三浦建太郎" }], original_authors: [] })).toEqual(["三浦建太郎"]);
  });
  it("同じ名前は1回だけ・空や欠けは無視", () => {
    expect(creditNames({ authors: [{ name: "A" }, { name: "" }], original_authors: [{ name: "A" }] })).toEqual(["A"]);
    expect(creditNames({})).toEqual([]);
  });
});

describe("formatReleaseDate", () => {
  it.each([
    ["1997-12-24", "1997.12.24"],
    ["1997-12", "1997.12"],
    ["1997", "1997"],
    [null, ""],
    [undefined, ""],
  ])("%s -> %s", (input, expected) => {
    expect(formatReleaseDate(input)).toBe(expected);
  });
});
