"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CoverImage from "@/components/CoverImage";

/** 🌈カラー版コーナー(2026-08-12 ユーザ採用: ボタン=案3「COLOR透かし」+中身=案B「書影だけの密な帯」)。
 *  設置=ホームの全集コーナー直上。ヘッダー=/color-manga(一覧)へ。
 *  ★書影タップ=Kindleストアの購入リンクへ直行(2026-08-12 ユーザ裁定。作品頁には飛ばさない=
 *    作品頁は紙の書誌でカラー版を出していないため)。ASIN無し=題名でKindle検索(i=digital-text)、
 *    アプリ起動回避の/go中継+[PR]表記は AffiliateLink と同じ流儀。
 *  データ=public/data/color-editions.json(_color-editions-build.py。8/2に{}で表示停止していたのを
 *  本コーナー新設に伴い再生成)。帯の並び=巻数の多い順=長期看板作の色表紙が先頭に来る。
 *  色トークンは全部テーマ変数=ライト/D3両対応(COLOR透かしの4色グラデのみ固定色)。 */

type Entry = { v: number; u: string; c?: string | null; b?: string; t?: string };

function kindleSearchUrl(title: string): string {
  const tag = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";
  const url = new URL("https://www.amazon.co.jp/s");
  url.searchParams.set("k", title);
  url.searchParams.set("i", "digital-text");
  if (tag) url.searchParams.set("tag", tag);
  return url.toString();
}

/** Kindleはブラウザで開く(AffiliateLinkと同じ: Amazonアプリ内ではKindle本が買えないIAP規約対策)。
 *  本番(Worker配下)は /go 中継、preview/開発は window.open 簡易版。 */
function openKindle(e: React.MouseEvent, href: string) {
  e.preventDefault();
  const viaWorker =
    window.location.hostname === "mangal-db.com" || window.location.hostname.endsWith("workers.dev");
  window.open(viaWorker ? `/go?u=${encodeURIComponent(href)}` : href, "_blank", "noopener");
}

export default function ColorCorner() {
  const [data, setData] = useState<Record<string, Entry> | null>(null);
  useEffect(() => {
    fetch("/data/color-editions.json")
      .then((r) => (r.ok ? r.json() : {}))
      .then(setData)
      .catch(() => setData({}));
  }, []);
  if (data === null) return null;
  const rows = Object.entries(data)
    .filter(([, e]) => e.c)
    .sort((a, b) => b[1].v - a[1].v)
    .slice(0, 14);
  if (rows.length === 0) return null;
  const total = Object.keys(data).length;
  return (
    <section className="mt-4 px-4">
      <div className="overflow-hidden rounded-xl border border-[var(--color-line)] border-b-4 border-b-[var(--color-accent)] bg-[var(--color-surface)] shadow-sm">
        <Link href="/color-manga" className="spring-press relative block overflow-hidden px-3.5 pb-2.5 pt-3.5">
          <span
            aria-hidden="true"
            className="pointer-events-none absolute -right-1 -top-3 bg-clip-text text-[52px] font-black leading-none tracking-[-0.04em] text-transparent opacity-50"
            style={{ backgroundImage: "linear-gradient(90deg,#29b7e5,#e254a4,#f2d23c,#57c465)" }}
          >
            COLOR
          </span>
          <span className="relative inline-block border border-[var(--color-accent)] px-1.5 py-0.5 text-[9px] font-extrabold tracking-[0.22em] text-[var(--color-accent)]">
            FULL COLOR EDITION
          </span>
          <span className="relative ml-1.5 text-[8.5px] text-ink/45">[PR]</span>
          <p className="relative mt-1.5 text-[17px] font-black leading-tight">
            カラー版で読める漫画 <span className="text-[var(--color-accent)]">→</span>
          </p>
          <p className="relative mt-0.5 text-[10.5px] text-ink/55">紙は白黒でも、電子はフルカラー。</p>
        </Link>
        <ul className="no-scrollbar flex snap-x gap-1 overflow-x-auto px-3 pb-3 scroll-pl-3">
          {rows.map(([slug, e]) => {
            const href = kindleSearchUrl(e.t ?? slug);
            return (
              <li key={slug} className="shrink-0 snap-start">
                <a
                  href={href}
                  target="_blank"
                  rel="nofollow sponsored noopener"
                  onClick={(ev) => openKindle(ev, href)}
                  aria-label={`${e.t ?? slug} をKindleで見る`}
                  className="spring-press block h-[92px] w-[62px] overflow-hidden border border-[var(--color-line)] bg-[var(--color-surface-2)]"
                >
                  <CoverImage src={e.c!} alt={e.t ?? slug} sizes="62px" size="card" />
                </a>
              </li>
            );
          })}
          <li className="shrink-0 snap-start">
            <Link
              href="/color-manga"
              className="spring-press flex h-[92px] w-[62px] flex-col items-center justify-center gap-0.5 border border-[var(--color-accent)]"
            >
              <span className="text-[15px] font-black tabular-nums text-[var(--color-accent)]">{total}</span>
              <span className="text-[8.5px] text-ink/60">作品</span>
              <span className="text-[8.5px] font-black text-[var(--color-accent)]">→ 全部</span>
            </Link>
          </li>
        </ul>
      </div>
    </section>
  );
}
