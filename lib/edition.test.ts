import { describe, expect, it } from "vitest";
import {
  EDITION_LABELS,
  EDITION_ORDER,
  EDITION_PRIORITY,
  baseTitle,
  buildCreatorClause,
  buildSeriesKey,
  classifyEdition,
  classifyEditionFromImprint,
  escapeCql,
  extractVolumeNumber,
  matchAdultPublisher,
  normalizeIsbn13,
  normalizeReleaseDate,
  normalizeSeriesKey,
  slugFromTitle,
  toLccCreatorForm,
  type EditionType,
} from "./edition";

describe("EDITION_PRIORITY", () => {
  it("covers every EditionType exactly once", () => {
    const allTypes: EditionType[] = [
      "standard",
      "kanzenban",
      "bunkobon",
      "shinsoban",
      "aizoban",
      "wideban",
      "deluxe",
      "renewal",
      "anime",
      "other",
    ];
    for (const t of allTypes) {
      expect(EDITION_PRIORITY[t]).toBeTypeOf("number");
    }
    expect(Object.keys(EDITION_PRIORITY).length).toBe(allTypes.length);
  });

  it("places standard first and other last", () => {
    expect(EDITION_PRIORITY.standard).toBe(0);
    expect(EDITION_PRIORITY.other).toBe(EDITION_ORDER.length - 1);
  });

  it("matches EDITION_ORDER index", () => {
    for (let i = 0; i < EDITION_ORDER.length; i++) {
      expect(EDITION_PRIORITY[EDITION_ORDER[i]]).toBe(i);
    }
  });

  it("EDITION_LABELS covers same keys", () => {
    for (const t of EDITION_ORDER) {
      expect(EDITION_LABELS[t]).toBeTypeOf("string");
    }
  });
});

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

  it("does not extract a digit glued to the title body as a volume number", () => {
    // 「アバンチュール21」の "21" は作品名の一部であって巻番号ではない。
    // 直前が文字 "ル" (空白なし) なので m3/m4 の \s 境界要求で棄却される。
    expect(extractVolumeNumber("アバンチュール21")).toBeNull();
    expect(extractVolumeNumber("ロボット8号")).toBeNull();
    // 一方、空白で区切られていれば従来どおり巻番号として採用
    expect(extractVolumeNumber("アバンチュール 21")).toBe(21);
  });

  it("extracts bare 'N巻' (without 第 prefix)", () => {
    // m2b: タイトル中の "5巻" "24巻" を巻番号として採用 (実走 NDL 由来)
    expect(extractVolumeNumber("犬夜叉 5巻")).toBe(5);
    expect(extractVolumeNumber("犬夜叉. 24巻")).toBe(24);
    expect(extractVolumeNumber("ONE PIECE 109巻")).toBe(109);
  });

  it("extracts middle digit from ISBD '. N (subtitle)' form", () => {
    // "Kirara. 1 (夢じゃない)" のような形式 → m4 が中間 "1" を拾う
    expect(extractVolumeNumber("Kirara. 1 (夢じゃない)")).toBe(1);
    expect(extractVolumeNumber("Kirara. 6 (元気でね!!)")).toBe(6);
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

  it("recognizes anime edition", () => {
    expect(classifyEdition("アニメ版うる星やつら 35")).toBe("anime");
    expect(classifyEdition("ドラゴンボール TVアニメ版 1")).toBe("anime");
  });
});

describe("classifyEditionFromImprint", () => {
  it("classifies 通常版 imprint as standard", () => {
    expect(classifyEditionFromImprint("少年サンデーコミックス")).toBe("standard");
    expect(classifyEditionFromImprint("ジャンプ・コミックス")).toBe("standard");
    expect(classifyEditionFromImprint("ビッグコミックス")).toBe("standard");
    expect(classifyEditionFromImprint("")).toBe("standard");
  });

  it("classifies アニメ版 imprint as anime (= 真値 priority over standard)", () => {
    expect(classifyEditionFromImprint("少年サンデーコミックス・アニメ版")).toBe(
      "anime",
    );
    expect(classifyEditionFromImprint("少年サンデーコミックス アニメ版")).toBe(
      "anime",
    );
    expect(classifyEditionFromImprint("TVアニメ コミックス")).toBe("anime");
  });

  it("classifies ワイド版 / 文庫 / 完全版 / 愛蔵 / 新装 imprint", () => {
    expect(classifyEditionFromImprint("少年サンデーコミックスワイド版")).toBe(
      "wideban",
    );
    expect(classifyEditionFromImprint("小学館文庫")).toBe("bunkobon");
    expect(classifyEditionFromImprint("ジャンプ・コミックス文庫版")).toBe(
      "bunkobon",
    );
    expect(classifyEditionFromImprint("ジャンプ・コミックス愛蔵版")).toBe(
      "aizoban",
    );
    expect(classifyEditionFromImprint("完全版コミックス")).toBe("kanzenban");
    expect(classifyEditionFromImprint("新装版コミックス")).toBe("shinsoban");
  });

  it("normalizes NFKC half-width hyphens / spaces", () => {
    expect(classifyEditionFromImprint("少年サンデーコミックス・アニメ版")).toBe(
      "anime",
    );
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

  it("strips ISBD '<title>. N (<subtitle>)' (Yui Toshiki / Kirara case)", () => {
    // NDL の ISBD 慣用形式。タイトル直前が Latin (Rule 10 では取れない) でも、
    // `. N (...)` という形なら明確に「巻番号 + 副題」と判定して剥がす。
    expect(baseTitle("Kirara. 1 (夢じゃない)")).toBe("Kirara");
    expect(baseTitle("Kirara. 2 (未来の想い出)")).toBe("Kirara");
    expect(baseTitle("Kirara. 3 (この人だ~れ!?)")).toBe("Kirara");
    expect(baseTitle("Kirara. 6 (元気でね!!)")).toBe("Kirara");
    // 数字が無い `. (副題)` は対象外（タイトル本体の括弧扱い）
    expect(baseTitle("Some Title (annotation)")).toBe("Some Title (annotation)");
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

  // 2026-05-08: MADB-style 通巻表記サフィックスの集約。
  // MADB は「Monster v.5」 「20世紀少年 Volume.1」 「Happy! v.13」 「21世紀少年 上」
  // のような space 区切りで series を細分化発行する。 これらを親 series 名に
  // 集約する。 keyword (no/vol/v/volume) または 上/下 が必須なので、 単純な
  // 末尾英単語 (Dr. House) や bare title は誤マッチしない。
  it("strips MADB-style v.N / vol.N / Volume.N suffix (space-only delimiter)", () => {
    expect(baseTitle("Monster v.1")).toBe("Monster");
    expect(baseTitle("Monster v.5")).toBe("Monster");
    expect(baseTitle("Monster v.9")).toBe("Monster");
    expect(baseTitle("Happy! v.13")).toBe("Happy!");
    expect(baseTitle("Happy! v.1")).toBe("Happy!");
    expect(baseTitle("Pineapple army v.2")).toBe("Pineapple army");
    expect(baseTitle("20世紀少年 Volume.1")).toBe("20世紀少年");
    expect(baseTitle("20世紀少年 Volume.10")).toBe("20世紀少年");
  });

  // MADB Monster CSV で発覚: 通常版が "Monster chapter X" / "Monster X" の
  // 表記揺らぎで series が分離される。 chapter X 形式も親 series に集約する。
  it("strips MADB-style chapter N suffix (= 通常版 chapter 表記揺らぎ)", () => {
    expect(baseTitle("Monster chapter 1")).toBe("Monster");
    expect(baseTitle("Monster chapter 5")).toBe("Monster");
    expect(baseTitle("Monster chapter 18")).toBe("Monster");
    // 「chapter」 keyword 必須で他英単語は誤マッチしない (= regression check)
    expect(baseTitle("Monster")).toBe("Monster");
    expect(baseTitle("Monster Special Paperback")).toBe("Monster Special Paperback");
  });

  it("strips MADB-style 上 / 下 / 上巻 / 下巻 (space-only delimiter)", () => {
    expect(baseTitle("21世紀少年 上")).toBe("21世紀少年");
    expect(baseTitle("21世紀少年 下")).toBe("21世紀少年");
    expect(baseTitle("21世紀少年 上巻")).toBe("21世紀少年");
    expect(baseTitle("21世紀少年 下巻")).toBe("21世紀少年");
  });

  it("regression: bare titles and english punctuation must not be eaten", () => {
    // bare title をそのまま残す
    expect(baseTitle("Monster")).toBe("Monster");
    expect(baseTitle("21世紀少年")).toBe("21世紀少年");
    expect(baseTitle("Happy!")).toBe("Happy!");
    // 英語 punctuation 入りタイトル (= keyword 一致なし、 誤マッチしない)
    expect(baseTitle("Dr. House")).toBe("Dr. House");
  });

  it("21世紀少年 と 20世紀少年 は別作品として保持される (continuity check)", () => {
    // 20世紀少年 と 21世紀少年 は別 series。 baseTitle が 21 → 20 に
    // 削るような誤動作をしないことを担保。
    expect(baseTitle("20世紀少年")).toBe("20世紀少年");
    expect(baseTitle("21世紀少年")).toBe("21世紀少年");
    expect(baseTitle("20世紀少年 Volume.1")).toBe("20世紀少年");
    expect(baseTitle("21世紀少年 Volume.1")).toBe("21世紀少年");
    expect(baseTitle("21世紀少年 上巻")).toBe("21世紀少年");
    // normalizeSeriesKey でも別物として保持
    expect(normalizeSeriesKey("20世紀少年")).not.toBe(
      normalizeSeriesKey("21世紀少年"),
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

describe("slugFromTitle", () => {
  it("uses kana hint to romanize kanji-only titles", () => {
    expect(slugFromTitle("犬夜叉", { kana: "いぬやしゃ" })).toBe("inuyasha");
    expect(slugFromTitle("めぞん一刻", { kana: "めぞんいっこく" })).toBe(
      "mezon-ikkoku",
    );
  });

  it("falls back to title-only conversion when kana absent (kana titles)", () => {
    expect(slugFromTitle("うる星やつら", { kana: "うるせいやつら" })).toBe(
      "uruseiyatsura",
    );
  });

  it("returns empty string for kanji-only titles without kana", () => {
    // 漢字のみは wanakana で変換されないので [a-z0-9] が空 → ""
    expect(slugFromTitle("犬夜叉")).toBe("");
  });

  it("converts ASCII titles unchanged (lowercased)", () => {
    expect(slugFromTitle("ONE PIECE")).toBe("one-piece");
    expect(slugFromTitle("Attack on Titan")).toBe("attack-on-titan");
  });

  it("collapses runs of separators and trims edges", () => {
    expect(slugFromTitle("Pの悲劇", { kana: "ぴーのひげき" })).toBe(
      "pi-nohigeki",
    );
  });

  it("truncates very long slugs to 60 chars", () => {
    const longKana = "あ".repeat(80); // toRomaji → "a" × 80
    const s = slugFromTitle("X", { kana: longKana });
    expect(s.length).toBeLessThanOrEqual(60);
  });
});

describe("matchAdultPublisher (Fix C: adult-publisher imprint detection)", () => {
  const known = new Set(["白夜書房", "茜新社", "コアマガジン", "ティーアイネット"]);

  it("matches exact imprint", () => {
    expect(matchAdultPublisher("白夜書房", known)).toBe("白夜書房");
    expect(matchAdultPublisher("茜新社", known)).toBe("茜新社");
  });

  it("matches imprint that contains a known adult name as substring", () => {
    // NDL の imprint には "茜新社コミックス" / "白夜書房 メディアックス" のような
    // 派生表記が出るので、含有マッチが必要。
    expect(matchAdultPublisher("茜新社コミックス", known)).toBe("茜新社");
    expect(matchAdultPublisher("白夜書房 メディアックス", known)).toBe("白夜書房");
  });

  it("does not match unrelated imprint", () => {
    expect(matchAdultPublisher("集英社", known)).toBeNull();
    expect(matchAdultPublisher("講談社 : 講談社コミッククリエイト", known)).toBeNull();
  });

  it("returns null for empty / nullish input", () => {
    expect(matchAdultPublisher(null, known)).toBeNull();
    expect(matchAdultPublisher(undefined, known)).toBeNull();
    expect(matchAdultPublisher("", known)).toBeNull();
  });
});
