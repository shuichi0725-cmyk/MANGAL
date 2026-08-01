import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { normalizeForSearch } from "./romaji";

/**
 * ★カナ数詞foldの単一正規表現化(2026-08-01)が、旧実装と★出力が1文字も違わない★ことの証明。
 *
 * 旧実装は17語×(カタカナ+ひらがな)を split/join で順に全文置換していた。
 * 新実装は同じ優先順で並べた1本の交替正規表現を1回だけ走らせる。
 * 交替は「各位置で先に書いた候補から試す」ので原理的には等価だが、
 * 「先に置換した結果に後の語が跨って当たる」型の差は理屈だけでは潰し切れない。
 * そこで★実データ全文字列★と★語の全組み合わせ★で機械的に突き合わせる。
 *
 * このテストは新実装を触ったときの番人であって、消してはいけない。
 * (オラクル=下の oldNormalizeForSearch は 2026-08-01 時点の実装の写し。動かさない)
 */

// ───────── オラクル: 2026-08-01 以前の実装をそのまま写したもの ─────────
const KANA_NUMS: Array<[string, string]> = [
  ["トゥエルブ", "12"], ["イレブン", "11"], ["ファースト", "1"], ["セカンド", "2"],
  ["サード", "3"], ["フォース", "4"], ["フィフス", "5"], ["シックス", "6"],
  ["セブン", "7"], ["エイト", "8"], ["ナイン", "9"], ["テン", "10"],
  ["ファイブ", "5"], ["フォー", "4"], ["スリー", "3"], ["ツー", "2"], ["ワン", "1"],
];
const ROMAN_MAP: Record<string, string> = {
  i: "1", ii: "2", iii: "3", iv: "4", v: "5", vi: "6", vii: "7", viii: "8",
  ix: "9", x: "10", xi: "11", xii: "12",
};
function oldFoldNumerals(s: string): string {
  s = s.replace(/(?<![a-z])[ivx]{1,4}(?![a-z])/g, (m) => ROMAN_MAP[m] ?? m);
  for (const [k, v] of KANA_NUMS) {
    s = s.split(k).join(v);
    const hira = k.replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60));
    if (hira !== k) s = s.split(hira).join(v);
  }
  s = s.replace(/[一二三四五六七八九〇零]/g, (c) => "12345678900"["一二三四五六七八九〇零".indexOf(c)]);
  return s;
}
function oldFoldUnicodeRoman(s: string): string {
  return s.replace(/[Ⅰ-Ⅻⅰ-ⅻ]/g, (c) => {
    const n = (c.charCodeAt(0) - (c.charCodeAt(0) >= 0x2170 ? 0x2170 : 0x2160)) + 1;
    return String(n);
  });
}
function oldNormalizeForSearch(input: string): string {
  return oldFoldNumerals(
    oldFoldUnicodeRoman(input)
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .normalize("NFKC")
      .toLowerCase(),
  )
    .replace(/[ー・\-\s]/g, "")
    .replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60))
    .replace(/[惡應戀壽假萬圓學國]/g, (c) => "悪応恋寿仮万円学国"["惡應戀壽假萬圓學國".indexOf(c)])
    .trim();
}
// ──────────────────────────────────────────────────────────────

const HIRA = (k: string) => k.replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60));
const WORDS = [...KANA_NUMS.map(([k]) => k), ...KANA_NUMS.map(([k]) => HIRA(k))];

function diffAgainstOracle(strings: Iterable<string>): { n: number; bad: Array<[string, string, string]> } {
  let n = 0;
  const bad: Array<[string, string, string]> = [];
  for (const s of strings) {
    n++;
    const a = normalizeForSearch(s);
    const b = oldNormalizeForSearch(s);
    if (a !== b && bad.length < 10) bad.push([s, b, a]);
  }
  return { n, bad };
}

describe("カナ数詞fold: 単一正規表現化が旧実装と等価", () => {
  it("語の全組み合わせ(単体・2連・間に文字を挟む・3連)で一致", () => {
    const cases: string[] = [];
    for (const w of WORDS) {
      cases.push(w, `の${w}`, `${w}の`, `X${w}Y`, `${w}${w}`);
      for (const x of WORDS) {
        cases.push(`${w}${x}`, `${w}あ${x}`, `${w}1${x}`, `${w}ー${x}`, `${w}・${x}`);
      }
    }
    // 3連は語数が多いので代表を回す(重なりが起きうる短語を優先)
    const short = ["ワン", "ツー", "テン", "フォー", "フォース", "セブン", "わん", "つー", "ふぉー"];
    for (const a of short) for (const b of short) for (const c of short) cases.push(a + b + c);
    // 漢数字・ローマ数字・全角との混在
    for (const w of WORDS) cases.push(`${w}二`, `${w}Ⅱ`, `${w}II`, `${w}ｖｉｉ`, `第${w}巻`);

    const { n, bad } = diffAgainstOracle(cases);
    expect({ 件数: n, 不一致: bad }).toEqual({ 件数: n, 不一致: [] });
  });

  it("実索引の全文字列(題・よみ・副題・著者名・著者よみ)で一致", () => {
    const idx = path.join(__dirname, "..", "data", "manga-list-index.json");
    if (!fs.existsSync(idx)) {
      // データが無い環境(CI等)では上の合成ケースだけで担保する
      return;
    }
    const raw = JSON.parse(fs.readFileSync(idx, "utf8")) as { f: string[]; d: unknown[][] };
    const col = (name: string) => raw.f.indexOf(name);
    const cols = ["title", "title_kana", "subtitle"].map(col).filter((i) => i >= 0);
    const ai = col("authors");
    const strings: string[] = [];
    for (const row of raw.d) {
      for (const c of cols) if (typeof row[c] === "string") strings.push(row[c] as string);
      const a = row[ai];
      if (typeof a === "string") strings.push(a);
      else if (Array.isArray(a)) strings.push(...(a as unknown[]).map((x) => JSON.stringify(x)));
    }
    const { n, bad } = diffAgainstOracle(strings);
    expect({ 件数: n, 不一致: bad }).toEqual({ 件数: n, 不一致: [] });
    expect(n).toBeGreaterThan(100_000);
  }, 300_000);
});
