import { describe, expect, it } from "vitest";
import { formatReleaseDate, yearStatusLabel } from "./format";
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
  publisher: "shueisha",
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
