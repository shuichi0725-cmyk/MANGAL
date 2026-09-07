"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ensureFullIndex, onFullIndex } from "@/lib/useMangaIndex";
import { prewarmAlt, prewarmSearch } from "@/lib/clientSearch";

/** PC専用の左サイドバー(2026-07-06 ユーザ要望「PCは左に検索常駐」)。
 *  lg未満では非表示(モバイルは従来の1カラム)。sticky常駐。
 *  検索は /list?q= へ(ListClient が初期クエリを読む)。
 *  ★2026-07-31 検索レスポンス改善(ユーザ報告「検索押してから表示までめっちゃ時間かかる」):
 *  ①遷移をSPA化(router.push) — 旧form GETはハードナビゲーションでモジュールキャッシュが毎回死に、
 *    22MB索引の再デコード+検索前処理が検索のたびに走っていた。
 *  ②PC(lg以上)のみホーム表示中にフル索引をidle先読み — 検索押下時には手元に揃っている。
 *    モバイルはサイドバー非表示+回線コスト配慮で先読みしない(CSS非表示でもJSは動くためmatchMediaで判定)。 */
let _warmHooked = false; // onFullIndex の二重登録防止(HeroD3 と同型)

export default function HomeSidebar({
  genres,
  prewarm = true,
}: {
  genres: Array<{ key: string; name: string }>;
  /** フル索引(br後6MB)を idle 先読みするか。省略=パスで自動判定。
   *  ★2026-09-07 全頁レール化: 読むだけの頁(漫画詳細・過去ログ等)では先読みしない
   *  = 検索する気のない訪問者に6MBを落とさない。検索が主目的の3面だけ温める。 */
  prewarm?: boolean;
}) {
  const [q, setQ] = useState("");
  const router = useRouter();
  const pathname = usePathname();
  const doWarm = prewarm ?? (pathname === "/" || pathname === "/browse" || pathname === "/list");
  // ★行き先はパス連動(2026-09-07 ユーザ①=3 で /browse の右上検索窓をここへ集約したため)。
  //   /browse に居る時はその場で絞り込む(?q= を読んで HomeClient が組み直す)。他は一覧表へ。
  const dest = pathname === "/browse" ? "/browse" : "/list";
  useEffect(() => {
    if (!doWarm) return;
    if (!window.matchMedia("(min-width: 1024px)").matches) return;
    const t = setTimeout(() => {
      ensureFullIndex();
      // ★haystack+別名まで前計算(2026-09-01): 旧=索引DLだけ先読みで、/list着地後の初回検索が
      //   「未構築のhaystackをその場で同期構築」に落ちていた(ヒーロー検索HeroD3と同じ形に揃える)
      if (!_warmHooked) {
        _warmHooked = true;
        onFullIndex((items) => {
          prewarmSearch(items);
          prewarmAlt();
        });
      }
    }, 2500);
    return () => clearTimeout(t);
  }, [doWarm]);
  return (
    <aside className="hidden lg:block w-[260px] shrink-0">
      <div className="sticky top-4 space-y-4">
        {/* 検索 */}
        <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
          <p className="text-[12px] font-extrabold text-ink/70">🔍 さがす</p>
          <form
            action={dest}
            method="get"
            className="mt-2"
            onSubmit={(e) => {
              e.preventDefault();
              router.push(q.trim() ? `${dest}?q=${encodeURIComponent(q.trim())}` : dest);
            }}
          >
            {/* ★ターミナル調(2026-09-07): /browse 右上にあった SearchBox の見た目をここへ移設。
                幅260pxなので窓とボタンは横並びでなく縦積み。 */}
            <div className="flex items-center gap-1.5 border-2 border-[var(--color-accent)] bg-[#050505] px-2.5 py-2 shadow-[3px_3px_0_rgba(217,248,67,0.14)]">
              <span className="shrink-0 text-[11px] font-bold text-[var(--color-accent)]" aria-hidden="true">
                mangal&gt;
              </span>
              <input
                type="search"
                name="q"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="題名・よみ・著者…"
                aria-label="作品を検索"
                className="d3-plain min-w-0 flex-1 text-[13px] font-bold text-[var(--color-ink)] outline-none"
              />
              <span aria-hidden="true" className="d3-blink h-[13px] w-1.5 shrink-0 bg-[var(--color-accent)]" />
            </div>
            <button
              type="submit"
              className="mt-2 w-full border-2 border-[var(--color-accent)] bg-[#050505] py-1.5 text-[12px] font-black text-[var(--color-accent)] transition active:scale-[0.97]"
            >
              検索
            </button>
          </form>
          <div className="mt-2 grid grid-cols-2 gap-1.5 text-[11px]">
            <Link href="/list" className="spring-press rounded-lg border border-[var(--color-line)] px-2 py-1.5 text-center">📋 一覧表</Link>
            <Link href="/browse" className="spring-press rounded-lg border border-[var(--color-line)] px-2 py-1.5 text-center">🎚️ 絞り込み</Link>
          </div>
        </div>
        {/* ジャンル */}
        <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
          <p className="text-[12px] font-extrabold text-ink/70">🏷️ ジャンルから</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {genres.map((g) => (
              <Link
                key={g.key}
                href={`/genre/${g.key}`}
                className="spring-press rounded-full border border-[var(--color-line)] bg-[var(--color-surface-2)]/60 px-2.5 py-1 text-[11px] text-ink/80 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
              >
                {g.name}
              </Link>
            ))}
          </div>
        </div>
        {/* 入口 */}
        <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
          <p className="text-[12px] font-extrabold text-ink/70">📚 コーナー</p>
          <nav className="mt-1.5 space-y-1 text-[12px]">
            <Link href="/shinkan" className="spring-press block rounded px-1.5 py-1 hover:bg-[var(--color-surface-2)]">📦 今月の新刊一覧</Link>
            <Link href="/rankings" className="spring-press block rounded px-1.5 py-1 hover:bg-[var(--color-surface-2)]">🏆 なんでもランキング</Link>
            <Link href="/sansedai-archive" className="spring-press block rounded px-1.5 py-1 hover:bg-[var(--color-surface-2)]">🕘 今日の一冊 過去ログ</Link>
            <Link href="/column-ai-league" className="spring-press block rounded px-1.5 py-1 hover:bg-[var(--color-surface-2)]">📝 AI書評家リーグ</Link>
            <Link href="/art-books" className="spring-press block rounded px-1.5 py-1 hover:bg-[var(--color-surface-2)]">🎨 画集</Link>
            <Link href="/about" className="spring-press block rounded px-1.5 py-1 hover:bg-[var(--color-surface-2)]">🔰 使い方</Link>
          </nav>
        </div>
      </div>
    </aside>
  );
}
