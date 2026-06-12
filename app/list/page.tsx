import ListTableClient, { type ListRow } from "@/components/ListTableClient";
import { DesignNav, latestDate, volCount } from "@/lib/homeDesign";
import { loadAllManga } from "@/lib/loadData";

/** 一覧表(案6の正式な行き先): 全作品のスプレッドシート型ビュー。
 *  列タップでソート・検索・状態絞り込み。 データはビルド時埋込(静的)。 */
export default function ListPage() {
  const data = loadAllManga();
  const rows: ListRow[] = data.manga.map((m) => ({
    slug: m.slug,
    title: m.title,
    kana: m.title_kana || "",
    authors: m.authors.map((a) => a.name).join("・"),
    vols: volCount(m),
    year: m.year_started ?? null,
    status: m.status,
    latest: latestDate(m)?.slice(0, 7) ?? "",
  }));
  return (
    <div className="min-h-screen bg-white pb-10">
      <DesignNav current={11} />
      <header className="flex items-baseline justify-between border-b-2 border-ink px-3 py-3">
        <h1 className="text-base font-extrabold">📋 一覧表</h1>
        <span className="text-[11px] text-ink/55">列タップで並べ替え</span>
      </header>
      <ListTableClient rows={rows} />
    </div>
  );
}
