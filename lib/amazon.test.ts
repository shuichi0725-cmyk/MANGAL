import { describe, expect, it } from "vitest";
import { amazonDpUrlFromIsbn13, amazonSearchUrl, isbn13ToIsbn10 } from "./amazon";

describe("isbn13ToIsbn10 (紙のASIN=ISBN-10。アソシエイト/dp/直リンクの土台 2026-07-29)", () => {
  it("チェックデジット再計算が正しい(HUNTER×HUNTER 1巻)", () => {
    expect(isbn13ToIsbn10("9784088725710")).toBe("4088725719");
  });
  it("チェックデジットX(合成例: body=000000006はsum=12→12%11=1→check=10=X)", () => {
    expect(isbn13ToIsbn10("9780000000064")).toBe("000000006X");
  });
  it("979系は変換不能でnull(ISBN-10が存在しない)", () => {
    expect(isbn13ToIsbn10("9791234567896")).toBeNull();
  });
  it("不正入力はnull", () => {
    expect(isbn13ToIsbn10("")).toBeNull();
    expect(isbn13ToIsbn10(null)).toBeNull();
  });
});

describe("Amazonリンク生成", () => {
  it("dp直リンクにtagが付く", () => {
    const u = amazonDpUrlFromIsbn13("9784088725710", "mangal08-22");
    expect(u).toBe("https://www.amazon.co.jp/dp/4088725719?tag=mangal08-22");
  });
  it("検索リンクにもtagが付く", () => {
    const u = amazonSearchUrl("ONE PIECE 全巻", "mangal08-22");
    expect(u).toContain("tag=mangal08-22");
    expect(u).toContain("i=stripbooks");
  });
  it("tag未設定なら素リンク(開発/preview fallback)", () => {
    expect(amazonDpUrlFromIsbn13("9784088725710", "")).toBe("https://www.amazon.co.jp/dp/4088725719");
  });
});
