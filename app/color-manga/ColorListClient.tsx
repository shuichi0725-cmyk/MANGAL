"use client";

import { useEffect, useState } from "react";
import CoverImage from "@/components/CoverImage";
import { kindleSearchUrl } from "@/lib/kindleLink";

type ColorEntry = { v: number; u: string; c?: string | null; b?: string; t?: string };

export default function ColorListClient() {
  const [data, setData] = useState<Record<string, ColorEntry> | null>(null);
  useEffect(() => {
    fetch("/data/color-editions.json")
      .then((r) => (r.ok ? r.json() : {}))
      .then(setData)
      .catch(() => setData({}));
  }, []);
  if (data === null) return <p className="px-4 text-[13px] text-ink/60">読み込み中…</p>;
  const rows = Object.entries(data).sort((a, b) => b[1].v - a[1].v || (a[1].t ?? "").localeCompare(b[1].t ?? "", "ja"));
  return (
    <div className="px-4 pb-8">
      <p className="mb-2 text-[11px] text-ink/50">{rows.length}作品</p>
      <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
        {rows.map(([slug, e]) => {
          // ★書影タップ=Kindle購入リンクへ直行(2026-08-12 ユーザ裁定。ホームのカラー版コーナーと同じ)。
          //   作品頁には飛ばさない=作品頁は紙の書誌でカラー版を出していないため。ブラウザ起動はopenKindleInBrowser。
          const href = kindleSearchUrl(e.t ?? slug);
          return (
          <li key={slug}>
            <a
              href={href}
              target="_blank"
              rel="nofollow sponsored noopener"
              aria-label={`${e.t ?? slug} をKindleで見る`}
              className="spring-press block"
            >
              <div
                className="relative overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
                style={{ aspectRatio: "2 / 3" }}
              >
                {e.c ? (
                  <CoverImage src={e.c} alt={e.t ?? slug} sizes="(max-width: 640px) 33vw, 16vw" />
                ) : (
                  <span className="flex h-full w-full items-center justify-center text-[9px] text-ink/40">no image</span>
                )}
              </div>
              <p className="mt-1 line-clamp-2 text-[11px] font-bold leading-snug">{e.t ?? slug}</p>
              <p className="text-[10px] text-ink/55">全{e.v}巻</p>
            </a>
          </li>
          );
        })}
      </ul>
      <p className="mt-4 text-[10px] text-ink/40">[PR] 各作品のリンクにはアフィリエイト広告を含みます(Kindleストアへ移動します)</p>
    </div>
  );
}
