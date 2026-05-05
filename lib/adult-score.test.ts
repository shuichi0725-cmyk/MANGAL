import { describe, expect, it } from "vitest";
import { computeAdultScore } from "./adult-score";
import { normalizeCreatorName } from "./edition";

const NO_AUTHORS = new Set<string>();
const NO_PUBLISHERS = new Set<string>();

const KNOWN_ADULT_PUBLISHERS = new Set([
  "白夜書房",
  "茜新社",
  "コアマガジン",
  "ティーアイネット",
]);

// adult_mangaka_known テーブルは normalizeCreatorName 後の文字列で持つので、
// テストでも同じ正規化を通したものを set に入れる。
const KNOWN_ADULT_MANGAKA = new Set(
  ["唯登詩樹", "陽気婢", "山文京伝"].map(normalizeCreatorName),
);

describe("computeAdultScore", () => {
  describe("no signals", () => {
    it("returns score=0 with empty signals when nothing matches", () => {
      const result = computeAdultScore({
        hasWikidataCredit: false,
        authorName: "手塚治虫",
        imprints: [],
        knownAdultMangaka: KNOWN_ADULT_MANGAKA,
        knownAdultPublishers: KNOWN_ADULT_PUBLISHERS,
      });
      expect(result.score).toBe(0);
      expect(result.signals).toEqual([]);
    });

    it("returns score=0 when imprints exist but none match", () => {
      const result = computeAdultScore({
        hasWikidataCredit: false,
        authorName: "手塚治虫",
        imprints: ["集英社", "講談社"],
        knownAdultMangaka: KNOWN_ADULT_MANGAKA,
        knownAdultPublishers: KNOWN_ADULT_PUBLISHERS,
      });
      expect(result.score).toBe(0);
      expect(result.signals).toEqual([]);
    });

    it("does not match adult-list when knownAdultMangaka set is empty", () => {
      const result = computeAdultScore({
        hasWikidataCredit: false,
        authorName: "唯登詩樹",
        imprints: [],
        knownAdultMangaka: NO_AUTHORS,
        knownAdultPublishers: KNOWN_ADULT_PUBLISHERS,
      });
      expect(result.score).toBe(0);
    });
  });

  describe("single signal", () => {
    it("wikidata_hentai_credit alone scores 2 (Option B: below threshold)", () => {
      const result = computeAdultScore({
        hasWikidataCredit: true,
        authorName: "ある作家",
        imprints: [],
        knownAdultMangaka: NO_AUTHORS,
        knownAdultPublishers: NO_PUBLISHERS,
      });
      expect(result.score).toBe(2);
      expect(result.signals).toEqual([
        {
          signal: "wikidata_hentai_credit",
          weight: 2,
          evidence: "ある作家",
        },
      ]);
    });

    it("wikipedia_adult_mangaka_list alone scores 2 (Option B: below threshold)", () => {
      const result = computeAdultScore({
        hasWikidataCredit: false,
        authorName: "唯登詩樹",
        imprints: [],
        knownAdultMangaka: KNOWN_ADULT_MANGAKA,
        knownAdultPublishers: NO_PUBLISHERS,
      });
      expect(result.score).toBe(2);
      expect(result.signals).toHaveLength(1);
      expect(result.signals[0]).toMatchObject({
        signal: "wikipedia_adult_mangaka_list",
        weight: 2,
        evidence: "唯登詩樹",
      });
    });

    it("adult_publisher_imprint alone scores 3 (single signal can skip)", () => {
      const result = computeAdultScore({
        hasWikidataCredit: false,
        authorName: "ある作家",
        imprints: ["白夜書房"],
        knownAdultMangaka: NO_AUTHORS,
        knownAdultPublishers: KNOWN_ADULT_PUBLISHERS,
      });
      expect(result.score).toBe(3);
      expect(result.signals).toEqual([
        {
          signal: "adult_publisher_imprint",
          weight: 3,
          evidence: "白夜書房 ⟵ 白夜書房",
        },
      ]);
    });
  });

  describe("combined signals (skip threshold = 3)", () => {
    it("both author signals together (2+2=4) cross threshold", () => {
      // Wikidata + Wikipedia list 両方ヒットなら作家として確証性が高い
      const result = computeAdultScore({
        hasWikidataCredit: true,
        authorName: "唯登詩樹",
        imprints: [],
        knownAdultMangaka: KNOWN_ADULT_MANGAKA,
        knownAdultPublishers: NO_PUBLISHERS,
      });
      expect(result.score).toBe(4);
      expect(result.signals.map((s) => s.signal)).toEqual([
        "wikidata_hentai_credit",
        "wikipedia_adult_mangaka_list",
      ]);
    });

    it("wikidata + adult publisher imprint = 5 (strong skip)", () => {
      const result = computeAdultScore({
        hasWikidataCredit: true,
        authorName: "ある作家",
        imprints: ["白夜書房"],
        knownAdultMangaka: NO_AUTHORS,
        knownAdultPublishers: KNOWN_ADULT_PUBLISHERS,
      });
      expect(result.score).toBe(5);
      expect(result.signals.map((s) => s.signal)).toEqual([
        "wikidata_hentai_credit",
        "adult_publisher_imprint",
      ]);
    });

    it("all three signals stack (2+2+3=7)", () => {
      const result = computeAdultScore({
        hasWikidataCredit: true,
        authorName: "唯登詩樹",
        imprints: ["白夜書房"],
        knownAdultMangaka: KNOWN_ADULT_MANGAKA,
        knownAdultPublishers: KNOWN_ADULT_PUBLISHERS,
      });
      expect(result.score).toBe(7);
      expect(result.signals.map((s) => s.signal)).toEqual([
        "wikidata_hentai_credit",
        "wikipedia_adult_mangaka_list",
        "adult_publisher_imprint",
      ]);
    });

    it("known adult mangaka with non-adult publisher only = 2 (drafted)", () => {
      // 唯登詩樹の集英社/講談社 一般青年作品を再現するシナリオ。
      // Option B 設計の眼目: 作家シグナルのみでは skip しない。
      const result = computeAdultScore({
        hasWikidataCredit: false,
        authorName: "唯登詩樹",
        imprints: ["集英社", "ヤングジャンプ"],
        knownAdultMangaka: KNOWN_ADULT_MANGAKA,
        knownAdultPublishers: KNOWN_ADULT_PUBLISHERS,
      });
      expect(result.score).toBe(2);
    });
  });

  describe("imprint matching", () => {
    it("counts adult_publisher_imprint only once even with multiple matching imprints", () => {
      // 同一 series が「白夜書房」と「コアマガジン」両方の imprint を持っても
      // adult_score は +3 のみ（同種シグナルの重複加算を防ぐ break が機能）
      const result = computeAdultScore({
        hasWikidataCredit: false,
        authorName: "ある作家",
        imprints: ["白夜書房", "コアマガジン"],
        knownAdultMangaka: NO_AUTHORS,
        knownAdultPublishers: KNOWN_ADULT_PUBLISHERS,
      });
      expect(result.score).toBe(3);
      expect(result.signals).toHaveLength(1);
      expect(result.signals[0].signal).toBe("adult_publisher_imprint");
      // 最初に見つかった imprint で確定する（コーパス順依存はしない設計）
      expect(result.signals[0].evidence).toBe("白夜書房 ⟵ 白夜書房");
    });

    it("matches by substring (e.g., '茜新社コミックス' in imprint)", () => {
      // matchAdultPublisher は substring 包含もマッチさせる仕様
      const result = computeAdultScore({
        hasWikidataCredit: false,
        authorName: "ある作家",
        imprints: ["茜新社コミックス"],
        knownAdultMangaka: NO_AUTHORS,
        knownAdultPublishers: KNOWN_ADULT_PUBLISHERS,
      });
      expect(result.score).toBe(3);
      expect(result.signals[0].evidence).toBe("茜新社コミックス ⟵ 茜新社");
    });

    it("first non-matching imprint does not block a later matching one", () => {
      const result = computeAdultScore({
        hasWikidataCredit: false,
        authorName: "ある作家",
        imprints: ["集英社", "白夜書房"],
        knownAdultMangaka: NO_AUTHORS,
        knownAdultPublishers: KNOWN_ADULT_PUBLISHERS,
      });
      expect(result.score).toBe(3);
      expect(result.signals[0].evidence).toBe("白夜書房 ⟵ 白夜書房");
    });

    it("ignores empty imprint strings without matching", () => {
      const result = computeAdultScore({
        hasWikidataCredit: false,
        authorName: "ある作家",
        imprints: [""],
        knownAdultMangaka: NO_AUTHORS,
        knownAdultPublishers: KNOWN_ADULT_PUBLISHERS,
      });
      expect(result.score).toBe(0);
      expect(result.signals).toEqual([]);
    });
  });

  describe("author-name normalization", () => {
    it("matches author name with whitespace against normalized set entry", () => {
      // 「唯登 詩樹」(NDL の表記揺れ) も「唯登詩樹」と一致する
      const result = computeAdultScore({
        hasWikidataCredit: false,
        authorName: "唯登 詩樹",
        imprints: [],
        knownAdultMangaka: KNOWN_ADULT_MANGAKA,
        knownAdultPublishers: NO_PUBLISHERS,
      });
      expect(result.score).toBe(2);
      expect(result.signals[0].signal).toBe("wikipedia_adult_mangaka_list");
      // evidence は元の表記をそのまま入れる（後でレビュー時に表記揺れを観察できる）
      expect(result.signals[0].evidence).toBe("唯登 詩樹");
    });

    it("matches author name with full-width punctuation against set entry", () => {
      // 「藤子・F・不二雄」スタイルの中黒入り名前。NFKC + 記号削除で正規化される
      const setWithFujiko = new Set([normalizeCreatorName("藤子F不二雄")]);
      const result = computeAdultScore({
        hasWikidataCredit: false,
        authorName: "藤子・F・不二雄",
        imprints: [],
        knownAdultMangaka: setWithFujiko,
        knownAdultPublishers: NO_PUBLISHERS,
      });
      expect(result.score).toBe(2);
    });

    it("does not crash on empty author name (defensive)", () => {
      const result = computeAdultScore({
        hasWikidataCredit: false,
        authorName: "",
        imprints: [],
        knownAdultMangaka: KNOWN_ADULT_MANGAKA,
        knownAdultPublishers: KNOWN_ADULT_PUBLISHERS,
      });
      expect(result.score).toBe(0);
      expect(result.signals).toEqual([]);
    });
  });

  describe("signal evidence shape", () => {
    it("imprint signal evidence shows 'matched_imprint ⟵ catalog_entry'", () => {
      const result = computeAdultScore({
        hasWikidataCredit: false,
        authorName: "ある作家",
        imprints: ["白夜書房 メディアックス"],
        knownAdultMangaka: NO_AUTHORS,
        knownAdultPublishers: KNOWN_ADULT_PUBLISHERS,
      });
      // 派生表記 "白夜書房 メディアックス" でも substring マッチで catalog 側
      // の "白夜書房" にひもづいたことが evidence で追跡できる
      expect(result.signals[0].evidence).toBe(
        "白夜書房 メディアックス ⟵ 白夜書房",
      );
    });

    it("preserves signal order: wikidata → wikipedia_list → imprint", () => {
      // signals 配列の順序は db への書き込み順 / レビューでの可読性に影響するので
      // 固定されていることを確認
      const result = computeAdultScore({
        hasWikidataCredit: true,
        authorName: "唯登詩樹",
        imprints: ["白夜書房"],
        knownAdultMangaka: KNOWN_ADULT_MANGAKA,
        knownAdultPublishers: KNOWN_ADULT_PUBLISHERS,
      });
      expect(result.signals.map((s) => s.signal)).toEqual([
        "wikidata_hentai_credit",
        "wikipedia_adult_mangaka_list",
        "adult_publisher_imprint",
      ]);
    });
  });
});
