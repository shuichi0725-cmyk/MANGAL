"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";

/** ≡メニュー(2026-08-12 案B採用=タイル型に全面刷新):
 *  - 全リンク先を収録(さがす4 / コーナー8 / 全集10 / サイト情報4)= フッターや
 *    メニューに無かったコーナー(著者一覧/アニメ化/カラー版/ランキング/全集)を追加。
 *  - アイコンは絵文字を廃止しナビ・カテゴリと同じモノクロSVG線画(accent色)に統一。
 *  - 役割ごとにグループ見出し。ドロワーは右からフルハイト・2列タイル。
 *  角丸はテーマ側で制御(.theme-d3 が rounded-* を0化)=ライト/ダーク両対応。 */

type Ic = { d: string; c?: [number, number, number] };
const IC: Record<string, Ic> = {
  home: { d: "M3 11L12 3l9 8M6 10v11h12V10" },
  search: { d: "M15 15l6 6", c: [10.5, 10.5, 6] },
  list: { d: "M4 6h16M4 12h16M4 18h10" },
  author: { d: "M5.5 20c.8-4.5 3.4-7 6.5-7s5.7 2.5 6.5 7", c: [12, 8, 3.6] },
  book: { d: "M12 6c-2-1.6-5-1.6-8-.6V19c3-1 6-1 8 .6 2-1.6 5-1.6 8-.6V5.4c-3-1-6-1-8 .6zM12 6v14" },
  calendar: { d: "M4 6h16v15H4zM4 10h16M8 3v4M16 3v4" },
  clock: { d: "M12 7v5l3.5 2", c: [12, 12, 8.5] },
  pen: { d: "M4 20l2-6L16 4l4 4L10 18l-6 2zM14 6l4 4" },
  film: { d: "M3 5h18v14H3zM7 5v14M17 5v14M3 9h4M3 15h4M17 9h4M17 15h4" },
  chart: { d: "M5 20v-6h4v6M10 20V6h4v14M15 20v-9h4v9M3 20h18" },
  drop: { d: "M12 3s6 7.5 6 11.5a6 6 0 0 1-12 0C6 10.5 12 3 12 3z" },
  picture: { d: "M3 5h18v14H3zM3 15l5-5 4 4 3-3 6 6" },
  mail: { d: "M3 6h18v12H3zM3 7l9 6 9-6" },
  doc: { d: "M6 3h9l4 4v14H6zM15 3v4h4M9 12h6M9 16h6" },
  lock: { d: "M6 11h12v9H6zM9 11V8a3 3 0 0 1 6 0v3" },
};

function Svg({ k, className = "h-5 w-5" }: { k: string; className?: string }) {
  const p = IC[k];
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={className}
      style={{ stroke: "var(--color-accent)", fill: "none", strokeWidth: 1.9 }}
    >
      {p.c && <circle cx={p.c[0]} cy={p.c[1]} r={p.c[2]} />}
      <path d={p.d} />
    </svg>
  );
}

type Tile = { icon: string; label: string; href: string; sub?: string };

const FIND: Tile[] = [
  { icon: "home", label: "ホーム", href: "/" },
  { icon: "search", label: "検索・絞り込み", href: "/browse" },
  { icon: "list", label: "一覧表(全作品)", href: "/list" },
  { icon: "author", label: "著者一覧(50音)", href: "/authors" },
];

const CORNERS: Tile[] = [
  // ★今日の一冊のリンク先="/"は誤り(2026-08-12 ユーザ指摘)。過去ログ頁へ=旧・過去ログタイルと統合
  { icon: "book", label: "今日の一冊 過去ログ", href: "/sansedai-archive", sub: "毎日更新" },
  { icon: "calendar", label: "日替わり特集", href: "/tokushu", sub: "毎日更新" },
  { icon: "pen", label: "AI書評家リーグ", href: "/column-ai-league", sub: "週刊" },
  { icon: "film", label: "アニメの原作漫画", href: "/anime" },
  { icon: "chart", label: "なんでもランキング", href: "/rankings" },
  { icon: "drop", label: "カラー版で読める漫画", href: "/color-manga" },
  { icon: "picture", label: "画集", href: "/art-books" },
];

const ZENSHUU: Array<[string, string]> = [
  ["水木しげる", "mizuki"],
  ["手塚治虫", "tezuka"],
  ["手塚治虫文庫", "tezuka-bunko"],
  ["藤子・F・不二雄", "fujiko-f"],
  ["藤子不二雄ランド", "fujiko-land"],
  ["石ノ森章太郎", "ishinomori"],
  ["長谷川町子", "hasegawa"],
  ["カムイ伝", "kamuiden"],
  ["つげ義春大全", "tsuge-taizen"],
  ["つげ義春", "tsuge"],
];

const INFO: Array<[string, string, string]> = [
  ["book", "使い方", "/about"],
  ["mail", "お問い合わせ", "/contact"],
  ["doc", "利用規約", "/terms"],
  ["lock", "プライバシー", "/privacy"],
];

export default function SiteMenu() {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  const Gh = ({ children }: { children: React.ReactNode }) => (
    <h3 className="mt-4 mb-1.5 text-[10px] font-extrabold tracking-[0.22em] text-[var(--color-accent)]">
      {children}
    </h3>
  );
  return (
    <>
      <button
        type="button"
        aria-label="メニュー"
        onClick={() => setOpen(true)}
        className="spring-press flex flex-col items-center gap-0.5 active:scale-90"
      >
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          className="h-[18px] w-[18px]"
          style={{ stroke: "currentColor", fill: "none", strokeWidth: 2 }}
        >
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
        <span className="text-[9px] text-ink/55">メニュー</span>
      </button>
      {/* ★portal必須(2026-08-12実踏): 設置先の共通ヘッダーが backdrop-blur 持ち。
          backdrop-filterを持つ祖先は fixed の containing block になるため、直下に描くと
          「全画面ドロワーがヘッダーの箱に閉じ込められ、ヘッダーより下が出ない」。body直下へ逃がす。 */}
      {open && createPortal(
        <div className="fixed inset-0 z-50" role="dialog" aria-label="サイトメニュー">
          <button aria-label="閉じる" className="absolute inset-0 bg-black/45" onClick={close} />
          {/* 右からフルハイトのドロワー。左辺=accentの太線(案B) */}
          <div className="absolute inset-y-0 right-0 w-[86%] max-w-[336px] overflow-y-auto border-l-[3px] border-[var(--color-accent)] bg-[var(--color-surface)] p-3.5">
            <div className="flex items-center justify-between">
              <p className="text-[15px] font-extrabold">
                MANGAL<span className="text-[var(--color-accent)]">.</span> メニュー
              </p>
              <button
                onClick={close}
                aria-label="閉じる"
                className="flex h-8 w-8 items-center justify-center rounded-full text-ink/50 hover:bg-[var(--color-surface-2)]"
              >
                ×
              </button>
            </div>

            <Gh>さがす</Gh>
            <div className="grid grid-cols-2 gap-1.5">
              {FIND.map((t) => (
                <Link
                  key={t.href + t.label}
                  href={t.href}
                  onClick={close}
                  className="spring-press flex flex-col items-center gap-1 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-2)]/60 px-2 py-2.5 text-center hover:bg-[var(--color-surface-2)]"
                >
                  <Svg k={t.icon} />
                  <span className="text-[11.5px] font-extrabold leading-tight">{t.label}</span>
                </Link>
              ))}
            </div>

            <Gh>コーナー</Gh>
            <div className="grid grid-cols-2 gap-1.5">
              {CORNERS.map((t) => (
                <Link
                  key={t.href + t.label}
                  href={t.href}
                  onClick={close}
                  className="spring-press flex flex-col items-center gap-1 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-2)]/60 px-2 py-2.5 text-center hover:bg-[var(--color-surface-2)]"
                >
                  <Svg k={t.icon} />
                  <span className="text-[11.5px] font-extrabold leading-tight">{t.label}</span>
                  {t.sub && <span className="text-[8.5px] text-ink/45">{t.sub}</span>}
                </Link>
              ))}
            </div>

            <Gh>全集(作家の全仕事)</Gh>
            <div className="flex flex-wrap gap-1.5">
              {ZENSHUU.map(([name, key]) => (
                <Link
                  key={key}
                  href={`/zenshuu/${key}`}
                  onClick={close}
                  className="spring-press rounded-md border border-[var(--color-line)] px-2 py-1 text-[10.5px] font-bold text-ink/85 hover:bg-[var(--color-surface-2)]"
                >
                  {name}
                </Link>
              ))}
            </div>

            <Gh>サイト情報</Gh>
            <div className="flex flex-wrap gap-x-4 gap-y-1.5">
              {INFO.map(([, label, href]) => (
                <Link
                  key={href}
                  href={href}
                  onClick={close}
                  className="spring-press text-[11.5px] font-bold text-ink/80 hover:text-ink"
                >
                  {label}
                </Link>
              ))}
            </div>

            <p className="mt-4 border-t border-[var(--color-line)] pt-2.5 text-[9.5px] leading-relaxed text-ink/45">
              [PR] 本サイトの店舗リンクにはアフィリエイト広告を含みます。
            </p>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
