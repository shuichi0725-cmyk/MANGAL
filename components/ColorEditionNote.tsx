"use client";

import { useEffect, useState } from "react";

/** 電子カラー版ストリップ(2026-07-30 柱化)。
 *  public/data/color-editions.json(_color-editions-build.py 生成・slugキー)を
 *  クライアントfetchし、該当作品の頁にだけ「電子カラー版 全N巻」を表示する。
 *  データ更新=JSON差し替えのみ(66k頁の再生成不要。sansedai-stock と同じ方式)。
 *  b(BookLive title_id)があれば試し読みリンクも出す。 */

type ColorEntry = { v: number; u: string; c?: string | null; b?: string };
let _ce: Record<string, ColorEntry> | null = null;

export default function ColorEditionNote({ slug }: { slug: string }) {
  const [data, setData] = useState<Record<string, ColorEntry> | null>(_ce);
  useEffect(() => {
    if (_ce) return;
    fetch("/data/color-editions.json")
      .then((r) => (r.ok ? r.json() : {}))
      .then((d) => {
        _ce = d;
        setData(d);
      })
      .catch(() => setData({}));
  }, []);
  const e = data?.[slug];
  if (!e) return null;
  return (
    <section className="mt-4">
      <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3 shadow-sm">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <p className="text-[13px] font-extrabold">
            🎨 電子カラー版<span className="ml-1.5 text-[12px] font-bold text-[var(--color-accent)]">全{e.v}巻 配信中</span>
          </p>
          <div className="flex items-center gap-2">
            {e.u && (
              <a
                href={e.u}
                target="_blank"
                rel="nofollow sponsored noopener"
                className="rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)] px-2.5 py-1 text-[11.5px] font-bold text-ink/80 spring-press"
              >
                楽天Koboで読む
              </a>
            )}
            {e.b && (
              <a
                href={`https://booklive.jp/product/index/title_id/${e.b}/vol_no/001`}
                target="_blank"
                rel="nofollow sponsored noopener"
                className="rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)] px-2.5 py-1 text-[11.5px] font-bold text-ink/80 spring-press"
              >
                試し読み
              </a>
            )}
          </div>
        </div>
        <p className="mt-1 text-[10px] text-ink/40">[PR] 店舗リンクにはアフィリエイト広告を含みます</p>
      </div>
    </section>
  );
}
