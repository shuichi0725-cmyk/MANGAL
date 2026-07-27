/** AI書評家リーグの週次公開スケジュール(★単一の正)。
 *
 *  過去バグ2件(節番号二重系 2026-07-12 / teaser週+2ズレ 2026-07-27)はどちらも
 *  「公開週の計算がコンポーネントごとに重複実装」だったのが根因。
 *  以後、公開数の計算は必ずこのモジュールを import する(再実装禁止)。
 *  テスト = lib/aiLeagueSchedule.test.ts(日付→公開節数の固定ケース)。
 */
export const EPOCH_SUNDAY_JST = Date.UTC(2026, 6, 5) - 9 * 3600_000; // 2026-07-05 00:00 JST = 第1節公開

/** 現在時刻(ms) → 公開済み節数(第1節から毎週日曜+1)。開始前でも最低1節は見せる。 */
export function visibleSectionCount(now: number): number {
  const weeks = Math.floor((now - EPOCH_SUNDAY_JST) / (7 * 86400_000));
  return Math.max(1, weeks + 1);
}
