import Link from "next/link";
import type { ReactNode } from "react";
import HubRow from "@/components/HubRow";
import { DesignNav } from "@/lib/homeDesign";
import { HUB_LABEL, hubHeading, hubHref, hubRows, type HubDef } from "@/lib/hubs";

const SITE = "https://mangal-db.com";

/** ハブ面(雑誌別/出版社別/年別)の共通本体(2026-09-04 SEO)。 パンくず+JSON-LD、見出し、頁送り、文字行一覧。
 *  種別ごとの付随情報(出版社・同社の雑誌・前後年など)は extra で差し込む。 */
export default function HubListPage({
  def,
  page,
  lead,
  extra,
}: {
  def: HubDef;
  page: number;
  lead: string;
  extra?: ReactNode;
}) {
  const rows = hubRows(def.kind, def.key, page);
  const prev = page > 1 ? hubHref(def.kind, def.key, page - 1) : null;
  const next = page < def.pages ? hubHref(def.kind, def.key, page + 1) : null;
  const heading = hubHeading(def);
  const breadcrumbLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "ホーム", item: `${SITE}/` },
      { "@type": "ListItem", position: 2, name: HUB_LABEL[def.kind], item: `${SITE}/${def.kind}` },
      { "@type": "ListItem", position: 3, name: def.name, item: `${SITE}${hubHref(def.kind, def.key)}` },
    ],
  };
  // 頁送り = 前後リンク + 全頁番号(深い頁へ1クリックで届く=クロール深度を浅く保つ)
  const pager =
    def.pages > 1 ? (
      <nav className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] font-bold">
        {prev ? (
          <Link href={prev} className="hover:text-[var(--color-accent)]">← 前の頁</Link>
        ) : (
          <span className="text-ink/30">← 前の頁</span>
        )}
        <span className="flex flex-wrap gap-1 text-[11.5px] font-semibold text-ink/50">
          {Array.from({ length: def.pages }, (_, i) => i + 1).map((p) =>
            p === page ? (
              <span key={p} className="rounded bg-[var(--color-surface-2)] px-1.5 text-ink">{p}</span>
            ) : (
              <Link key={p} href={hubHref(def.kind, def.key, p)} className="px-1.5 hover:text-ink">
                {p}
              </Link>
            ),
          )}
        </span>
        {next ? (
          <Link href={next} className="hover:text-[var(--color-accent)]">次の頁 →</Link>
        ) : (
          <span className="text-ink/30">次の頁 →</span>
        )}
      </nav>
    ) : null;
  return (
    <div>
      <DesignNav />
      <div className="mx-auto max-w-4xl px-4 py-8">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }} />
        <nav className="text-[12px] text-ink/55">
          <Link href="/" className="hover:text-ink">ホーム</Link> ›{" "}
          <Link href={`/${def.kind}`} className="hover:text-ink">{HUB_LABEL[def.kind]}</Link> › {def.name}
        </nav>
        <h1 className="mt-2 text-2xl font-extrabold">
          {heading}
          {page > 1 && (
            <span className="ml-2 text-[12px] font-semibold text-ink/45">
              {page}/{def.pages}ページ
            </span>
          )}
        </h1>
        <p className="mt-1 text-[13px] text-ink/70">{lead}</p>
        {extra && <div className="mt-3 space-y-1 text-[12px] text-ink/60">{extra}</div>}
        {pager && <div className="mt-3">{pager}</div>}
        <ol className="mt-4">
          {rows.map((m) => (
            <HubRow key={m.slug} m={m} omit={def.kind} />
          ))}
        </ol>
        {pager && <div className="mt-5">{pager}</div>}
      </div>
    </div>
  );
}
