/**
 * 日本語照合の共有 Collator。
 *
 * ★なぜ共有するのか(2026-07-22 に filters.ts で導入 → 2026-08-01 に共通化)
 *   `a.localeCompare(b, "ja")` は呼ぶたびにロケール機構を起こすため、
 *   67,000件の並べ替え(= 比較およそ100万回)で桁違いに効く。
 *   実測: 一覧の人気順は 48.5% が popularity 未設定で最終タイブレークの
 *   文字列比較まで落ちるため、ここが並べ替え時間の大半を占めていた。
 *
 * 使う側は必ずこのインスタンスを使い、`localeCompare` を直接呼ばない。
 */
export const jaCollator = new Intl.Collator("ja");

/** ロケール指定なしの既定照合(日付文字列など、言語に依存しない比較用)。 */
export const defaultCollator = new Intl.Collator();
