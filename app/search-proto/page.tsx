import { DesignNav } from "@/lib/homeDesign";
import SearchProto from "@/components/SearchProto";

/** 索引プロトタイプ(仕様v2 S1)。 既存ページを壊さない独立ルート。
 *  /idx/search.json(_build-index.py が生成)を遅延ロードしてクライアント検索。 */
export default function SearchProtoPage() {
  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-16">
      <DesignNav current={11} />
      <SearchProto />
    </div>
  );
}
