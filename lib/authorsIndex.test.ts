import { describe, expect, it } from "vitest";
import { parsePart, splitAuthors, type AuthorIndexEntry } from "./authorsIndex";

const A = (name: string, kana: string | null, key = name): AuthorIndexEntry => ({ key, name, kana, n: 1 });

describe("splitAuthors", () => {
  it("行ごとに振り分け、行内は入力順のまま頁に割る", () => {
    const list = [A("相川", "アイカワ"), A("青木", "アオキ"), A("井上", "イノウエ"), A("加藤", "カトウ"), A("CLAMP", null)];
    const r = splitAuthors(list, 2);
    expect(r.parts["a-1"].map((a) => a.name)).toEqual(["相川", "青木"]);
    expect(r.parts["a-2"].map((a) => a.name)).toEqual(["井上"]);
    expect(r.parts["ka-1"].map((a) => a.name)).toEqual(["加藤"]);
    expect(r.parts["other-1"].map((a) => a.name)).toEqual(["CLAMP"]);
    expect(r.gyo.find((g) => g.key === "a")).toMatchObject({ count: 3, pages: 2 });
    expect(r.gyo.find((g) => g.key === "sa")).toMatchObject({ count: 0, pages: 0 });
    expect(r.parts["sa-1"]).toBeUndefined();
  });

  it("全員がどこか1頁にだけ載る(取りこぼし・重複なし)", () => {
    const list = Array.from({ length: 1234 }, (_, i) => A(`n${i}`, i % 3 ? "サトウ" : "ワタナベ", `k${i}`));
    const r = splitAuthors(list, 300);
    const keys = Object.values(r.parts).flat().map((a) => a.key);
    expect(keys.length).toBe(1234);
    expect(new Set(keys).size).toBe(1234);
    expect(Object.values(r.parts).every((rows) => rows.length > 0 && rows.length <= 300)).toBe(true);
  });

  it("ヴ はあ行、カナ無しは名前の頭で判定", () => {
    const r = splitAuthors([A("ヴィクター", "ヴィクター"), A("さくら", null)], 10);
    expect(r.parts["a-1"].map((a) => a.name)).toEqual(["ヴィクター"]);
    expect(r.parts["sa-1"].map((a) => a.name)).toEqual(["さくら"]);
  });
});

describe("parsePart", () => {
  it("行keyと頁番号に分ける", () => {
    expect(parsePart("ka-3")).toEqual({ gyoKey: "ka", page: 3 });
    expect(parsePart("other-1")).toEqual({ gyoKey: "other", page: 1 });
  });
  it("不正な形は null", () => {
    expect(parsePart("ka")).toBeNull();
    expect(parsePart("ka-0")).toBeNull();
    expect(parsePart("ka-x")).toBeNull();
    expect(parsePart("-1")).toBeNull();
  });
});
