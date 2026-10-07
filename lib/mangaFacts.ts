/**
 * 作品頁の基本情報欄(= 見本その2「D3 コマ割り」・2026-10-07 ユーザ裁定)の判断だけを切り出したもの。
 * 表示部品は components/MangaFacts.tsx、見た目は components/manga-facts.css。
 *
 * 真ん中の段は「著者 | 連載誌(無ければ出版社)」の斜めの2コマ。 左のコマは幅が狭い
 * (360px 幅で大きい字が1行に約7字)ので、名前が多い・長い時は斜めをやめて縦に積む。
 * 実測(2026-10-07 本番索引 69,515作): 著者1人 92.9% / 2人 5.3% / 3人以上 1.9%。
 * 著者名の合計は 中央値4字・99%点19字・99.9%点101字(アンソロジー)。 「その他」(監修など)は約2%で 中央値8字。
 */

/** 文字数(サロゲートペアを1字と数える)。 名前どうしの区切り「・」も1字に数える。 */
function textLen(names: string[]): number {
  return names.reduce((s, x) => s + [...x].length, 0) + Math.max(0, names.length - 1);
}

/** 著者のコマを斜めの2コマにせず、縦に積む(=横幅いっぱいのコマ2つ)か。 */
export function stackPeople(
  authors: string[],
  originals: string[],
  credits: { role: string; names: string[] }[],
): boolean {
  if (authors.length >= 3) return true;
  if (textLen(authors) > 14) return true;
  // 原作・その他は小さい字の行。 合わせて約2行を超えるなら積む
  const extra = (originals.length ? 3 + textLen(originals) : 0) +
    credits.reduce((s, c) => s + [...c.role].length + 1 + textLen(c.names), 0);
  return extra > 16;
}

/** 名前が多い時は大きい字をやめる(アンソロジーで20人以上並ぶ)。 */
export function manyPeople(authors: string[]): boolean {
  return authors.length >= 4;
}

/**
 * 説明文のコマ(見本「B あらすじのコマ」・2026-10-08 ユーザ裁定)に何を出すか。
 * 説明文(synopsis)が主役。 説明文が無い頁だけキャッチを「作品紹介」として出す
 * (キャッチだけの頁 = 1巻もの等 8,613頁・12%。 旧 = 何も出なかった)。
 * 両方ある頁はキャッチを出さない: キャッチの言い回しの2割以上が説明文と重なる頁が49%あり、
 * 並べると同じ話を2回読ませる(2026-10-07 実測・本番39,049作)。
 */
export function pickDescription(
  synopsis: string | null | undefined,
  catchCopy: string | null | undefined,
): { label: "あらすじ" | "作品紹介"; text: string } | null {
  const s = synopsis?.trim();
  if (s) return { label: "あらすじ", text: s };
  const c = catchCopy?.trim();
  if (c) return { label: "作品紹介", text: c };
  return null;
}
