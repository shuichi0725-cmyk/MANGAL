import { describe, expect, it } from "vitest";
import {
  EXPECTED_COLUMN_COUNT,
  isAdultMadbRecord,
  parseCsvLine,
  parseVolumeNumber,
  rowToMadbCsvRow,
  splitAuthors,
  stripBom,
  type MadbCsvRow,
} from "./madb-csv";

describe("parseCsvLine", () => {
  it("parses simple double-quoted fields", () => {
    expect(parseCsvLine(`"a","b","c"`)).toEqual(["a", "b", "c"]);
  });

  it("handles empty quoted fields", () => {
    expect(parseCsvLine(`"a","","c"`)).toEqual(["a", "", "c"]);
  });

  it("expands escaped quotes (\"\" -> \")", () => {
    // MADB cm104 line example: ...,"湯けむりスナイパー \"\"椿屋\"\"の源編",...
    expect(parseCsvLine(`"湯けむりスナイパー ""椿屋""の源編"`)).toEqual([
      `湯けむりスナイパー "椿屋"の源編`,
    ]);
  });

  it("handles trailing empty field", () => {
    expect(parseCsvLine(`"a","b",""`)).toEqual(["a", "b", ""]);
  });

  it("handles consecutive empty fields", () => {
    expect(parseCsvLine(`"a","","","b"`)).toEqual(["a", "", "", "b"]);
  });

  it("preserves embedded comma inside quoted field", () => {
    expect(parseCsvLine(`"a, b","c"`)).toEqual(["a, b", "c"]);
  });
});

// MADB cm104 から抜粋した実 row。 column 数が 51 で adult / non-adult
// 両方を含む。 rowToMadbCsvRow の挙動確認に使う。
const ADULT_ROW_CELLS = parseCsvLine(
  `"M1110405","9784868120964","表現種別 : テキスト / 表現種別 : 静止画 / 機器種別 : 機器不用 / キャリア種別 : 冊子 / 成年コミック","","","","日本語","","","2026-04-30","","","","","","","","","","マンガ単行本","","1300円","","","","","24234664","Sweet Affection","","スウィート アフェクション","","","21cm","WANIMAGAZINE COMICS SPECIAL","","","","ワニマガジン社","東京","","http://id.ndl.go.jp/class/ndc10/726.1","","","","","","","","","Sweet Affection","成年コミック",""`,
);

const MAINSTREAM_ROW_CELLS = parseCsvLine(
  `"M1110357","9784867949146","表現種別 : テキスト / 表現種別 : 静止画 / 機器種別 : 機器不用 / キャリア種別 : 冊子","","","","日本語","","","2026-04-30","","浅見朝志　＼＼　辻二十日","ツジハツカ","","","","","","","マンガ単行本","","640円","","","","","24234171","え?ギルド内で唯一〈コック〉を極めてる俺をクビですか?@COMIC","","エ ギルドナイ デ ユイイツ コック オ キワメテル オレ オ クビ デスカ アットマーク コミック","","","19cm","コロナ・コミックス","コロナ コミックス","","","TOブックス","東京","","http://id.ndl.go.jp/class/ndc10/726.1","177p","","","1","","","","","え?ギルド内で唯一〈コック〉を極めてる俺をクビですか?@COMIC 1","",""`,
);

describe("rowToMadbCsvRow", () => {
  it("parses cm104 adult sample correctly (= レーティング = 成年コミック)", () => {
    expect(ADULT_ROW_CELLS.length).toBe(EXPECTED_COLUMN_COUNT);
    const row = rowToMadbCsvRow(ADULT_ROW_CELLS);
    expect(row).not.toBeNull();
    expect(row).toMatchObject({
      madbId: "M1110405",
      isbn: "9784868120964",
      publishedAt: "2026-04-30",
      title: "Sweet Affection",
      bookLabel: "WANIMAGAZINE COMICS SPECIAL",
      publisherName: "ワニマガジン社",
      rating: "成年コミック",
    });
    expect(row?.summary).toContain("成年コミック");
  });

  it("parses cm104 mainstream sample correctly (= レーティング 空)", () => {
    expect(MAINSTREAM_ROW_CELLS.length).toBe(EXPECTED_COLUMN_COUNT);
    const row = rowToMadbCsvRow(MAINSTREAM_ROW_CELLS);
    expect(row).not.toBeNull();
    expect(row).toMatchObject({
      madbId: "M1110357",
      isbn: "9784867949146",
      authorName: "浅見朝志　＼＼　辻二十日",
      bookLabel: "コロナ・コミックス",
      publisherName: "TOブックス",
      volumeNumber: "1",
      rating: "",
    });
    expect(row?.title).toContain("ギルド内");
  });

  it("returns null for short rows (= column 数 < 51)", () => {
    expect(rowToMadbCsvRow(["only", "two"])).toBeNull();
  });
});

describe("isAdultMadbRecord", () => {
  const empty = new Set<string>();

  function build(overrides: Partial<MadbCsvRow>): MadbCsvRow {
    return {
      madbId: "M1",
      isbn: "9784000000000",
      summary: "",
      publishedAt: "",
      authorName: "",
      title: "",
      titleKana: "",
      bookLabel: "",
      publisherName: "",
      volumeNumber: "",
      editionLabel: "",
      rating: "",
      ...overrides,
    };
  }

  it("returns 'rating' when レーティング is 成年コミック", () => {
    expect(
      isAdultMadbRecord(build({ rating: "成年コミック" }), empty, empty),
    ).toBe("rating");
  });

  it("returns 'summary' when 概要 contains 成年コミック (rating empty)", () => {
    expect(
      isAdultMadbRecord(
        build({ rating: "", summary: "表現種別 / 成年コミック" }),
        empty,
        empty,
      ),
    ).toBe("summary");
  });

  it("returns 'imprint' when bookLabel matches adultImprints", () => {
    const adultImprints = new Set(["WANIMAGAZINE COMICS SPECIAL"]);
    expect(
      isAdultMadbRecord(
        build({ bookLabel: "WANIMAGAZINE COMICS SPECIAL" }),
        adultImprints,
        empty,
      ),
    ).toBe("imprint");
  });

  it("returns 'publisher' when publisherName matches adultPublishers", () => {
    const adultPublishers = new Set(["ワニマガジン社"]);
    expect(
      isAdultMadbRecord(
        build({ publisherName: "ワニマガジン社" }),
        empty,
        adultPublishers,
      ),
    ).toBe("publisher");
  });

  it("returns null for clean record", () => {
    expect(
      isAdultMadbRecord(
        build({
          title: "うる星やつら",
          publisherName: "小学館",
          bookLabel: "少年サンデーコミックス",
        }),
        empty,
        empty,
      ),
    ).toBeNull();
  });

  it("priority order: rating beats summary/imprint/publisher", () => {
    const adultImprints = new Set(["X"]);
    const adultPublishers = new Set(["Y"]);
    expect(
      isAdultMadbRecord(
        build({
          rating: "成年コミック",
          summary: "成年コミック",
          bookLabel: "X",
          publisherName: "Y",
        }),
        adultImprints,
        adultPublishers,
      ),
    ).toBe("rating");
  });
});

describe("splitAuthors", () => {
  it("splits ＼＼ separated authors with 全角 space", () => {
    expect(splitAuthors("浅見朝志　＼＼　辻二十日")).toEqual([
      "浅見朝志",
      "辻二十日",
    ]);
  });

  it("returns single-element array for single author", () => {
    expect(splitAuthors("諫山創")).toEqual(["諫山創"]);
  });

  it("returns empty array for empty input", () => {
    expect(splitAuthors("")).toEqual([]);
  });

  it("splits 3 authors", () => {
    expect(splitAuthors("A　＼＼　B　＼＼　C")).toEqual(["A", "B", "C"]);
  });
});

describe("parseVolumeNumber", () => {
  it("parses pure digit", () => {
    expect(parseVolumeNumber("1")).toBe(1);
    expect(parseVolumeNumber("19")).toBe(19);
    expect(parseVolumeNumber("100")).toBe(100);
  });

  it("rejects non-digit (= 椿屋の源編 like)", () => {
    expect(parseVolumeNumber("椿屋の源編")).toBeNull();
  });

  it("rejects empty", () => {
    expect(parseVolumeNumber("")).toBeNull();
  });

  it("normalizes 全角 digit", () => {
    expect(parseVolumeNumber("１２")).toBe(12);
  });
});

describe("stripBom", () => {
  it("removes leading U+FEFF", () => {
    expect(stripBom("﻿hello")).toBe("hello");
  });

  it("returns input unchanged when no BOM", () => {
    expect(stripBom("hello")).toBe("hello");
  });

  it("does not strip BOM in the middle", () => {
    expect(stripBom("a﻿b")).toBe("a﻿b");
  });
});
