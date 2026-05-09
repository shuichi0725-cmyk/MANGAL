import { describe, expect, it } from "vitest";
import {
  cleanCreatorStrings,
  extractMadbId,
  extractRecord,
  findKanaLiteral,
  firstString,
  flattenStringArray,
  isAdultMadbRecord,
  parseVolumeNumber,
  rebuildSchemaName,
  selectiveNormalize,
  splitMadbLiteral,
  stripLeadingRolePrefix,
  type MadbJsonLdRecord,
  type MadbRecord,
} from "./madb-jsonld";

describe("stripLeadingRolePrefix (= publisher [発売]/[頒布] 等の prefix 除去)", () => {
  it("strips [発売] prefix", () => {
    expect(stripLeadingRolePrefix("[発売]KADOKAWA")).toBe("KADOKAWA");
  });

  it("strips [頒布] prefix", () => {
    expect(stripLeadingRolePrefix("[頒布]鉄人社")).toBe("鉄人社");
  });

  it("strips compound role like [共同刊行・発売]", () => {
    expect(stripLeadingRolePrefix("[共同刊行・発売]講談社")).toBe("講談社");
  });

  it("preserves value when no prefix", () => {
    expect(stripLeadingRolePrefix("KADOKAWA")).toBe("KADOKAWA");
    expect(stripLeadingRolePrefix("集英社")).toBe("集英社");
  });

  it("preserves bracket-only content when strip would produce empty (= 出版者不明 case)", () => {
    expect(stripLeadingRolePrefix("[出版者不明]")).toBe("[出版者不明]");
    expect(stripLeadingRolePrefix("[光文社]")).toBe("[光文社]");
    expect(stripLeadingRolePrefix("[いしいたける]")).toBe("[いしいたける]");
  });

  it("strips only leading prefix (= keeps trailing brackets)", () => {
    // 仮想ケース: prefix + content + 末尾括弧
    expect(stripLeadingRolePrefix("[発売]社名(出版部門)")).toBe("社名(出版部門)");
  });

  it("handles whitespace around prefix", () => {
    expect(stripLeadingRolePrefix(" [発売] KADOKAWA")).toBe("KADOKAWA");
  });

  it("returns empty input as-is", () => {
    expect(stripLeadingRolePrefix("")).toBe("");
  });
});

describe("selectiveNormalize (= B/C/D のみ統一、 括弧他は保持)", () => {
  it("converts 全角空白 (U+3000) to 半角空白 (= pattern B)", () => {
    expect(selectiveNormalize("集英社文庫　コミック版")).toBe("集英社文庫 コミック版");
  });

  it("converts 全角 ％ (U+FF05) to 半角 % (= pattern C)", () => {
    expect(selectiveNormalize("ニュータイプ100％コミックス")).toBe("ニュータイプ100%コミックス");
  });

  it("converts 半角中黒 ･ (U+FF65) to 全角中黒 ・ (= pattern D, half→full)", () => {
    expect(selectiveNormalize("ダ･ヴィンチブックス")).toBe("ダ・ヴィンチブックス");
  });

  it("preserves 全角括弧 (= pattern A excluded by user choice)", () => {
    // デザインコンセプトとして保持されるべき
    expect(selectiveNormalize("Daito comics PC（pet comic）シリーズ")).toBe("Daito comics PC（pet comic）シリーズ");
    expect(selectiveNormalize("［コミックエッセイの森］")).toBe("［コミックエッセイの森］");
  });

  it("preserves 全角アルファベット (= NFKC would touch but we don't)", () => {
    // ユーザ明示選択スコープ外
    expect(selectiveNormalize("ＫＡＤＯＫＡＷＡ")).toBe("ＫＡＤＯＫＡＷＡ");
  });

  it("handles mixed B+C+D in single string", () => {
    // 全角空白 + 全角％ + 半角中黒 を同時に
    expect(selectiveNormalize("Foo　50％･bar")).toBe("Foo 50%・bar");
  });

  it("returns empty string unchanged", () => {
    expect(selectiveNormalize("")).toBe("");
  });

  it("returns plain ASCII unchanged", () => {
    expect(selectiveNormalize("Hello World")).toBe("Hello World");
  });
});

describe("rebuildSchemaName (= 種2 用 schema:name 仕様準拠化)", () => {
  it("demotes ASCII-only ja-hrkt values to en (= 進撃の巨人 case)", () => {
    const input = [
      "進撃の巨人 = attack on titan",
      { "@value": "attack on titan", "@language": "ja-hrkt" },
      { "@value": "シンゲキ ノ キョジン", "@language": "ja-hrkt" },
    ];
    const output = rebuildSchemaName(input) as Array<unknown>;
    // 漢字 string 残存
    expect(output[0]).toBe("進撃の巨人 = attack on titan");
    // カタカナ含む ja-hrkt 残存
    expect(output).toContainEqual({
      "@value": "シンゲキ ノ キョジン",
      "@language": "ja-hrkt",
    });
    // ASCII-only ja-hrkt は en に降格
    expect(output).toContainEqual({
      "@value": "attack on titan",
      "@language": "en",
    });
    // 元の ja-hrkt slot に attack on titan は残ってない
    expect(output).not.toContainEqual({
      "@value": "attack on titan",
      "@language": "ja-hrkt",
    });
  });

  it("preserves clean array (= no ja-hrkt mixing)", () => {
    const input = [
      "鬼滅の刃",
      { "@value": "キメツ ノ ヤイバ", "@language": "ja-hrkt" },
    ];
    const output = rebuildSchemaName(input);
    expect(output).toEqual(input);
  });

  it("does NOT add en when en already exists (= ZETMAN case)", () => {
    // 仮想: "Zetman" が ja-hrkt に居て、 en にも別の英文があるケース
    const input = [
      "ZETMAN",
      { "@value": "Existing English Title", "@language": "en" },
      { "@value": "Zetman", "@language": "ja-hrkt" },
      { "@value": "ゼットマン", "@language": "ja-hrkt" },
    ];
    const output = rebuildSchemaName(input) as Array<unknown>;
    // カタカナ ja-hrkt 残存
    expect(output).toContainEqual({
      "@value": "ゼットマン",
      "@language": "ja-hrkt",
    });
    // 既存 en 残存
    expect(output).toContainEqual({
      "@value": "Existing English Title",
      "@language": "en",
    });
    // Zetman は ja-hrkt から消えてる (= 既に en あるので追加もされない)
    expect(output).not.toContainEqual({
      "@value": "Zetman",
      "@language": "ja-hrkt",
    });
    expect(output).not.toContainEqual({
      "@value": "Zetman",
      "@language": "en",
    });
  });

  it("keeps ja-hrkt with hiragana (= ひらがな含むも カナ扱い)", () => {
    const input = [
      "ふしぎな駄菓子屋",
      { "@value": "ふしぎな ダガシヤ", "@language": "ja-hrkt" },
    ];
    const output = rebuildSchemaName(input);
    expect(output).toEqual(input);
  });

  it("handles all-ASCII record (= 全 ja-hrkt が ASCII)", () => {
    const input = [
      "Eva lady",
      { "@value": "Eva lady", "@language": "ja-hrkt" },
    ];
    const output = rebuildSchemaName(input) as Array<unknown>;
    // ja-hrkt は空
    expect(output).not.toContainEqual({
      "@value": "Eva lady",
      "@language": "ja-hrkt",
    });
    // en に降格
    expect(output).toContainEqual({
      "@value": "Eva lady",
      "@language": "en",
    });
  });

  it("preserves @id references", () => {
    const input = [
      "タイトル",
      { "@id": "https://example.com/id/X1" },
      { "@value": "タイトル ヨミ", "@language": "ja-hrkt" },
    ];
    const output = rebuildSchemaName(input) as Array<unknown>;
    expect(output).toContainEqual({ "@id": "https://example.com/id/X1" });
    expect(output).toContainEqual({
      "@value": "タイトル ヨミ",
      "@language": "ja-hrkt",
    });
  });

  it("returns undefined for undefined / null", () => {
    expect(rebuildSchemaName(undefined)).toBeUndefined();
    expect(rebuildSchemaName(null as never)).toBeNull();
  });

  it("returns plain string unchanged (= no array)", () => {
    expect(rebuildSchemaName("単純タイトル")).toBe("単純タイトル");
  });

  it("handles 3+ ja-hrkt values keeping all kana ones", () => {
    const input = [
      "美味しんぼ",
      { "@value": "オイシンボ", "@language": "ja-hrkt" },
      { "@value": "Oishinbo", "@language": "ja-hrkt" },
      { "@value": "メイヒンシュウ", "@language": "ja-hrkt" },
    ];
    const output = rebuildSchemaName(input) as Array<unknown>;
    // カタカナ 2 件 とも 残存
    expect(output).toContainEqual({
      "@value": "オイシンボ",
      "@language": "ja-hrkt",
    });
    expect(output).toContainEqual({
      "@value": "メイヒンシュウ",
      "@language": "ja-hrkt",
    });
    // ASCII は en に降格
    expect(output).toContainEqual({
      "@value": "Oishinbo",
      "@language": "en",
    });
  });
});

describe("cleanCreatorStrings (= MADB old-format [著] prefix handling)", () => {
  it("strips [著] role prefix from single-author old-format string", () => {
    expect(cleanCreatorStrings(["[著]吾峠呼世晴"])).toEqual(["吾峠呼世晴"]);
  });

  it("strips prefix and splits comma-packed multi-author old-format string", () => {
    expect(cleanCreatorStrings(["[著]浦沢直樹,スタジオ・ナッツ"])).toEqual([
      "浦沢直樹",
      "スタジオ・ナッツ",
    ]);
  });

  it("passes through clean new-format names unchanged", () => {
    expect(cleanCreatorStrings(["原泰久"])).toEqual(["原泰久"]);
    expect(cleanCreatorStrings(["花咲アキラ", "雁屋哲"])).toEqual([
      "花咲アキラ",
      "雁屋哲",
    ]);
  });

  it("handles compound roles like [著・画]", () => {
    expect(cleanCreatorStrings(["[著・画]山田太郎"])).toEqual(["山田太郎"]);
  });

  it("splits records with multiple [role]name pairs joined by full-width slash", () => {
    expect(cleanCreatorStrings(["[原作]大場つぐみ／[漫画]小畑健"])).toEqual([
      "大場つぐみ",
      "小畑健",
    ]);
  });

  it("filters out empty strings and whitespace-only fragments", () => {
    expect(cleanCreatorStrings(["", "  ", "[著]"])).toEqual([]);
  });

  it("handles half-width comma + various role labels", () => {
    expect(
      cleanCreatorStrings(["[原作]A,[作画]B,[編集協力]C"]),
    ).toEqual(["A", "B", "C"]);
  });

  it("keeps Japanese punctuation (= 中黒) inside a name", () => {
    expect(cleanCreatorStrings(["[著]スタジオ・ナッツ"])).toEqual(["スタジオ・ナッツ"]);
  });
});

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

  it("captures schema:position as volumeSort (= integer) and schema:image as coverImage", () => {
    const raw = {
      "@id": "https://mediaarts-db.artmuseums.go.jp/id/M999",
      "schema:isbn": "9784000000000",
      "schema:name": "テスト",
      "schema:position": "13.0",
      "schema:image": "https://example.com/cover.jpg",
      "schema:volumeNumber": "其之十三",
    } as MadbJsonLdRecord;
    const rec = extractRecord(raw);
    // 表示文字列 「其之十三」 と numeric position "13.0" の両方を保持
    expect(rec?.volumeNumber).toBe("其之十三");
    expect(rec?.volumeSort).toBe(13);
    expect(rec?.coverImage).toBe("https://example.com/cover.jpg");
  });

  it("returns null volumeSort when schema:position is missing or non-numeric", () => {
    const raw = {
      "@id": "https://mediaarts-db.artmuseums.go.jp/id/M998",
      "schema:isbn": "9784000000017",
      "schema:name": "テスト2",
      "schema:volumeNumber": "1",
    } as MadbJsonLdRecord;
    const rec = extractRecord(raw);
    expect(rec?.volumeSort).toBeNull();
    expect(rec?.coverImage).toBe("");
  });

  it("accepts numeric schema:position (= JSON number, not string)", () => {
    const raw = {
      "@id": "https://mediaarts-db.artmuseums.go.jp/id/M997",
      "schema:isbn": "9784000000024",
      "schema:position": 5,
    } as unknown as MadbJsonLdRecord;
    const rec = extractRecord(raw);
    expect(rec?.volumeSort).toBe(5);
  });

  it("extracts dcterms:creator C-ID suffixes (= single ref)", () => {
    const raw = {
      "@id": "https://mediaarts-db.artmuseums.go.jp/id/M001",
      "schema:isbn": "9784000000048",
      "dcterms:creator": {
        "@id": "https://mediaarts-db.artmuseums.go.jp/id/C53400",
      },
    } as unknown as MadbJsonLdRecord;
    const rec = extractRecord(raw);
    expect(rec?.creatorRefs).toEqual(["C53400"]);
  });

  it("extracts multiple C-IDs (= 共著 array form)", () => {
    const raw = {
      "@id": "https://mediaarts-db.artmuseums.go.jp/id/M002",
      "schema:isbn": "9784000000055",
      "dcterms:creator": [
        { "@id": "https://mediaarts-db.artmuseums.go.jp/id/C61882" },
        { "@id": "https://mediaarts-db.artmuseums.go.jp/id/C61883" },
      ],
    } as unknown as MadbJsonLdRecord;
    const rec = extractRecord(raw);
    expect(rec?.creatorRefs).toEqual(["C61882", "C61883"]);
  });

  it("ignores dcterms:creator @id values that are not C-prefixed", () => {
    const raw = {
      "@id": "https://mediaarts-db.artmuseums.go.jp/id/M003",
      "schema:isbn": "9784000000062",
      "dcterms:creator": [
        { "@id": "https://example.com/no-c-id" },
        { "@id": "https://mediaarts-db.artmuseums.go.jp/id/C99" },
      ],
    } as unknown as MadbJsonLdRecord;
    const rec = extractRecord(raw);
    expect(rec?.creatorRefs).toEqual(["C99"]);
  });

  it("returns empty array when dcterms:creator is missing", () => {
    const raw = {
      "@id": "https://mediaarts-db.artmuseums.go.jp/id/M004",
      "schema:isbn": "9784000000079",
    } as MadbJsonLdRecord;
    const rec = extractRecord(raw);
    expect(rec?.creatorRefs).toEqual([]);
  });

  it("picks first URL from schema:image when given an array", () => {
    const raw = {
      "@id": "https://mediaarts-db.artmuseums.go.jp/id/M996",
      "schema:isbn": "9784000000031",
      "schema:image": [
        "https://example.com/a.jpg",
        "https://example.com/b.jpg",
      ],
    } as unknown as MadbJsonLdRecord;
    const rec = extractRecord(raw);
    expect(rec?.coverImage).toBe("https://example.com/a.jpg");
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
      volumeSort: null,
      coverImage: "",
      creatorRefs: [],
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
