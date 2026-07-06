import Link from "next/link";
import SiteMenu from "@/components/SiteMenu";
import CoverImage from "@/components/CoverImage";
import MarqueeTitle from "@/components/MarqueeTitle";
import { loadAllManga } from "@/lib/loadData";
import { coverUrl, type Manga } from "@/lib/schema";

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

/** ★今月の新刊(2026-07-05): ビルド時JSTの当月に発売巻を持つ作品を発売日昇順で。
 *  旧byNew(最新刊行日降順)は未来予約巻持ちの長期連載が上位を占め固定化していた。 */
/** 1巻の発売日(最小)を導出(full Manga用。索引のfirst_volume_dateと同義) */
export function firstVolumeDate(m: Manga): string | null {
  let best: string | null = null;
  for (const e of m.editions) for (const v of e.volumes) {
    if (v.number === 1 && v.release_date) {
      const d = String(v.release_date);
      if (!best || d < best) best = d;
    }
  }
  return best;
}

/** ★#1巻応援(2026-07-07 manba学び): 当月に1巻が出る新作。新刊棚と違い「はじまる作品」だけ */
export function debutThisMonth(manga: Manga[], n = 12): Manga[] {
  const now = new Date(Date.now() + 9 * 3600 * 1000);
  const ym = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}`;
  return manga
    .map((m) => [firstVolumeDate(m), m] as const)
    .filter(([d]) => d && d.startsWith(ym))
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
    .slice(0, n)
    .map(([, m]) => m);
}

export function thisMonthReleases(manga: Manga[], fallback: Manga[], n = 12): Manga[] {
  const now = new Date(Date.now() + 9 * 3600 * 1000); // JST
  const ym = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}`;
  const hits: Array<[string, Manga]> = [];
  for (const m of manga) {
    let best: string | null = null;
    for (const ed of m.editions) {
      for (const v of ed.volumes) {
        if (v.release_date && v.release_date.startsWith(ym)) {
          if (!best || v.release_date < best) best = v.release_date;
        }
      }
    }
    if (best) hits.push([best, m]);
  }
  hits.sort((a, b) => a[0].localeCompare(b[0]));
  const out = hits.map(([, m]) => m).slice(0, n);
  for (const m of fallback) {
    if (out.length >= n) break;
    if (!out.includes(m)) out.push(m);
  }
  return out;
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
  const c = coverUrl(m);
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

export function DesignNav({ current: _current }: { current?: number }) {
  // ★2026-06-14: アイコン式の単一ナビ。 🏠ホームは左固定、 残りは右寄せクラスタ(≡メニュー含む)。
  //   全ページ共通。 旧テキスト行 + 旧 ScrollShortcutsMock を統合・廃止。
  const cell =
    "spring-press flex flex-col items-center gap-0.5 active:scale-90";
  const right = [
    ["📋", "一覧", "/list"],
    ["🔍", "検索", "/browse"],
    ["📝", "AI書評", "/column-ai-league"],
    ["🕘", "過去ログ", "/sansedai-archive"],
    ["🔰", "使い方", "/about"],
  ] as const;
  return (
    <div className="flex items-center border-b border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-1.5">
      {/* 左固定 = ホーム */}
      <Link href="/" aria-label="ホーム" className={cell}>
        <span className="text-[18px] leading-none">🏠</span>
        <span className="text-[9px] text-ink/55">ホーム</span>
      </Link>
      {/* 右寄せクラスタ */}
      <div className="ml-auto flex items-center gap-3.5">
        {right.map(([icon, label, href]) => (
          <Link key={label} href={href} aria-label={label} className={cell}>
            <span className="text-[18px] leading-none">{icon}</span>
            <span className="text-[9px] text-ink/55">{label}</span>
          </Link>
        ))}
        {/* 三本線(メニュー) = 本実装(SiteMenu ドロワー 2026-07-03) */}
        <SiteMenu />
      </div>
    </div>
  );
}
