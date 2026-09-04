import Link from "next/link";
import { notFound } from "next/navigation";
import HubListPage from "@/components/HubListPage";
import { decadeOf, hubDefs, hubHref, hubMeta, hubStaticParams, resolveHubParts } from "@/lib/hubs";

/** 連載開始年別 漫画一覧(2026-09-04 SEO ハブ面)。 /year/<yyyy>(1頁目) と /year/<yyyy>/<n>(続き)。
 *  ★年を持つ全作品を必ず載せる = 作品頁66k枚への静的な内部リンク(孤児頁の発見経路)。 */

const KIND = "year" as const;
const SITE = "https://mangal-db.com";

export const dynamicParams = false;

export function generateStaticParams() {
  return hubStaticParams(KIND);
}

type P = { params: Promise<{ parts: string[] }> };

export async function generateMetadata({ params }: P) {
  const { parts } = await params;
  const r = resolveHubParts(KIND, parts);
  if (!r) return {};
  const { title, description } = hubMeta(r.def, r.page);
  const url = `${SITE}${hubHref(KIND, r.def.key, r.page)}`;
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, url, type: "website", siteName: "MANGAL" },
  };
}

export default async function YearHubPage({ params }: P) {
  const { parts } = await params;
  const r = resolveHubParts(KIND, parts);
  if (!r) notFound();
  const { def, page } = r!;
  const all = hubDefs(KIND);
  const i = all.findIndex((d) => d.key === def.key);
  const prev = i > 0 ? all[i - 1] : null;
  const next = i >= 0 && i < all.length - 1 ? all[i + 1] : null;
  const dec = decadeOf(Number(def.key));
  const decade = all.filter((d) => decadeOf(Number(d.key)) === dec);
  const lead = `全${def.count.toLocaleString()}作品（完結${def.completed.toLocaleString()}）・人気順`;
  const extra = (
    <>
      <p>
        {prev && (
          <Link href={hubHref(KIND, prev.key)} className="text-[var(--color-accent)] hover:underline">← {prev.name}</Link>
        )}
        {prev && next && " ・ "}
        {next && (
          <Link href={hubHref(KIND, next.key)} className="text-[var(--color-accent)] hover:underline">{next.name} →</Link>
        )}
      </p>
      <p>
        {dec}年代:{" "}
        {decade.map((d, j) => (
          <span key={d.key}>
            {j > 0 && " / "}
            {d.key === def.key ? (
              <b>{d.key}</b>
            ) : (
              <Link href={hubHref(KIND, d.key)} className="text-[var(--color-accent)] hover:underline">{d.key}</Link>
            )}
          </span>
        ))}
      </p>
    </>
  );
  return <HubListPage def={def} page={page} lead={lead} extra={extra} />;
}
