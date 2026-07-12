/** アニメ季節コーナー共通ヘルパ (= data/anime-seasons-view.json を読む側の語彙)。2026-07-12 */

export type AnimeSeasonEntry = {
  slug: string;
  title: string;
  cover?: string | null;
  authors?: string[];
  anime_title?: string | null;
  source?: string | null;
  pop: number;
};

export type AnimeSeasonsView = {
  order: string[]; // "2026-summer" 昇順
  seasons: Record<string, AnimeSeasonEntry[]>;
};

const SEASON_JA: Record<string, string> = {
  winter: "冬",
  spring: "春",
  summer: "夏",
  fall: "秋",
};

/** "2026-summer" → "2026年夏" */
export function seasonLabel(key: string): string {
  const [y, s] = key.split("-");
  return `${y}年${SEASON_JA[s] ?? s}`;
}

/** 原作種別の表示ラベル(= AniList source → 日本語) */
export function sourceLabel(source?: string | null): string {
  switch (source) {
    case "MANGA":
    case "ONE_SHOT":
      return "漫画原作";
    case "LIGHT_NOVEL":
    case "NOVEL":
    case "WEB_NOVEL":
      return "ラノベ原作";
    case "ORIGINAL":
      return "コミカライズ";
    case "VIDEO_GAME":
    case "VISUAL_NOVEL":
      return "ゲーム原作";
    default:
      return "原作もの";
  }
}

const SEASON_IDX: Record<string, number> = { winter: 0, spring: 1, summer: 2, fall: 3 };

/** "2026-summer" → 通し番号(年×4+季)。時系列比較用 */
function seasonNum(key: string): number {
  const [y, s] = key.split("-");
  return parseInt(y, 10) * 4 + (SEASON_IDX[s] ?? 0);
}

/** いまのJST日付が属する季キー("2026-summer")。viewに無ければ時系列で直近過去 */
export function currentSeasonKey(order: string[]): string {
  const jst = new Date(Date.now() + 9 * 3600 * 1000);
  const y = jst.getUTCFullYear();
  const m = jst.getUTCMonth() + 1;
  const s = m <= 3 ? "winter" : m <= 6 ? "spring" : m <= 9 ? "summer" : "fall";
  const now = seasonNum(`${y}-${s}`);
  const past = order.filter((k) => seasonNum(k) <= now);
  return past.length ? past[past.length - 1] : order[order.length - 1];
}

/** 前後の季キー(履歴ナビ用)。orderは時系列昇順前提 */
export function adjacentSeasons(order: string[], key: string): { prev?: string; next?: string } {
  const i = order.indexOf(key);
  if (i < 0) return {};
  return { prev: order[i - 1], next: order[i + 1] };
}
