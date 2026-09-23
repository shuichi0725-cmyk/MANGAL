/**
 * 復元済みの一覧索引(items 配列)に「版」を紐づける(2026-09-23)。
 *
 * 版 = 列形式索引の src(元の行配列の内容ハッシュ)。検索の下ごしらえ結果を端末に保存して
 * 使い回す時の鍵にする(lib/clientSearch.ts)。items 自体に項目を足さないよう WeakMap で持つ
 * (= 索引の型・コンポーネントは無改修。版の無い索引=行配列フォールバック/head は保存しない)。
 */
const _v = new WeakMap<object, string>();

export function tagIndexVersion(items: object, v: string | null): void {
  if (v) _v.set(items, v);
}

export function indexVersion(items: object): string | null {
  return _v.get(items) ?? null;
}
