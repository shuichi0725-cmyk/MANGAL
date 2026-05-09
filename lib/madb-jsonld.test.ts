import { describe, expect, it } from "vitest";
import {
  extractMadbId,
  extractRecord,
  findKanaLiteral,
  firstString,
  flattenStringArray,
  isAdultMadbRecord,
  parseVolumeNumber,
  splitMadbLiteral,
  type MadbJsonLdRecord,
  type MadbRecord,
} from "./madb-jsonld";

describe("flattenStringArray", () => {
  it("returns empty for undefined / null", () => {
    expect(flattenStringArray(undefined)).toEqual([]);
  });

  it("returns single string in array", () => {
    expect(flattenStringArray("Hello")).toEqual(["Hello"]);
  });

  it("flattens [string, {@value, @language}] (= 漢字 + ヨミ pair)", () => {
    // default: 漢字 のみ取り出す
    expect(
      flattenStringArray([
        "ほしのなつみ",
        { "@value": "ホシノナツミ", "@language": "ja-hrkt" },
      ]),
    ).toEqual(["ほしのなつみ"]);
  });

  it("keeps localized string when keepLocalized=true", () => {
    expect(
      flattenStringArray(
        [
          "ほしのなつみ",
          { "@value": "ホシノナツミ", "@language": "ja-hrkt" },
        ],
        { keepLocalized: true },
      ),
    ).toEqual(["ほしのなつみ", "ホシノナツミ"]);
  });

  it("flattens multi-author (= 共著) with shared kana", () => {
    // MADB JSON-LD: array に 漢字 N 個 + ヨミ 1 個 (= 連続表記)。
    // 漢字のみ取り出す = ["史村翔", "新谷かおる"]
    expect(
      flattenStringArray([
        "史村翔",
        "新谷かおる",
        { "@value": "シンタニカオル", "@language": "ja-hrkt" },
      ]),
    ).toEqual(["史村翔", "新谷かおる"]);
  });

  it("ignores @id reference objects", () => {
    expect(
      flattenStringArray({ "@id": "https://example.com/id/X1" }),
    ).toEqual([]);
  });

  it("filters out empty strings", () => {
    expect(
      flattenStringArray([
        "",
        "abc",
        { "@value": "", "@language": "ja-hrkt" },
      ]),
    ).toEqual(["abc"]);
  });
});

describe("firstString", () => {
  it("returns first 漢字 string from mixed array", () => {
    expect(
      firstString([
        "GENESYS COMICS",
        { "@value": "", "@language": "ja-hrkt" },
      ]),
    ).toBe("GENESYS COMICS");
  });

  it("returns empty for empty / undefined", () => {
    expect(firstString(undefined)).toBe("");
    expect(firstString([])).toBe("");
  });
});

describe("splitMadbLiteral", () => {
  it("strips ∥-separated kana, full-width spaces", () => {
    expect(splitMadbLiteral("集英社　∥　シュウエイシャ")).toBe("集英社");
    expect(splitMadbLiteral("白夜書房　∥　ビャクヤ ショボウ")).toBe("白夜書房");
    expect(splitMadbLiteral("祥伝社　∥　ショウデンシャ")).toBe("祥伝社");
  });

  it("handles half-width spaces and missing spaces around ∥", () => {
    expect(splitMadbLiteral("集英社 ∥ シュウエイシャ")).toBe("集英社");
    expect(splitMadbLiteral("集英社∥シュウエイシャ")).toBe("集英社");
  });

  it("returns input unchanged when no ∥", () => {
    expect(splitMadbLiteral("集英社")).toBe("集英社");
    expect(splitMadbLiteral("KADOKAWA")).toBe("KADOKAWA");
  });

  it("returns empty for empty input", () => {
    expect(splitMadbLiteral("")).toBe("");
  });

  it("trims trailing whitespace", () => {
    expect(splitMadbLiteral("集英社 　")).toBe("集英社");
  });
});

describe("findKanaLiteral", () => {
  it("returns @value when @language=ja-hrkt", () => {
    expect(
      findKanaLiteral([
        "キジトラ猫の小梅さん",
        { "@value": "キジトラネコ ノ コウメサン", "@language": "ja-hrkt" },
      ]),
    ).toBe("キジトラネコ ノ コウメサン");
  });

  it("returns empty for plain string field", () => {
    expect(findKanaLiteral("just a string")).toBe("");
  });

  it("returns empty when no ja-hrkt object", () => {
    expect(
      findKanaLiteral([
        "abc",
        { "@value": "ABC", "@language": "en" },
      ]),
    ).toBe("");
  });
});

describe("extractMadbId", () => {
  it("extracts suffix after /id/", () => {
    expect(
      extractMadbId("https://mediaarts-db.artmuseums.go.jp/id/M1032568"),
    ).toBe("M1032568");
  });

  it("returns empty for missing /id/", () => {
    expect(extractMadbId("https://example.com/")).toBe("");
  });

  it("returns empty for empty author URI (= MADB の漢字なし record)", () => {
    expect(
      extractMadbId("https://mediaarts-db.artmuseums.go.jp/id/"),
    ).toBe("");
  });

  it("returns empty for undefined", () => {
    expect(extractMadbId(undefined)).toBe("");
  });
});

// MADB cm101 JSON-LD から抜粋した実 record。 mainstream / adult / multi-author
// の 3 件を inline JSON で書く。 unzip した metadata101.json の最初の方
// から取った。

const MAINSTREAM_RAW: MadbJsonLdRecord = {
  "@id": "https://mediaarts-db.artmuseums.go.jp/id/M1032568",
  "@type": "class:MangaBook",
  "rdfs:label": "キジトラ猫の小梅さん 25",
  "schema:contentRating": "",
  "schema:isbn": "9784785977382",
  "schema:datePublished": "2024-08-06",
  "schema:description":
    "表現種別 : テキスト / 表現種別 : 静止画 / 機器種別 : 機器不用 / キャリア種別 : 冊子",
  "schema:name": [
    "キジトラ猫の小梅さん",
    { "@value": "キジトラネコ ノ コウメサン", "@language": "ja-hrkt" },
  ],
  "schema:creator": [
    "ほしのなつみ",
    { "@value": "ホシノナツミ", "@language": "ja-hrkt" },
  ],
  "schema:brand": [
    "ねこぱんちコミックス",
    { "@value": "ネコ パンチ コミックス", "@language": "ja-hrkt" },
  ],
  "schema:publisher": "少年画報社",
  "schema:volumeNumber": "25",
};

const ADULT_RAW: MadbJsonLdRecord = {
  "@id": "https://mediaarts-db.artmuseums.go.jp/id/M1032618",
  "@type": "class:MangaBook",
  "rdfs:label": "生贄の放課後",
  "schema:alternativeHeadline": "気の強い転校生を責め堕とす",
  "schema:contentRating": "成年コミック",
  "schema:isbn": "9784865377347",
  "schema:datePublished": "2024-04-06",
  "schema:description":
    "表現種別 : テキスト / 表現種別 : 静止画 / 機器種別 : 機器不用 / キャリア種別 : 冊子 / 成年コミック",
  "schema:name": [
    "生贄の放課後",
    {
      "@value": "イケニエ ノ ホウカゴ : キ ノ ツヨイ テンコウセイ オ セメオトス",
      "@language": "ja-hrkt",
    },
  ],
  "schema:creator": ["", { "@value": "", "@language": "ja-hrkt" }],
  "schema:brand": [
    "GENESYS COMICS",
    { "@value": "", "@language": "ja-hrkt" },
  ],
  "schema:publisher": ["[頒布]鉄人社", "ゲネシス"],
  "schema:volumeNumber": "",
};

const MULTI_AUTHOR_RAW: MadbJsonLdRecord = {
  "@id": "https://mediaarts-db.artmuseums.go.jp/id/M99999",
  "@type": "class:MangaBook",
  "schema:contentRating": "",
  "schema:alternativeHeadline": "完全版",
  "schema:isbn": "9784091234567",
  "schema:datePublished": "2010-05-01",
  "schema:description": "表現種別 : テキスト / ...",
  "schema:name": [
    "エリア88",
    { "@value": "エリア ハチジュウハチ", "@language": "ja-hrkt" },
  ],
  // 共著: 漢字 が 2 つ並ぶ array
  "schema:creator": [
    "史村翔",
    "新谷かおる",
    { "@value": "シンタニカオル", "@language": "ja-hrkt" },
  ],
  "schema:brand": "MFコミックス",
  "schema:publisher": "メディアファクトリー",
  "schema:volumeNumber": "1",
};

describe("extractRecord", () => {
  it("extracts mainstream record correctly", () => {
    const rec = extractRecord(MAINSTREAM_RAW);
    expect(rec).toMatchObject({
      madbId: "M1032568",
      isbn: "9784785977382",
      rating: "",
      title: "キジトラ猫の小梅さん",
      titleKana: "キジトラネコ ノ コウメサン",
      subtitle: "",
      authors: ["ほしのなつみ"],
      brand: "ねこぱんちコミックス",
      publisher: "少年画報社",
      volumeNumber: "25",
      datePublished: "2024-08-06",
    });
  });

  it("extracts adult record correctly (= rating filled, brand set)", () => {
    const rec = extractRecord(ADULT_RAW);
    expect(rec).toMatchObject({
      madbId: "M1032618",
      rating: "成年コミック",
      title: "生贄の放課後",
      subtitle: "気の強い転校生を責め堕とす",
      authors: [],
      brand: "GENESYS COMICS",
      publisher: "[頒布]鉄人社",
    });
    expect(rec?.description).toContain("成年コミック");
  });

  it("extracts multi-author record (= 共著 array flattened)", () => {
    const rec = extractRecord(MULTI_AUTHOR_RAW);
    expect(rec).toMatchObject({
      madbId: "M99999",
      title: "エリア88",
      subtitle: "完全版",
      authors: ["史村翔", "新谷かおる"],
      brand: "MFコミックス",
      publisher: "メディアファクトリー",
    });
  });

  it("returns null for record without @id", () => {
    expect(extractRecord({} as MadbJsonLdRecord)).toBeNull();
  });
});

describe("isAdultMadbRecord", () => {
  const empty = new Set<string>();

  function build(overrides: Partial<MadbRecord>): MadbRecord {
    return {
      madbId: "M1",
      isbn: "9784000000000",
      rating: "",
      description: "",
      title: "",
      titleKana: "",
      subtitle: "",
      authors: [],
      brand: "",
      publisher: "",
      datePublished: "",
      volumeNumber: "",
      ...overrides,
    };
  }

  it("returns 'rating' when contentRating is 成年コミック", () => {
    expect(
      isAdultMadbRecord(build({ rating: "成年コミック" }), empty, empty),
    ).toBe("rating");
  });

  it("returns 'description' when description contains 成年コミック (rating empty)", () => {
    expect(
      isAdultMadbRecord(
        build({ rating: "", description: "表現種別 / 成年コミック" }),
        empty,
        empty,
      ),
    ).toBe("description");
  });

  it("returns 'imprint' when brand matches adultImprints", () => {
    const adultImprints = new Set(["GENESYS COMICS"]);
    expect(
      isAdultMadbRecord(
        build({ brand: "GENESYS COMICS" }),
        adultImprints,
        empty,
      ),
    ).toBe("imprint");
  });

  it("returns 'publisher' when publisher matches adultPublishers", () => {
    const adultPublishers = new Set(["ゲネシス"]);
    expect(
      isAdultMadbRecord(
        build({ publisher: "ゲネシス" }),
        empty,
        adultPublishers,
      ),
    ).toBe("publisher");
  });

  it("returns null for clean record", () => {
    expect(
      isAdultMadbRecord(
        build({ title: "うる星やつら", publisher: "小学館" }),
        empty,
        empty,
      ),
    ).toBeNull();
  });

  it("priority: rating beats description/imprint/publisher", () => {
    const adultImprints = new Set(["X"]);
    const adultPublishers = new Set(["Y"]);
    expect(
      isAdultMadbRecord(
        build({
          rating: "成年コミック",
          description: "成年コミック",
          brand: "X",
          publisher: "Y",
        }),
        adultImprints,
        adultPublishers,
      ),
    ).toBe("rating");
  });
});

describe("parseVolumeNumber", () => {
  it("parses pure digit", () => {
    expect(parseVolumeNumber("25")).toBe(25);
  });

  it("rejects non-digit", () => {
    expect(parseVolumeNumber("椿屋の源編")).toBeNull();
  });

  it("rejects empty", () => {
    expect(parseVolumeNumber("")).toBeNull();
  });

  it("normalizes 全角 digit", () => {
    expect(parseVolumeNumber("１２")).toBe(12);
  });
});
