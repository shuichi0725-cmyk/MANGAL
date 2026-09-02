import { describe, expect, it } from "vitest";
import { fullCover, isEbookCover } from "./coverSlim";

describe("fullCover", () => {
  it("restores the rakuten prefix/suffix from the slim form", () => {
    expect(fullCover("book/cabinet/5757/57572345.gif")).toBe(
      "https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/5757/57572345.gif?_ex=300x300",
    );
  });
  it("keeps a full URL as-is", () => {
    expect(fullCover("https://example.com/a.jpg")).toBe("https://example.com/a.jpg");
  });
  it("is null-safe", () => {
    expect(fullCover(null)).toBeNull();
    expect(fullCover(undefined)).toBeNull();
    expect(fullCover("")).toBeNull();
  });
});

describe("isEbookCover", () => {
  it("detects a Kobo ebook cover in slim form", () => {
    expect(isEbookCover("rakutenkobo-ebooks/cabinet/4011/2000006804011.jpg")).toBe(true);
  });
  it("detects a Kobo ebook cover in full URL form", () => {
    expect(
      isEbookCover(
        "https://thumbnail.image.rakuten.co.jp/@0_mall/rakutenkobo-ebooks/cabinet/4009/2000006804009.jpg?_ex=200x200",
      ),
    ).toBe(true);
  });
  it("does not flag a paper (rakuten books) cover", () => {
    expect(isEbookCover("book/cabinet/5757/57572345.gif")).toBe(false);
    expect(
      isEbookCover("https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/1234/9784088634418.jpg"),
    ).toBe(false);
  });
  it("is null-safe", () => {
    expect(isEbookCover(null)).toBe(false);
    expect(isEbookCover(undefined)).toBe(false);
    expect(isEbookCover("")).toBe(false);
  });
});
