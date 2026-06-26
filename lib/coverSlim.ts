// ★cover URL 軽量化(索引): 楽天サムネの共通 prefix/default suffix を剥がし可変部のみ保存。
//   保存形 = "book/cabinet/5757/57572345.gif" (http 無し) / 例外(300x300・非楽天)は full URL のまま(http で始まる)。
//   client(useMangaIndex) と server(loadMangaListIndex) のデコード両方で fullCover で復元 → コンポーネント無改修。
const RK_PRE = "https://thumbnail.image.rakuten.co.jp/@0_mall/";
const RK_SUF = "?_ex=200x200";

/** slim(可変部) or full URL → 表示用の full URL に復元。 null安全。 */
export function fullCover(c: string | null | undefined): string | null {
  if (!c) return null;
  if (c.startsWith("http")) return c; // 例外は full のまま
  return RK_PRE + c + RK_SUF;
}
