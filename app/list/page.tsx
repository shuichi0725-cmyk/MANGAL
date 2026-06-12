import ListTableClient, { type ListRow } from "@/components/ListTableClient";
import { DesignNav, latestDate, volCount } from "@/lib/homeDesign";
import { loadAllManga } from "@/lib/loadData";

/** 一覧表(案6の正式な行き先): 全作品のスプレッドシート型ビュー。
 *  列タップでソート・検索・状態絞り込み。
 *
 *  ★読み込み設計(2026-06-13 ユーザ裁定「初期100件くらいが丁度よい」):
 *    本番(69k)では全行埋込み禁止(~7MBになる)。トップ3層化と同じパターンで、
 *    ①初期=かな順100件のみ埋込(~30KB) ②「さらに表示」=静的チャンクJSON(500件
 *    単位)を逐次fetch ③ソート切替=ソート別に事前生成したチャンク列へ切替
 *    ④検索=共用の軽量検索索引(gzip+IndexedDBキャッシュ)。 全て静的ファイルで成立。
 *    プレビュー(100件)は全量=初期量なので現実装のままでよい。 チャンク生成は
 *    本番ビルド(R2移行)時に実装。 */
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
    genres: m.genres
      .map((g) => data.genres.find((x) => x.key === g)?.name ?? g)
      .filter((v, i, a) => a.indexOf(v) === i),
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
