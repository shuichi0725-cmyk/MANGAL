"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import FilterPanel from "@/components/FilterPanel";
import { useFilterPanelData } from "@/lib/useFilterPanelData";
import {
  emptyFilterState,
  filtersFromSearchParams,
  filtersToSearchParams,
  type FilterState,
} from "@/lib/filters";
import type { ListBundle } from "@/lib/schema";

/**
 * PC左レール = **検索窓 + 絞り込みパネル**(★2026-09-07 ユーザ指示)。
 *
 * ★経緯: 最初「一覧へ飛ぶリンク集(HomeSidebar)」を左に出したが、ユーザの求めていたものは
 *   **その右にあった絞り込みパネルそのもの**だった(「左が一覧検索になってる。これは一切いらない。
 *   写真の一覧検索の右の検索を全ページに出して」)。リンク集は撤去し、これに置き換える。
 *
 * ★状態は URL(?q= &genre= …)が source of truth。`filtersToSearchParams` /
 *   `filtersFromSearchParams` は既存の対称エンコーダをそのまま使う。
 *   - /browse・/list に居る時 = 同じパスへ replace(その場で絞り込みが効く。両画面とも
 *     URL 変化で state を組み直す配線が既にある)
 *   - それ以外の頁(漫画詳細・ジャンル面・過去ログ…)= /browse へ push(絞り込み結果へ移動)
 *
 * ★lg(1024px)未満では出さない = モバイルは従来の抽斗UIのまま(見た目完全不変)。
 * ★`useSearchParams()` を使うので **Suspense 必須**(静的書き出しではフォールバックがHTMLに焼かれる)。
 *   フォールバックは素のGETフォーム = JS前でも検索に飛べる([[browse_ssr_shell_and_seo]] の教訓)。
 */
export type RailMasters = Pick<ListBundle, "publishers" | "magazines" | "genres" | "demographics">;

const CARD = "border-2 border-[var(--color-accent)] bg-[#050505] px-2.5 py-2 shadow-[3px_3px_0_rgba(217,248,67,0.14)]";
const BTN = "mt-2 w-full border-2 border-[var(--color-accent)] bg-[#050505] py-1.5 text-[12px] font-black text-[var(--color-accent)] transition active:scale-[0.97]";

/** 検索窓(ターミナル調)。action があるので JS 前/非JS でも飛べる。 */
function SearchCard({
  action,
  value,
  onChange,
  onSubmit,
}: {
  action: string;
  value: string;
  onChange?: (v: string) => void;
  onSubmit?: (e: React.FormEvent) => void;
}) {
  return (
    <form action={action} method="get" onSubmit={onSubmit}>
      <div className={`flex items-center gap-1.5 ${CARD}`}>
        <span className="shrink-0 text-[11px] font-bold text-[var(--color-accent)]" aria-hidden="true">
          mangal&gt;
        </span>
        <input
          type="search"
          name="q"
          defaultValue={onChange ? undefined : value}
          value={onChange ? value : undefined}
          onChange={onChange ? (e) => onChange(e.target.value) : undefined}
          placeholder="題名・よみ・著者…"
          aria-label="作品を検索"
          className="d3-plain min-w-0 flex-1 text-[13px] font-bold text-[var(--color-ink)] outline-none"
        />
        <span aria-hidden="true" className="d3-blink h-[13px] w-1.5 shrink-0 bg-[var(--color-accent)]" />
      </div>
      <button type="submit" className={BTN}>
        検索
      </button>
    </form>
  );
}

/** lg(1024px)以上か。★`hidden lg:block` は CSS で隠すだけでマウントは走るので、
 *  「見えないのに索引6.06MBを落として haystack を3.7秒前計算する」を止めるにはこれが要る。
 *  2026-08-01 に同型を一度潰している(HomeClient が FilterPanel を2つ常時マウントし、
 *  CSSで隠れている側の568msを毎回捨てていた)。同じ型なので同じ道具(matchMedia)で塞ぐ。 */
function useIsLg(): boolean {
  const [isLg, setIsLg] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const on = () => setIsLg(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return isLg;
}

/** 到着ウォームを許してよい回線か。★ホームの `warmSearchIdle`(HeroD3)と同じ節度:
 *  データセーバー / 2G では先読みしない(触れた時だけ読む)。 */
function useArrivalWarmAllowed(): boolean {
  const [ok, setOk] = useState(false);
  useEffect(() => {
    type NetInfo = { saveData?: boolean; effectiveType?: string };
    const conn = (navigator as { connection?: NetInfo }).connection;
    if (conn?.saveData || /2g/.test(conn?.effectiveType ?? "")) return;
    setOk(true);
  }, []);
  return ok;
}

function RailInner({ masters }: { masters: RailMasters }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();

  const key = searchParams.toString();
  const state = useMemo<FilterState>(
    () => ({ ...emptyFilterState(), ...filtersFromSearchParams(searchParams) }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [key],
  );
  const [q, setQ] = useState(state.query);

  // ★行き先: 一覧表に居るならそのまま /list、それ以外は /browse(絞り込み結果の本拠地)
  const dest = pathname === "/list" ? "/list" : "/browse";
  const inPlace = pathname === "/browse" || pathname === "/list";

  // ★索引を要求してよい条件(2026-09-08 ユーザ指摘「全ページ検索になってキャッシュを何度も
  //   解凍していないか」→ 裁定「ホームと同じく到着で先読み」):
  //   ①lg未満 = レールは display:none。**何もしない**(見えないUIに費用を払わせない)。
  //      `hidden lg:block` はCSSだけなので、この matchMedia が無いとモバイルも
  //      6.06MB + haystack前計算(実機3,773ms)を払う。2026-08-01に潰した同型の再発。
  //   ②lg以上 = **到着で先読み**(ホーム HeroD3 の warmSearchIdle と同じ思想)。
  //      取得自体は fetchIndex が head→idleでfull、デコード8,000行刻み、
  //      haystack 500行刻み(clientSearch の FILL_CHUNK)なので初描画は汚さない。
  //   ③saveData / 2G だけは先読みを見送り、レールに触れた時に読む。
  //   ④/browse・/list・検索語ありは無条件(画面本体が索引を読む/利用者が検索している)。
  //   ※未取得の間もパネルは使える = チップは全部出て件数だけ伏せる(押せば /browse へ飛ぶ)。
  const isLg = useIsLg();
  const [touched, setTouched] = useState(false);
  const arrivalWarm = useArrivalWarmAllowed();
  const wantIndex = isLg && (inPlace || !!state.query || touched || arrivalWarm);
  const fp = useFilterPanelData({ query: state.query, enabled: wantIndex });

  const go = (next: FilterState) => {
    const qs = filtersToSearchParams(next).toString();
    const url = qs ? `${dest}?${qs}` : dest;
    if (inPlace) router.replace(url, { scroll: false });
    else router.push(url);
  };

  return (
    <div
      className="sticky top-4 space-y-3"
      onFocusCapture={() => setTouched(true)}
      onPointerDownCapture={() => setTouched(true)}
    >
      <SearchCard
        action={dest}
        value={q}
        onChange={setQ}
        onSubmit={(e) => {
          e.preventDefault();
          go({ ...state, query: q.trim() });
        }}
      />
      <FilterPanel
        data={{ manga: fp.manga, artBooks: [], ...masters }}
        state={state}
        setState={go}
        authorEntries={fp.authorEntries}
        matchedSlugs={fp.matchedSlugs}
        loading={fp.panelLoading}
        showArtBooks={false}
        stickyTop="top-0"
      />
    </div>
  );
}

export default function FilterRail({ masters }: { masters: RailMasters }) {
  return (
    <aside className="hidden lg:block w-[260px] shrink-0">
      <Suspense
        fallback={
          <div className="sticky top-4 space-y-3">
            <SearchCard action="/browse" value="" />
            <p className="text-[11px] text-ink/40">絞り込みを読み込み中…</p>
          </div>
        }
      >
        <RailInner masters={masters} />
      </Suspense>
    </aside>
  );
}
