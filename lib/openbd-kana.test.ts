import { describe, expect, it } from "vitest";
import { cleanCollationKey, katakanaToHiragana } from "./openbd-kana";

describe("katakanaToHiragana", () => {
  it("converts full-width katakana to hiragana", () => {
    expect(katakanaToHiragana("カタカナ")).toBe("かたかな");
  });

  it("preserves 「ー」 (chōonpu) since it is shared", () => {
    expect(katakanaToHiragana("グローリー")).toBe("ぐろーりー");
  });

  it("preserves non-katakana characters", () => {
    expect(katakanaToHiragana("Astro Boy")).toBe("Astro Boy");
    expect(katakanaToHiragana("123")).toBe("123");
  });

  it("handles small katakana (ァィゥェォャュョ)", () => {
    expect(katakanaToHiragana("ファミリー")).toBe("ふぁみりー");
    expect(katakanaToHiragana("ジョー")).toBe("じょー");
  });
});

describe("cleanCollationKey", () => {
  it("returns null for empty / null input", () => {
    expect(cleanCollationKey("")).toBeNull();
    expect(cleanCollationKey(null)).toBeNull();
    expect(cleanCollationKey(undefined)).toBeNull();
  });

  it("strips subtitle after ':' separator", () => {
    expect(cleanCollationKey("ブレイク タイム : Manga meets music")).toBe(
      "ぶれいくたいむ",
    );
  });

  it("removes whitespace between word boundaries", () => {
    expect(cleanCollationKey("ハチビット カノジョ")).toBe("はちびっとかのじょ");
    expect(cleanCollationKey("アカメカブトトカゲチャン")).toBe(
      "あかめかぶととかげちゃん",
    );
  });

  it("converts katakana to hiragana", () => {
    expect(cleanCollationKey("グローリー")).toBe("ぐろーりー");
  });

  it("returns null for English-only input", () => {
    expect(cleanCollationKey("Manga meets music")).toBeNull();
  });

  it("handles long anthology titles with subtitle", () => {
    const raw =
      "アクヤク レイジョウ ミタイ ニ ダンザイ サレソウ : アンソロジー コミック";
    expect(cleanCollationKey(raw)).toBe(
      "あくやくれいじょうみたいにだんざいされそう",
    );
  });
});
