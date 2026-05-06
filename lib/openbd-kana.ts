/**
 * openBD ONIX collationkey の正規化ヘルパ (B-2, 2026-05-06).
 *
 * openBD は ヨミガナ を `collationkey` として全角 katakana で返すが、 形式は
 * 不揃い:
 *   "ハチビット カノジョ"
 *   "ブレイク タイム : Manga meets music"
 *   "アクヤク レイジョウ ... : アンソロジー コミック"
 *
 * 我々の DB の `series.title_kana` は 「きみとぼく」 のような hiragana が
 * 主流 (Wikipedia 由来)。 整合性のため:
 *   1. 「:」 以降 (副題) を切り捨て
 *   2. 連続空白を除去
 *   3. katakana → hiragana 変換
 *   4. hiragana を 1 文字も含まない結果は除外 (英字のみ等)
 *
 * 純関数なのでテスト容易。
 */

/** 全角 katakana (U+30A1..U+30F6) を hiragana へ変換。 「ー」 (U+30FC) はそのまま。 */
export function katakanaToHiragana(s: string): string {
  return s.replace(/[ァ-ヶ]/g, (c) =>
    String.fromCharCode(c.charCodeAt(0) - 0x60),
  );
}

/** hiragana を 1 文字でも含むか */
function containsHiragana(s: string): boolean {
  return /[ぁ-ゖ]/.test(s);
}

/**
 * openBD collationkey を DB に書ける形に正規化。
 * 使えない値 (英字のみ、 空文字、 hiragana ゼロ) は null を返す。
 */
export function cleanCollationKey(raw: string | null | undefined): string | null {
  if (!raw) return null;
  // 副題切り捨て (": Manga meets music" 等)
  const beforeColon = raw.split(":")[0];
  // 連続空白除去 (kana 内の word boundary は不要)
  const compact = beforeColon.replace(/\s+/g, "").trim();
  if (!compact) return null;
  // katakana → hiragana
  const hiragana = katakanaToHiragana(compact);
  // hiragana を含まない (= 全部英字 or 全角中黒等) の結果は使えない
  if (!containsHiragana(hiragana)) return null;
  return hiragana;
}
