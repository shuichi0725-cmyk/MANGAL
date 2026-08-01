import type { MangaListItem } from "./schema";

/**
 * 一覧の並べ替え(ListClient から切り出し)。
 *
 * ★切り出しの目的(2026-08-01): 実索引に対する検索スナップショット試験
 * (`lib/searchSnapshot.test.ts`)が「本番と同じ並べ替え」を通すため。
 * 内部にコピーを持つと、テストが緑でも本番だけ壊れる型のドリフトが起きる。
 *
 * ★ここは 2026-08-01 時点の ListClient の挙動をそのまま転写したもの。
 * 変更するとスナップショットに必ず差分が出る(= 意図した変更かを人が確認する)。
 */

export type SortId = "kana" | "year-asc" | "year-desc" | "vols-desc" | "latest-desc" | "popularity";

export const SORTS: Array<{ id: SortId; label: string }> = [
  { id: "popularity", label: "人気順" },
  { id: "kana", label: "50音順" },
  { id: "year-asc", label: "開始が古い" },
  { id: "year-desc", label: "開始が新しい" },
  { id: "vols-desc", label: "巻数が多い" },
  { id: "latest-desc", label: "最新刊が新しい" },
];

/** 表示・並べ替え共通の巻数(一覧表の「巻数」列と同じ値)。 */
export function volCount(m: MangaListItem): number {
  return m.max_edition_volumes;
}
/** 表示・並べ替え共通の最新刊日(未設定は空文字)。 */
export function latestDate(m: MangaListItem): string {
  return m.latest_date ?? "";
}

/** 並べ替えの比較器。 */
export function compareBy(sortId: SortId): (a: MangaListItem, b: MangaListItem) => number {
  return (a, b) => {
    switch (sortId) {
      case "popularity":
        return (
          (b.popularity ?? 0) - (a.popularity ?? 0) ||
          (b.score ?? 0) - (a.score ?? 0) ||
          a.title_kana.localeCompare(b.title_kana, "ja")
        );
      case "year-asc":
        return (a.year_started ?? 9999) - (b.year_started ?? 9999);
      case "year-desc":
        return (b.year_started ?? 0) - (a.year_started ?? 0);
      case "vols-desc":
        return volCount(b) - volCount(a);
      case "latest-desc":
        return latestDate(b).localeCompare(latestDate(a));
      default:
        return (a.title_kana || a.title).localeCompare(b.title_kana || b.title, "ja");
    }
  };
}

/**
 * 一覧の行を並べ替える。
 * @param rows      絞り込み済みの行(この配列は破壊しない)
 * @param sortId    有効な並び順(検索中×未タッチなら呼び手が "popularity" を渡す)
 * @param tiers     検索中なら searchWithTiers の結果。null なら tier 整列しない
 * @param sortTouched ユーザが並び順を明示選択したか(true なら tier 整列しない)
 */
export function sortRows(
  rows: MangaListItem[],
  sortId: SortId,
  tiers: Map<string, number> | null,
  sortTouched: boolean,
): MangaListItem[] {
  const sorted = [...rows].sort(compareBy(sortId));
  // ★案A(2026-07-23): 検索中×並び順未タッチ → 一致の強い順(同tier内=人気順。安定ソート)
  if (tiers && !sortTouched) {
    sorted.sort((a, b) => (tiers.get(a.slug) ?? 9) - (tiers.get(b.slug) ?? 9));
  }
  return sorted;
}
