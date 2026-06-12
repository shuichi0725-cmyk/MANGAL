import Link from "next/link";
import CoverImage from "@/components/CoverImage";
import MarqueeTitle from "@/components/MarqueeTitle";
import { loadAllManga } from "@/lib/loadData";
import { primaryVolume, type Manga } from "@/lib/schema";

/** 見本市(/home-design-0X)用の共有部品。 本番には使わない試作層。 */

export function bundle() {
  const data = loadAllManga();
  const manga = data.manga;
  const byNew = [...manga].sort((a, b) =>
    (latestDate(b) ?? "").localeCompare(latestDate(a) ?? ""),
  );
  const completedClassics = manga
    .filter((m) => m.status === "completed" && volCount(m) >= 5)
    .sort((a, b) => volCount(b) - volCount(a));
  return { data, manga, byNew, completedClassics };
}

export function latestDate(m: Manga): string | null {
  let d: string | null = null;
  for (const ed of m.editions) {
    for (const v of ed.volumes) {
      if (v.release_date && (!d || v.release_date > d)) d = v.release_date;
    }
  }
  return d;
}

export function volCount(m: Manga): number {
  return Math.max(0, ...m.editions.map((e) => e.volumes.length));
}

/** slug ハッシュの擬似乱数(= リロードで安定) */
export function seeded<T>(arr: T[], key: (t: T) => string, n: number, salt = 7): T[] {
  const h = (s: string) => {
    let x = salt;
    for (const c of s) x = (x * 31 + c.charCodeAt(0)) % 100003;
    return x;
  };
  return [...arr].sort((a, b) => h(key(a)) - h(key(b))).slice(0, n);
}

export function Cover({ m, sizes = "120px" }: { m: Manga; sizes?: string }) {
  const c = primaryVolume(m)?.cover_url ?? null;
  return (
    <div className="relative aspect-[2/3] w-full overflow-hidden rounded bg-[var(--color-surface-2)] border border-[var(--color-line)]">
      {c ? (
        <CoverImage src={c} alt={m.title} sizes={sizes} size="card" />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center p-2 text-center text-[11px] leading-tight text-ink/45">
          {m.title.slice(0, 28)}
        </div>
      )}
    </div>
  );
}

export function CoverTile({ m, sizes }: { m: Manga; sizes?: string }) {
  // ★題=1行オートスクロール(はみ出し時のみ)+作者行 で全コーナー統一(2026-06-12 ユーザ裁定)
  return (
    <Link href={`/manga/${m.slug}`} className="block group spring-press">
      <Cover m={m} sizes={sizes} />
      <MarqueeTitle
        text={m.title}
        className="mt-1 text-[12px] leading-snug text-ink/85 group-hover:text-[var(--color-accent)]"
      />
      <p className="truncate text-[10px] text-ink/50">
        {m.authors.map((a) => a.name).join("・")}
      </p>
    </Link>
  );
}

export function DesignNav({ current }: { current: number }) {
  return (
    <div className="sticky top-0 z-50 flex items-center gap-1.5 border-b border-[var(--color-line)] bg-[var(--color-surface)]/95 px-3 py-2 text-xs backdrop-blur">
      <span className="font-bold text-ink/60 mr-1">見本市</span>
      {[7, 8, 9, 10, 11].map((n) => (
        <Link
          key={n}
          href={`/home-design-${String(n).padStart(2, "0")}`}
          className={`spring-press rounded px-2 py-1 font-semibold ${
            n === current
              ? "bg-[var(--color-accent)] text-white"
              : "border border-[var(--color-line)] text-ink/70"
          }`}
        >
          {n}
        </Link>
      ))}
      <Link href="/" className="ml-auto text-ink/50 underline decoration-dotted">
        現行
      </Link>
    </div>
  );
}
