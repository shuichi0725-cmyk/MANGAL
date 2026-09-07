"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

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
  AI書評: { d: "M4 20l2-6L16 4l4 4L10 18l-6 2zM14 6l4 4" },
  過去ログ: { d: "M12 7v5l3.5 2", circle: [12, 12, 8.5] },
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
const RIGHT: Array<[string, string]> = [
  ["検索", "/browse"],
  ["新作", "/shinkan"],
  ["AI書評", "/column-ai-league"],
  ["過去ログ", "/sansedai-archive"],
  ["使い方", "/about"],
];

export default function GlobalNav() {
  const pathname = usePathname();
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
