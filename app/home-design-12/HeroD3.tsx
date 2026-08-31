"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useEffect } from "react";
import { prewarmAlt, prewarmSearch } from "@/lib/clientSearch";
import { dotGothic } from "@/lib/fonts";
import { ensureFullIndex, onFullIndex } from "@/lib/useMangaIndex";

/** ★ホーム到着で検索を全ウォーム(2026-08-31 ユーザ裁定「ホームに来たら全読み。フォーカス待ちにしない」):
 *  旧(8/18)はDLキャッシュを温めるだけだった。素のGETフォーム遷移=フルページロードでJSヒープが
 *  捨てられるため、/browse到着後に br解凍→JSON.parse→67kデコード→haystack構築をゼロから
 *  やり直していた(=「解凍される」体感の正体)。他ページからの<Link>遷移(ヒープ生存+クエリ無し
 *  着地で打つまでに温まる)との差はここ。
 *  新: ①到着後の手すきでフル索引取得+デコード+haystack前計算+別名索引まで済ませる
 *      (全部既存の細切れ実装: 8,000行/刻みデコード+500行/刻みhaystack=初描画を汚さない)
 *      ②submitをJSで横取りして router.push のSPA遷移に=モジュールキャッシュが生きたまま
 *        /browseに着く。一度読んだらサイト内回遊中は再読しない。
 *  フォームのaction/methodはJS無効時の保険でそのまま残す(その時だけ従来のMPA遷移)。
 *  節度: saveData/2G回線は到着ウォームをスキップ(検索窓フォーカス=明示的意思の時だけ開始)。 */
let _hooked = false;
function warmSearch(): void {
  ensureFullIndex(); // 冪等。DL失敗後もフォーカス等の呼び直しで再試行が効く
  if (!_hooked) {
    _hooked = true;
    onFullIndex((items) => {
      prewarmSearch(items); // haystack細切れ前計算
      prewarmAlt(); // 別名索引も先読み(初回検索後の後追い再照合を無くす)
    });
  }
}
function warmSearchIdle(): void {
  type NetInfo = { saveData?: boolean; effectiveType?: string };
  const conn = (navigator as { connection?: NetInfo }).connection;
  if (conn?.saveData || /2g/.test(conn?.effectiveType ?? "")) return;
  if (typeof requestIdleCallback === "function") requestIdleCallback(() => warmSearch(), { timeout: 4000 });
  else setTimeout(warmSearch, 1500);
}

/** D3ヒーロー → E融合型(2026-08-15 ユーザ指示「ヘッダーから検索窓までEを取り入れる」):
 *  - コピーは固定「次の一冊が、見つかる。」(E案採用。旧ランダムコピー16種は退役=履歴はgit)
 *  - サブテキストは「N作品・M冊の書誌を収録。」まで(ユーザ指示「書影以降はいらない」)
 *  - 検索窓=ターミナル式 mangal> プロンプト+点滅カーソル。素のGETフォーム=JS前でも検索できる
 *    (ボタンは無し=Enter/検索キーで送信。E案の見た目を優先)
 *  - 走査線背景(E案)。SEO対策=巨大タイポはh1にしない(h1相当はページ側のsr-only) */
export default function HeroD3({ total, books }: { total: number; books: number }) {
  const router = useRouter();
  useEffect(() => {
    warmSearchIdle();
    router.prefetch("/browse"); // SPA遷移の初手(RSCペイロード)も温める(旧: /browse文書fetchの置換)
  }, [router]);
  // JSが生きていればSPA遷移(=温めたヒープを持ち越す)。無効時はこのハンドラ自体が無く素のGETが走る
  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const q = String(new FormData(e.currentTarget).get("q") ?? "").trim();
    router.push(q ? `/browse?q=${encodeURIComponent(q)}` : "/browse");
  };
  return (
    <section
      className="relative overflow-hidden border-b-[3px] border-[var(--color-accent)] px-4 pb-6 pt-7"
      style={{
        background:
          "repeating-linear-gradient(0deg, transparent 0px, transparent 3px, rgba(217,248,67,0.02) 3px, rgba(217,248,67,0.02) 4px)",
      }}
    >
      <div className="mb-3 text-[9.5px] tracking-[0.24em] text-ink/50">// 日本の漫画データベース</div>
      {/* 装飾タイポ(h1ではない) */}
      <p className={`${dotGothic.className} text-[37px] leading-[1.32] text-ink`}>
        次の一冊が、
        <br />
        見つかる<span className="text-[var(--color-accent)]">。</span>
      </p>
      <p className="mt-3 text-[11px] leading-relaxed text-ink/65">
        {total.toLocaleString()}作品・{books.toLocaleString()}冊の書誌を収録。
      </p>
      {/* 素のGETフォーム=JS前でも検索できる(/browseのシェルと同じ思想) */}
      <form
        action="/browse"
        method="get"
        onSubmit={onSubmit}
        className="mt-5 flex items-center gap-2 border-2 border-[var(--color-accent)] bg-[#050505] px-3.5 py-3 shadow-[3px_3px_0_rgba(217,248,67,0.14)]"
      >
        <span className="shrink-0 text-[12.5px] font-bold text-[var(--color-accent)]">mangal&gt;</span>
        <input
          type="search"
          name="q"
          placeholder="作品名・著者名で検索"
          aria-label="作品を検索"
          onFocus={warmSearch}
          className="d3-plain min-w-0 flex-1 text-[14px] font-bold text-[var(--color-ink)] outline-none"
        />
        <span aria-hidden="true" className="d3-blink h-[15px] w-2 shrink-0 bg-[var(--color-accent)]" />
      </form>
    </section>
  );
}
