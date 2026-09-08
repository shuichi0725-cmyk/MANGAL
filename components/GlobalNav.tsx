"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { seasonReached } from "@/lib/animeSeason";

/**
 * 全ページ共通のアイコンナビ(★2026-09-07 layout へ一本化)。
 *
 * ★経緯: それまで **47箇所**(app配下46頁 + HubListPage)が各自 `<DesignNav />` を呼んでいた。
 *   PC左レールをサイト全体に出すには「ナビ帯(全幅)の内側にレールと本文を並べる」必要があり、
 *   ナビが各頁の中にあるとレールを layout に置けない(ナビまでレールの右へ押し出される)。
 *   → ナビを layout に上げ、各頁からは削除した。
 *
 * ★見た目はホームだけ D3(アシッドライムの太い下線 + paper地)、他は通常(細線 + surface地)。
 *   旧 `lib/homeDesign.tsx#DesignNav`(通常)と `app/home-design-12/page.tsx#D3Nav`(ホーム)を
 *   統合したもの。アイコンの絵柄は元から同一だったので1つの表に集約した。
 *   ★lib/homeDesign.tsx は loadData(fs)を引き込むのでクライアント側から import できない
 *     = ここは自己完結にしてある(パス表をコピーしているのはそのため)。
 *
 * ★器は SiteHeader と同じ mx-auto max-w-6xl px-4(2026-09-07 ユーザ指摘「PCでアイコンが
 *   離れすぎ」= この行だけ max-width が無く1920px幅でロゴ/≡と372pxずれていた)。
 */
const NAV_SVG: Record<string, { d: string; circle?: [number, number, number] }> = {
  ホーム: { d: "M3 11L12 3l9 8M6 10v11h12V10" },
  検索: { d: "M15 15l6 6", circle: [10.5, 10.5, 6] },
  // 新作=今月の新刊一覧(/shinkan)。≡メニューの「今月の新刊一覧」タイル(box)と同じ絵柄
  新作: { d: "M21 8l-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8" },
  // ★アニメ化(2026-09-08): ホームのカテゴリタイル「アニメ化」と**同じフィルム絵柄**を使う
  //   (同じ概念に別の絵を当てると、同じ行き先だと分からなくなる)。矩形は subpath で表現。
  アニメ化: { d: "M3 5h18v14H3zM7 5v14M17 5v14M3 9h4M3 15h4M17 9h4M17 15h4" },
  使い方: { d: "M12 5c-2-1.6-5-1.6-8-.6V19c3-1 6-1 8 .6 2-1.6 5-1.6 8-.6V4.4c-3-1-6-1-8 .6zM12 5v14" },
};

function NavSvg({ label }: { label: string }) {
  const s = NAV_SVG[label];
  if (!s) return null;
  return (
    <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" style={{ stroke: "var(--color-accent)", fill: "none", strokeWidth: 1.9 }}>
      {s.circle && <circle cx={s.circle[0]} cy={s.circle[1]} r={s.circle[2]} />}
      <path d={s.d} />
    </svg>
  );
}

// ★2026-09-02 ユーザ裁定: 「一覧」を外し、検索を先頭に・その右に「新作」(=今月の新刊一覧)。
//   /list は ≡メニュー「一覧表(全作品)」とフッターから引き続き到達可。
// ★2026-09-08 ユーザ裁定: 「AI書評」→「アニメ化」に差し替え、「過去ログ」は撤去。
//   外した2つは孤立しない = AI書評家リーグ: ホーム本体 + ≡メニュー + フッター /
//   今日の一冊 過去ログ: フッター + ホームのコーナー(FeaturedDaily / SansedaiDaily)から到達可。
//   ★空いた枠には本来「サービス(サブスク)」を出したいが、導線の形を決めてから(宿題)。
const RIGHT_FIXED: Array<[string, string]> = [
  ["検索", "/browse"],
  ["新作", "/shinkan"],
];
const RIGHT_TAIL: Array<[string, string]> = [["使い方", "/about"]];

export default function GlobalNav({ animeNow, animeNext }: { animeNow: string; animeNext?: string }) {
  const pathname = usePathname();
  // ★「アニメ化」の行き先は**ホームの今季コーナーと同じ** `/anime/<季>`(2026-09-08 ユーザ指示)。
  //   サーバ側の既定 = ビルド時の季。水和後に**今日の日付**で見直し、次の季に達していれば
  //   そちらへ差し替える = 静的書き出しのまま季替わりに追随する
  //   (旧: ビルド時に焼くだけ=次のビルドまで前の季を指したまま)。
  //   ★animeNext は view に実在する季しか来ない=存在しない頁へは飛ばさない。
  const [season, setSeason] = useState(animeNow);
  useEffect(() => {
    if (animeNext && seasonReached(animeNext)) setSeason(animeNext);
  }, [animeNext]);
  const RIGHT: Array<[string, string]> = [
    ...RIGHT_FIXED,
    ["アニメ化", `/anime/${season}`],
    ...RIGHT_TAIL,
  ];
  const isHome = pathname === "/";
  const cell = "spring-press flex flex-col items-center gap-0.5 active:scale-90";
  const frame = isHome
    ? "border-b-[3px] border-[var(--color-accent)] bg-[var(--color-paper)]"
    : "border-b border-[var(--color-line)] bg-[var(--color-surface)]";
  return (
    <div className={frame}>
      <div className="mx-auto flex w-full max-w-6xl items-center px-4 py-1.5">
        {/* 左固定 = ホーム(ロゴは共通ヘッダーに一本化済み) */}
        <Link href="/" aria-label="ホーム" className={cell}>
          <NavSvg label="ホーム" />
          <span className="text-[9px] text-ink/55">ホーム</span>
        </Link>
        {/* 右寄せクラスタ(≡メニューは共通ヘッダー右端。この行は「使い方」が右端) */}
        <div className="ml-auto flex items-center gap-3.5">
          {RIGHT.map(([label, href]) => (
            <Link key={label} href={href} aria-label={label} className={cell}>
              <NavSvg label={label} />
              <span className="text-[9px] text-ink/55">{label}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
