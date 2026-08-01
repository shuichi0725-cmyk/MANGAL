import { toRomaji, toHiragana } from "wanakana";

export function kanaToRomaji(input: string): string {
  return toRomaji(input).toLowerCase();
}

export function romajiToHiragana(input: string): string {
  return toHiragana(input.toLowerCase());
}

/**
 * 検索照合用の正規化:
 * - ダイアクリティカルマーク（マクロン等）を除去
 * - NFKC で全角半角を統一（半角中黒 ･ U+FF65 → ・ U+30FB も統一）
 * - 小文字化
 * - 長音符・ハイフン・空白・中黒(・)を除去
 *   （"wanpi-su"="wanpisu" / "シャングリラ・フロンティア"="シャングリラフロンティア" を同一視。
 *    中黒は位置揺れも吸収=「シャングリ・ラフロンティア」でも当たる）
 * - ★カタカナ→ひらがな畳み込み(2026-07-21): 「こちかめ」⇄「コチカメ」等、クエリと
 *   データのかな表記種が違っても直接当たる(クエリ・haystack双方が本関数を通る前提)
 * - ★数字表記揺れ折り畳み(2026-07-27 会議決定): ローマ数字(Ⅱ/II)・漢数字(単字)・カナ数詞
 *   (ツー/スリー等)を算用数字へ統一。「ロザリオとバンパイアseason2」でseasonⅡ頁が、
 *   「世紀末ダーリン2」で年次頁が当たる。クエリ・haystack双方が同関数を通るので
 *   置換の衝突(ワンピース→1ピース等)は両側で一貫し自己一致は壊れない。
 *   ※データ監査側の同種正規化は scripts/_title_numnorm.py(検出器用・別実装)。片方を
 *   直したらもう片方も見ること。位取り漢数字(十百千)は誤爆リスクで両実装とも対象外。
 */
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
/**
 * ★カナ数詞の畳み込みは「1本の正規表現で1回走査」(2026-08-01 性能改修)。
 *
 * 旧実装は KANA_NUMS を回しながら毎回 split/join で全文を走査し(17語×カタカナ+ひらがな=
 * 最大34パス)、さらに★ひらがな形をループの中で毎回 replace で作り直していた★。
 * 本番67k件のhaystack構築で実測: normalizeForSearch 5,510ms のうち 4,729ms がここ。
 * 定数を巻き上げるだけで1,949ms、単一正規表現なら31ms(=152倍)。
 *
 * 等価性: 交替(|)は「各位置で先に書いた候補から試す」ので、旧実装の適用順
 * (K1→H1→K2→H2→…)と同じ順で並べれば優先度が一致する(フォース→フォーの
 * 長い方優先もこの順序で保たれる)。置換結果は数字のみで新たな一致を生まない。
 * ★lib/romaji.foldNumerals.test.ts が実索引の全文字列(36万本)+全語の組み合わせで
 * 旧実装との出力一致を突き合わせている(差異ゼロを常時検証)。
 */
const KANA_NUM_MAP = new Map<string, string>();
const KANA_NUM_RE = (() => {
  const alts: string[] = [];
  for (const [k, v] of KANA_NUMS) {
    if (!KANA_NUM_MAP.has(k)) {
      KANA_NUM_MAP.set(k, v);
      alts.push(k);
    }
    const hira = k.replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60));
    if (hira !== k && !KANA_NUM_MAP.has(hira)) {
      KANA_NUM_MAP.set(hira, v);
      alts.push(hira);
    }
  }
  return new RegExp(alts.join("|"), "g");
})();

const KANJI_NUMS = "一二三四五六七八九〇零";
const KANJI_NUM_DIGITS = "12345678900";

function foldNumerals(s: string): string {
  // ローマ数字(ASCII綴り): 英字に挟まれていない単独トークンのみ(ILLUSION等の語中は不変)。
  // 空白除去より前に呼ぶこと(境界が要る)。
  s = s.replace(/(?<![a-z])[ivx]{1,4}(?![a-z])/g, (m) => ROMAN_MAP[m] ?? m);
  // ★ひらがな表記も同じに畳む(2026-07-28 ユーザ報告「検索が機能してない」の退行修正):
  //   カナ数詞foldはかな→カナ畳み込みより前に走るため、カタカナ側だけ畳むと
  //   「わんぴーす」(→わんぴいす)と題「ワンピース」(→1ぴいす)が二度と一致しなくなっていた。
  //   クエリはひらがな入力が多い=対称に畳んで自己一致を回復する。
  s = s.replace(KANA_NUM_RE, (m) => KANA_NUM_MAP.get(m) as string);
  s = s.replace(/[一二三四五六七八九〇零]/g, (c) => KANJI_NUM_DIGITS[KANJI_NUMS.indexOf(c)]);
  return s;
}

/** Unicodeローマ数字文字(Ⅱ等)を数字へ。★NFKCより前に呼ぶ(NFKCはⅡ→"II"へ分解し
 *  「seasonⅡ」が"seasonii"と連結して境界判定が効かなくなる=2026-07-27実測)。 */
function foldUnicodeRoman(s: string): string {
  return s.replace(/[Ⅰ-Ⅻⅰ-ⅻ]/g, (c) => {
    const n = (c.charCodeAt(0) - (c.charCodeAt(0) >= 0x2170 ? 0x2170 : 0x2160)) + 1;
    return String(n);
  });
}

export function normalizeForSearch(input: string): string {
  return foldNumerals(
    foldUnicodeRoman(input)
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
