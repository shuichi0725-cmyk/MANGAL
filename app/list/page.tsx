import Link from "next/link";
import { Suspense } from "react";
import ListClient from "@/components/ListClient";
import { DesignNav } from "@/lib/homeDesign";
import { hubDefs, hubHref } from "@/lib/hubs";
import { loadMasters, loadArtBooks, loadIndexSummary } from "@/lib/loadData";
import type { ListBundle } from "@/lib/schema";

const SITE = "https://mangal-db.com";

/** ★SEO(2026-09-04): /list は既定title「MANGAL — 日本の漫画データベース」+ 静的HTMLに作品リンク0本
 *  (可視401字)のまま sitemap とフッターに載っていた。 頁別 title/description を焼き、JS前でも
 *  意味のある本文(件数・使い方・索引への導線)を出す。 ★サフィックスは layout template が付ける。 */
export function generateMetadata() {
  const n = loadIndexSummary().total.toLocaleString();
  const title = `漫画 全作品一覧表（${n}作品）`;
  const description =
    `MANGAL掲載の漫画${n}作品を一覧表で。題名・著者・出版年・巻数・完結/連載中で並べ替え、検索・絞り込みができます。` +
    "題名索引・著者・雑誌・出版社・年別・ジャンル別の索引からも探せます。";
  return { title, description, alternates: { canonical: `${SITE}/list` } };
}

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
  const masters = loadMasters();
  const data: ListBundle = { manga: [], artBooks: loadArtBooks(), ...masters };
  const total = loadIndexSummary().total;
  const magazines = hubDefs("magazine").slice(0, 8);
  const chip =
    "rounded-full border border-[var(--color-line)] px-2.5 py-0.5 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]";
  return (
    <div className="min-h-screen bg-[var(--color-surface)] pb-10">
      <DesignNav current={11} />
      <header className="flex items-baseline justify-between border-b-2 border-ink px-3 py-3">
        <h1 className="text-base font-extrabold">📋 一覧表</h1>
        <span className="text-[11px] text-ink/55">フィルター×並び順は自由に掛け算</span>
      </header>
      {/* ★サーバ描画の説明(JS前でも件数と使い方が出る = 白紙対策・SEO) */}
      <p className="px-3 pt-3 text-[12.5px] leading-relaxed text-ink/70">
        掲載中の漫画 全 <b className="tabular-nums">{total.toLocaleString()}</b> 作品を一覧表で表示します。
        列見出しで並べ替え、検索窓で題名・著者を絞り込めます。
      </p>
      {/* ★ListClient は useSearchParams を使うため Suspense 境界が要る(静的書き出しではここまでCSR)。
          fallback は null にしない(2026-08-01 /browse の教訓: 本文が丸ごと消える) */}
      <Suspense fallback={<div className="px-3 py-8 text-sm text-ink/55">一覧表を読み込み中…</div>}>
        <ListClient data={data} />
      </Suspense>
      {/* ★索引から探す(常設・サーバ描画): 題名/著者/雑誌/出版社/年/ジャンル = 静的な内部リンク網 */}
      <section className="mt-8 border-t border-[var(--color-line)] px-3 pt-5 text-[12px] text-ink/70">
        <h2 className="text-[13px] font-bold text-ink/80">索引から探す</h2>
        <p className="mt-2 flex flex-wrap gap-1.5 text-[11.5px]">
          <Link href="/titles" className={chip}>題名索引（50音順）</Link>
          <Link href="/authors" className={chip}>著者一覧</Link>
          <Link href="/magazine" className={chip}>雑誌別</Link>
          <Link href="/publisher" className={chip}>出版社別</Link>
          <Link href="/year" className={chip}>連載開始年別</Link>
          <Link href="/shinkan" className={chip}>今月の新刊</Link>
          <Link href="/anime" className={chip}>アニメ化作品</Link>
        </p>
        <h3 className="mt-4 text-[12px] font-bold text-ink/75">ジャンル</h3>
        <p className="mt-1.5 flex flex-wrap gap-1.5 text-[11.5px]">
          {masters.genres.map((g) => (
            <Link key={g.key} href={`/genre/${g.key}`} className={chip}>
              {g.name}
            </Link>
          ))}
        </p>
        {magazines.length > 0 && (
          <>
            <h3 className="mt-4 text-[12px] font-bold text-ink/75">主な連載誌</h3>
            <p className="mt-1.5 flex flex-wrap gap-1.5 text-[11.5px]">
              {magazines.map((d) => (
                <Link key={d.key} href={hubHref("magazine", d.key)} className={chip}>
                  {d.name}
                </Link>
              ))}
            </p>
          </>
        )}
      </section>
    </div>
  );
}
