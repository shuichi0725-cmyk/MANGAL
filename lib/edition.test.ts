import { describe, expect, it } from "vitest";
import {
  baseTitle,
  buildCreatorClause,
  buildSeriesKey,
  classifyEdition,
  escapeCql,
  extractVolumeNumber,
  normalizeIsbn13,
  normalizeReleaseDate,
  normalizeSeriesKey,
  toLccCreatorForm,
} from "./edition";

describe("extractVolumeNumber", () => {
  it("extracts simple trailing number", () => {
    expect(extractVolumeNumber("うる星やつら 1")).toBe(1);
    expect(extractVolumeNumber("うる星やつら 34")).toBe(34);
  });

  it("extracts (N) and （N） parenthesized form", () => {
    expect(extractVolumeNumber("うる星やつら（1）")).toBe(1);
    expect(extractVolumeNumber("うる星やつら(15)")).toBe(15);
  });

  it("extracts 第N巻 form", () => {
    expect(extractVolumeNumber("うる星やつら 第3巻")).toBe(3);
    expect(extractVolumeNumber("うる星やつら第120巻")).toBe(120);
  });

  it("does not extract year as volume number (the C1 bug)", () => {
    // 4-digit year at end should not produce phantom volumes 980 / 024
    expect(extractVolumeNumber("うる星やつら 1980")).toBeNull();
    expect(extractVolumeNumber("うる星やつら 2024")).toBeNull();
    expect(extractVolumeNumber("うる星やつら 2024年初版")).toBeNull();
    expect(extractVolumeNumber("うる星やつら 2024年")).toBeNull();
  });

  it("does not get confused by multi-number titles", () => {
    expect(extractVolumeNumber("第1巻 うる星やつら 2024")).toBe(1);
  });

  it("returns null for unnumbered specials", () => {
    expect(extractVolumeNumber("うる星やつら パーフェクトカラーエディション 上")).toBeNull();
    expect(extractVolumeNumber("うる星やつら ガイドブック")).toBeNull();
  });
});

describe("classifyEdition (M5: scoring-based)", () => {
  it("classifies the standard editions", () => {
    expect(classifyEdition("うる星やつら 1")).toBe("standard");
    expect(classifyEdition("うる星やつら 完全版 1")).toBe("kanzenban");
    expect(classifyEdition("うる星やつら 文庫版 第1巻")).toBe("bunkobon");
    expect(classifyEdition("うる星やつら〔新装版〕（1）")).toBe("shinsoban");
    expect(classifyEdition("うる星やつら 愛蔵版 1")).toBe("aizoban");
    expect(classifyEdition("うる星やつら ワイド版 1")).toBe("wideban");
  });

  it("recognizes cover-renewal explicitly", () => {
    expect(classifyEdition("うる星やつら カバー新装 1")).toBe("renewal");
    expect(classifyEdition("ドラゴンボール カバーリニューアル 1")).toBe("renewal");
  });

  it("standard wins on ties (no edition tokens at all)", () => {
    expect(classifyEdition("ふつうの単行本タイトル 1")).toBe("standard");
  });
});

describe("baseTitle / normalizeSeriesKey", () => {
  it("strips edition + volume markers across forms", () => {
    expect(baseTitle("うる星やつら〔新装版〕（1）")).toBe("うる星やつら");
    expect(baseTitle("うる星やつら 完全版 第3巻")).toBe("うる星やつら");
    expect(baseTitle("うる星やつら 文庫版 1")).toBe("うる星やつら");
  });

  it("normalizes for series-key comparison (case + space)", () => {
    expect(normalizeSeriesKey("うる星やつら（1）")).toBe(
      normalizeSeriesKey("うる星やつら 文庫版 第3巻"),
    );
    expect(normalizeSeriesKey("ONE PIECE 1")).toBe("onepiece");
  });

  it("M4: keeps non-edition parentheses (no longer strips all brackets)", () => {
    // 以前は (株) もエディション注釈と一緒に消されていた。
    expect(baseTitle("(株)社長")).toBe("(株)社長");
    expect(baseTitle("[Tシャツ] 物語")).toBe("[Tシャツ] 物語");
  });

  it("M4: still strips brackets that contain edition tokens", () => {
    expect(baseTitle("BLEACH【完全版】 1")).toBe("BLEACH");
    expect(baseTitle("デスノート〔文庫版〕 第3巻")).toBe("デスノート");
  });

  // 実走で発覚した NDL/MARC 表記揺れの取りこぼし対策
  it("strips NDL/MARC trailing period", () => {
    expect(baseTitle("犬夜叉.")).toBe("犬夜叉");
    expect(baseTitle("MAO.")).toBe("MAO");
    expect(baseTitle("うる星やつら.")).toBe("うる星やつら");
  });

  it("strips ': subtitle' (NDL ISBD subtitle separator)", () => {
    expect(baseTitle("境界のRINNE : Circle Of Reincarnation")).toBe(
      "境界のRINNE",
    );
    expect(baseTitle("Pの悲劇 : 高橋留美子傑作集")).toBe("Pの悲劇");
    expect(baseTitle("うる星やつら : TVアニメ版")).toBe("うる星やつら");
    expect(baseTitle("うる星やつら : ラム&幼なじみセレクション")).toBe(
      "うる星やつら",
    );
  });

  it("strips '= english title' parallel-title", () => {
    expect(
      baseTitle(
        "うる星やつらパーフェクト★カラーエディション = Urusei Yatsura Perfect Color Edition",
      ),
    ).toBe("うる星やつらパーフェクト★カラーエディション");
  });

  it("strips trailing numbering markers (. v. / . vol. / . no. / , no.)", () => {
    expect(baseTitle("1ポンドの福音. v.")).toBe("1ポンドの福音");
    expect(baseTitle("1ポンドの福音. vol.")).toBe("1ポンドの福音");
    expect(baseTitle("1ポンドの福音. v. 2")).toBe("1ポンドの福音");
    expect(baseTitle("うる星やつら. no.")).toBe("うる星やつら");
    expect(baseTitle("うる星やつら, no. 5")).toBe("うる星やつら");
  });

  it("merges all NDL variants of one title to a single base", () => {
    const expected = "うる星やつら";
    const variants = [
      "うる星やつら",
      "うる星やつら.",
      "うる星やつら〔新装版〕（1）",
      "うる星やつら : 復刻box",
      "うる星やつら 完全版 第3巻",
      "うる星やつら. no.",
    ];
    for (const v of variants) {
      expect(baseTitle(v)).toBe(expected);
    }
  });

  // Run #3 で発覚した残課題（baseTitle 二次強化）
  it("strips kana-only annotations in parens (e.g. yomigana)", () => {
    expect(baseTitle("境界のRinne (りんね)")).toBe("境界のRinne");
  });

  it("strips '. 上 / . 下 / . 上巻 / . 下巻' half-volume markers", () => {
    expect(baseTitle("劇場版犬夜叉時代を越える想い. 上巻")).toBe(
      "劇場版犬夜叉時代を越える想い",
    );
    expect(baseTitle("うる星やつら令和版ラブセレクション. 上")).toBe(
      "うる星やつら令和版ラブセレクション",
    );
    expect(baseTitle("うる星やつら令和版ラブセレクション. 下")).toBe(
      "うる星やつら令和版ラブセレクション",
    );
  });

  it("strips 第N集 / 第N部 / 第N話 like 第N巻", () => {
    expect(baseTitle("めぞん一刻. 第10集")).toBe("めぞん一刻");
    expect(baseTitle("めぞん一刻. 第1集")).toBe("めぞん一刻");
  });

  it("strips bare 'N巻' (without 第 prefix) — NDL run #4 case", () => {
    // 「犬夜叉 5巻」「犬夜叉. 24巻」が独立シリーズ化していたケース
    expect(baseTitle("犬夜叉 5巻")).toBe("犬夜叉");
    expect(baseTitle("犬夜叉. 24巻")).toBe("犬夜叉");
    expect(baseTitle("ONE PIECE 109巻")).toBe("ONE PIECE");
  });

  it("does not eat year-shaped numbers from 'N巻' rule", () => {
    // 4 桁数字を巻番号にしない（誤って "1978" を "巻=1978" 扱いしない）
    expect(baseTitle("COLORS 1978-2024")).toBe("COLORS 1978-2024");
  });

  it("strips '. <Japanese subtitle>' when preceded by a CJK char", () => {
    expect(baseTitle("しゃばけ漫画. 仁吉の巻")).toBe("しゃばけ漫画");
  });

  it("does NOT strip '. <subtitle>' when preceded by a Latin char", () => {
    // Dr. House / J. K. ローリング 等を巻き込まない
    expect(baseTitle("Dr. House")).toBe("Dr. House");
  });

  it("preserves a year suffix that looks like a volume number", () => {
    // 末尾の '024' を巻 24 と誤認しないこと（COLORS 1978-2024 例）
    expect(baseTitle("COLORS 1978-2024 : 高橋留美子原画集")).toBe(
      "COLORS 1978-2024",
    );
  });

  it("the union of new strip rules collapses NDL run #3 split-out cases", () => {
    expect(baseTitle("境界のRINNE.")).toBe("境界のRINNE");
    expect(baseTitle("境界のRinne (りんね)")).toBe("境界のRinne");
    // normalizeSeriesKey で同一視される（大文字小文字 + 空白除去後）
    expect(normalizeSeriesKey("境界のRINNE.")).toBe(
      normalizeSeriesKey("境界のRinne (りんね)"),
    );
  });
});

describe("buildSeriesKey (C2 fix)", () => {
  it("includes author so same-title different-author do not collide", () => {
    const a = buildSeriesKey("ハンター 1", { qid: "Q11111" });
    const b = buildSeriesKey("ハンター 1", { qid: "Q22222" });
    expect(a).not.toBe(b);
  });

  it("falls back to name when qid is unknown", () => {
    const k = buildSeriesKey("めぞん一刻 第1巻", { name: "高橋留美子" });
    expect(k).toBe("norm:めぞん一刻|name:高橋留美子");
  });

  it("collapses different editions of the same series to the same key", () => {
    const k1 = buildSeriesKey("うる星やつら 1", { qid: "Q193300" });
    const k2 = buildSeriesKey("うる星やつら〔新装版〕(15)", { qid: "Q193300" });
    expect(k1).toBe(k2);
  });
});

describe("toLccCreatorForm (NDL fallback variant)", () => {
  it("splits typical 4-char Japanese names at the 2-char family boundary", () => {
    expect(toLccCreatorForm("高橋留美子")).toBe("高橋, 留美子");
    expect(toLccCreatorForm("尾田栄一郎")).toBe("尾田, 栄一郎");
  });

  it("uses an existing space as the family/given divider when present", () => {
    expect(toLccCreatorForm("藤子 不二雄")).toBe("藤子, 不二雄");
  });

  it("returns the input unchanged when too short to split", () => {
    expect(toLccCreatorForm("ON")).toBe("ON");
    expect(toLccCreatorForm("X")).toBe("X");
  });
});

describe("escapeCql / buildCreatorClause (C3 fix)", () => {
  it("escapes embedded quotes", () => {
    expect(escapeCql('Q.B.B "Bunch"')).toBe('Q.B.B \\"Bunch\\"');
    expect(escapeCql("foo\\bar")).toBe("foo\\\\bar");
  });

  it("builds OR clause from alt names", () => {
    expect(buildCreatorClause(["高橋留美子", "高橋るみ子"])).toBe(
      '(creator="高橋留美子" OR creator="高橋るみ子")',
    );
    expect(buildCreatorClause(["高橋留美子"])).toBe('creator="高橋留美子"');
    expect(buildCreatorClause([])).toBe("");
  });

  it("dedupes and escapes inside the OR clause", () => {
    expect(buildCreatorClause(["a", "a", 'b"c'])).toBe(
      '(creator="a" OR creator="b\\"c")',
    );
  });
});

describe("normalizeIsbn13 (C5 fix: check digit)", () => {
  it("accepts a valid ISBN-13", () => {
    // 9784088725093 is real (One Piece vol 1) and has correct check digit
    expect(normalizeIsbn13("978-4-08-872509-3")).toBe("9784088725093");
    expect(normalizeIsbn13("9784088725093")).toBe("9784088725093");
  });

  it("rejects ISBN-13 with bad check digit", () => {
    expect(normalizeIsbn13("9784088725090")).toBeNull(); // last digit wrong
    expect(normalizeIsbn13("9784088725099")).toBeNull();
  });

  it("rejects non-book GTIN-13 (not 978/979 prefix)", () => {
    expect(normalizeIsbn13("4901234567894")).toBeNull(); // JAN code
  });

  it("converts valid ISBN-10 to ISBN-13", () => {
    // 4088725093 is the ISBN-10 form. The 10-digit check digit needs to be valid.
    // ISBN-10 check digit for "408872509" :
    //   sum = 4*10 + 0*9 + 8*8 + 8*7 + 7*6 + 2*5 + 5*4 + 0*3 + 9*2
    //       = 40 + 0 + 64 + 56 + 42 + 10 + 20 + 0 + 18 = 250
    //   mod 11 = 250 % 11 = 8 → check digit = 11 - 8 = 3, sum incl cd = 253 → not divisible by 11
    // So 4088725093 is NOT a valid ISBN-10 (the One Piece vol 1 ISBN-10 is actually 4088725093,
    // verified valid since 253 % 11 = 0 yes wait: 253/11=23 exact). Let's recompute:
    //   sum incl 3*1 = 250 + 3 = 253. 253 / 11 = 23.0. So divisible. Valid.
    expect(normalizeIsbn13("4088725093")).toBe("9784088725093");
  });

  it("returns null for malformed inputs", () => {
    expect(normalizeIsbn13(null)).toBeNull();
    expect(normalizeIsbn13("")).toBeNull();
    expect(normalizeIsbn13("nonsense")).toBeNull();
    expect(normalizeIsbn13("123")).toBeNull();
  });
});

describe("normalizeReleaseDate", () => {
  it("normalizes japanese date format", () => {
    expect(normalizeReleaseDate("2007年11月17日")).toBe("2007-11-17");
    expect(normalizeReleaseDate("1980年9月")).toBe("1980-09");
  });

  it("normalizes ISO and slash forms", () => {
    expect(normalizeReleaseDate("2007-11-17")).toBe("2007-11-17");
    expect(normalizeReleaseDate("2007/11/17")).toBe("2007-11-17");
    expect(normalizeReleaseDate("20071117")).toBe("2007-11-17");
  });

  it("returns null for garbage", () => {
    expect(normalizeReleaseDate(null)).toBeNull();
    expect(normalizeReleaseDate("???")).toBeNull();
  });
});
