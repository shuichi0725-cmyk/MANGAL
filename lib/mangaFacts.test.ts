import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { KIND_COLOR } from "../app/compass/compass";
import { manyPeople, stackPeople } from "./mangaFacts";

describe("作品頁の基本情報欄(D3 コマ割り)", () => {
  it("写植箱の色 = 羅針盤の糸の色(components/manga-facts.css と KIND_COLOR が食い違わない)", () => {
    const css = readFileSync(new URL("../components/manga-facts.css", import.meta.url), "utf8");
    const pick = (name: string) => css.match(new RegExp(`--mf-${name}:\\s*(#[0-9a-fA-F]{6})`))?.[1]?.toLowerCase();
    expect(pick("au")).toBe(KIND_COLOR.author.toLowerCase());
    expect(pick("mg")).toBe(KIND_COLOR.mag.toLowerCase());
    expect(pick("yr")).toBe(KIND_COLOR.year.toLowerCase());
    expect(pick("el")).toBe(KIND_COLOR.elem.toLowerCase());
    expect(pick("gn")).toBe(KIND_COLOR.genre.toLowerCase());
  });

  it("ふつうの作品は斜めの2コマ(シャングリラ・フロンティア / ベルセルク)", () => {
    expect(stackPeople(["不二涼介"], ["硬梨菜"], [])).toBe(false);
    expect(stackPeople(["三浦建太郎"], [], [])).toBe(false);
    expect(stackPeople(["大場つぐみ", "小畑健"], [], [])).toBe(false);
    expect(stackPeople(["近藤浩一路"], [], [{ role: "監修", names: ["神野正史"] }])).toBe(false);
  });

  it("著者が3人以上・名前が長い・原作やその他が長い時は縦に積む", () => {
    expect(stackPeople(["A", "B", "C"], [], [])).toBe(true);
    expect(stackPeople(["ながいなまえのさっかさん", "もうひとり"], [], [])).toBe(true);
    expect(
      stackPeople(["作画者"], ["原作者いちろう"], [{ role: "キャラクター原案", names: ["原案者"] }]),
    ).toBe(true);
  });

  it("4人以上は大きい字をやめる(アンソロジー)", () => {
    expect(manyPeople(["A", "B", "C"])).toBe(false);
    expect(manyPeople(["A", "B", "C", "D"])).toBe(true);
  });
});
