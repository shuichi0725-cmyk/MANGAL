// ★cover URL 軽量化(索引): 楽天サムネの共通 prefix/default suffix を剥がし可変部のみ保存。
//   保存形 = "book/cabinet/5757/57572345.gif" (http 無し) / 例外(300x300・非楽天)は full URL のまま(http で始まる)。
//   client(useMangaIndex) と server(loadMangaListIndex) のデコード両方で fullCover で復元 → コンポーネント無改修。
const RK_PRE = "https://thumbnail.image.rakuten.co.jp/@0_mall/";
// ★2026-07-25 200x200 → 300x300。楽天サムネは「1枚のマスター+_exサイズ指定」で、
//   largeImageUrl(=_ex=200x200) は最大ではない。300 にすると 140x200 → 210x300 になり、
//   マスターが大きい現行作品は明確に鮮明化する(古書=マスターが小さい本は据置きで容量も増えない)。
//   実測: 本番20枚平均 13.9KB → 23.3KB (1.68倍)。書影は楽天CDN直リンク = R2の課金には影響しない。
const RK_SUF = "?_ex=300x300";

// ★電子書籍版(楽天Kobo)の書影の目印(2026-09-03 ユーザ裁定)。
//   紙の書影が公開されていない旧作は Kobo の電子版書影で埋めている(scripts/_kobo-covers.py)。
//   電子版は復刻レーベルが独自装丁を付けることがある(グループ・ゼロ「マンガの金字塔」=
//   モノトーン処理+題字帯の統一装丁で、1989年の集英社版カバーとは別物)。
//   ★出さない ではなく **出したうえで巻情報の下に注意書きを添える** = ユーザ裁定。
//   slim形("rakutenkobo-ebooks/cabinet/…") でも full URL でも同じ部分文字列で判定できる。
const KOBO_MARK = "rakutenkobo-ebooks";

/** その書影が電子書籍版(楽天Kobo)由来か。 null安全。 */
export function isEbookCover(c: string | null | undefined): boolean {
  return !!c && c.includes(KOBO_MARK);
}

/** slim(可変部) or full URL → 表示用の full URL に復元。 null安全。 */
export function fullCover(c: string | null | undefined): string | null {
  if (!c) return null;
  if (c.startsWith("http")) return c; // 例外は full のまま
  return RK_PRE + c + RK_SUF;
}
