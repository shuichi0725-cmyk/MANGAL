import { DesignNav } from "@/lib/homeDesign";
import AuditDateOrder from "@/components/AuditDateOrder";

export const metadata = { robots: { index: false, follow: false } };  // 実験頁=非索引

/** [調査用] 発売日逆行の監査ビュー。 /audit/date-order.json(db-v2由来)を読み一覧表示。
 *  本番データ・本番ページには影響しない独立ルート。 */
export default function AuditDateOrderPage() {
  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-16">
      <DesignNav current={11} />
      <AuditDateOrder />
    </div>
  );
}
