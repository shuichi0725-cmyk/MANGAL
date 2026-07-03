import ArchiveClient from "./ArchiveClient";

/** 「三世代、今日の一冊」過去ログ(本実装 2026-07-03)。
 *  sansedai-stock.json(741件)からクライアントがJST日付で決定的に選ぶ=ホームと同じ式。
 *  静的サイトのまま毎日自動でログが伸びる。 いいねは Worker /api/like の匿名カウンタ。 */
export const metadata = { title: "三世代、今日の一冊 − 過去ログ | MANGAL" };

export default function SansedaiArchive() {
  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="px-4 pb-2 pt-6">
        <h1 className="text-[19px] font-extrabold">👥 三世代、今日の一冊 − 過去ログ</h1>
        <p className="mt-1 text-[12px] leading-relaxed text-ink/60">
          三世代の案内人が毎日1冊ずつ。過去の推薦をさかのぼれます。♥で「この人の推し、良い」を教えてください(匿名・登録不要)。
        </p>
      </div>
      <ArchiveClient />
    </div>
  );
}
