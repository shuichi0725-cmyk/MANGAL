import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import {
  __adoptHayForTest,
  __exportHayForTest,
  __hayFillForTest,
  __resetHayForTest,
  __resetSearchCacheForTest,
  __setAltIndexForTest,
  searchWithTiers,
} from "./clientSearch";
import { decodeListIndex, indexRowCount, indexVersionOf } from "./listIndexDecode";
import type { MangaListItem } from "./schema";

/**
 * ★検索の読み込み高速化(2026-09-23)の恒久ガード。
 *  1. 列形式索引(Python が生成 = scripts/_index_files.py)を TS で復元すると、行配列と全行一致する
 *  2. 下ごしらえの2層: 日本語の語はローマ字層を作らずに完結し、英字の語の時だけローマ字層を作る
 *  3. 端末保存 → 復元した下ごしらえで、同じ結果(一致集合・順位)になる
 *  4. 著者の継ぎ目で日本語の語が誤ヒットしない(旧: 「ピア・ゲラ」+「ブライアン」で「ラブ」が当たった)
 * 全件(69,463件×2,800語)の旧実装との突合は .cache/bench/oracle*.ts で実施済み:
 *   新にしか無い一致0・順位違い0・旧にしか無い一致34件(=全部この継ぎ目の誤ヒット)。
 */

const ROOT = path.join(__dirname, "..");
const PREVIEW_ROW = path.join(ROOT, ".preview-data", "manga-list-index.json");
const PREVIEW_COL = path.join(ROOT, ".preview-data", "manga-list-cols.v1.json");
const FIXTURE = path.join(__dirname, "__fixtures__", "search-corpus.json");
const FIXTURE_ALT = path.join(__dirname, "__fixtures__", "search-corpus-alt.json");

describe("列形式索引(Python生成)× TS復元", () => {
  it("preview の列形式と行配列が全行一致で復元される", () => {
    const row = JSON.parse(fs.readFileSync(PREVIEW_ROW, "utf8"));
    const col = JSON.parse(fs.readFileSync(PREVIEW_COL, "utf8"));
    expect(indexRowCount(col)).toBe(indexRowCount(row));
    expect(decodeListIndex(col)).toEqual(decodeListIndex(row));
  });
  it("列形式の版(src)= 行配列の内容ハッシュ(古い列形式が残っていない)", () => {
    const col = JSON.parse(fs.readFileSync(PREVIEW_COL, "utf8"));
    const sha = crypto.createHash("sha1").update(fs.readFileSync(PREVIEW_ROW)).digest("hex").slice(0, 16);
    // 失敗したら: python scripts/_index_files.py ensure .preview-data
    expect(indexVersionOf(col)).toBe(sha);
  });
  it("行配列は版を持たない(=端末保存の対象外)", () => {
    const row = JSON.parse(fs.readFileSync(PREVIEW_ROW, "utf8"));
    expect(indexVersionOf(row)).toBeNull();
  });
});

describe("下ごしらえの2層と端末保存(固定コーパス)", () => {
  let items: MangaListItem[] = [];
  const QUERIES = [
    "ワンピース", "わんぴーす", "ONE PIECE", "鬼滅の刃", "進撃の巨人", "ゴルゴ", "高橋留美子", "たかはしるみこ",
    "wanpisu", "kimetsu", "conan", "isu", "イース", "season2", "七つの大罪", "ワンピース 尾田", "高橋 らんま",
    "one piece", "attack on titan", "の", "ラブ", "学園", "らんま1/2", "ぎゃわんぶらー",
  ];
  const run = (q: string) => {
    __resetSearchCacheForTest();
    return [...searchWithTiers(q, items).entries()].sort();
  };

  beforeAll(() => {
    items = decodeListIndex(JSON.parse(fs.readFileSync(FIXTURE, "utf8")));
    __setAltIndexForTest(JSON.parse(fs.readFileSync(FIXTURE_ALT, "utf8")));
  });

  it("日本語の語だけならローマ字層を作らない / 英字の語で初めて作る", () => {
    __resetHayForTest();
    run("ワンピース");
    run("高橋 らんま");
    expect(__hayFillForTest()).toEqual({ base: items.length, roma: 0 });
    run("wanpisu");
    expect(__hayFillForTest()).toEqual({ base: items.length, roma: items.length });
  });

  it("ローマ字層の有無で日本語の語の結果は変わらない", () => {
    __resetHayForTest();
    const before = ["ワンピース", "高橋留美子", "イース", "ラブ"].map(run); // ローマ字層なし
    run("isu"); // ここでローマ字層ができる
    const after = ["ワンピース", "高橋留美子", "イース", "ラブ"].map(run);
    expect(after).toEqual(before);
  });

  it("保存→復元した下ごしらえで全クエリの結果(一致集合・tier)が同じ", () => {
    __resetHayForTest();
    const expected = QUERIES.map(run); // ここで全層が埋まる(英字の語を含むため)
    const rec = __exportHayForTest("k");
    expect(rec).not.toBeNull();
    __resetHayForTest();
    expect(__adoptHayForTest(items, rec!)).toBe(true);
    expect(__hayFillForTest()).toEqual({ base: items.length, roma: items.length });
    expect(QUERIES.map(run)).toEqual(expected);
  });

  it("行数の合わない保存分は採用しない", () => {
    __resetHayForTest();
    run("wanpisu");
    const rec = __exportHayForTest("k")!;
    __resetHayForTest();
    expect(__adoptHayForTest(items.slice(0, items.length - 1), rec)).toBe(false);
  });
});

describe("著者の継ぎ目の誤ヒット(2026-09-23 是正)", () => {
  const items = [
    { slug: "y-the-last-man", title: "Y:ザラストマン", title_kana: "ワイザラストマン",
      authors: [{ name: "ピア・ゲラ" }, { name: "ブライアン・K・ヴォーン" }] },
  ] as unknown as MangaListItem[];
  it("日本語の語は著者の境目をまたいで当たらない(げら|ぶら → 「ラブ」)", () => {
    __resetHayForTest();
    __setAltIndexForTest(null);
    __resetSearchCacheForTest();
    expect(searchWithTiers("ラブ", items).size).toBe(0);
  });
  it("著者名そのものでは従来どおり当たる", () => {
    __resetSearchCacheForTest();
    expect(searchWithTiers("ブライアン", items).has("y-the-last-man")).toBe(true);
    __resetSearchCacheForTest();
    expect(searchWithTiers("ゲラ", items).has("y-the-last-man")).toBe(true);
  });
});
