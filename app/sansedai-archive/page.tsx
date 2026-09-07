import ArchiveClient from "./ArchiveClient";

/** 「三世代、今日の一冊」過去ログ(本実装 2026-07-03)。
 *  sansedai-stock.json(741件)からクライアントがJST日付で決定的に選ぶ=ホームと同じ式。
 *  静的サイトのまま毎日自動でログが伸びる。 いいねは Worker /api/like の匿名カウンタ。 */
export const metadata = {
  alternates: { canonical: "/sansedai-archive" }, title: "今日の一冊 − 過去ログ" };

export default function SansedaiArchive() {
  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      {/* ★2026-09-07 ユーザ指摘「過去ログは横幅長すぎ」: この頁だけ器(max-width)が無く
          全幅に伸びていた(/list も同様=別途)。他頁と同じ max-w-6xl 中央寄せに揃える。 */}
      <div className="mx-auto max-w-6xl lg:max-w-none">
        <div className="px-4 pb-2 pt-6">
          <h1 className="text-[19px] font-extrabold">📖 今日の一冊 − 過去ログ</h1>
          <p className="mt-1 text-[12px] leading-relaxed text-ink/60">
            案内人3人が毎日1冊ずつ。過去の推薦をさかのぼれます。♥で「この人の推し、良い」を教えてください(匿名・登録不要)。
          </p>
        </div>
        <ArchiveClient />
      </div>
    </div>
  );
}
