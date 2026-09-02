import Link from "next/link";
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

/** 今月発売の1エントリ: m=作品 / date・number・cover=当月に出る巻そのもの
 *  (★2026-07-13: 旧実装は作品の1巻書影を出し「一年前の本?」と誤読された。新刊巻を明示する) */
export type MonthRelease = { m: Manga; date: string; number: number | null; cover: string | null };

/** 実書影判定: 楽天の仮書影(文字だけ画像)はURL末尾が.gif=偽装影([[placeholder-cover-refresh]])。
 *  ★今月の新刊はgifを「書影なし」として扱う(2026-08-06 ユーザ指定「gifは出したくない」)。 */
function realCover(u?: string | null): boolean {
  return !!u && !u.split("?")[0].toLowerCase().endsWith(".gif");
}

export function thisMonthReleases(manga: Manga[], fallback: Manga[], n = 12): MonthRelease[] {
  const now = new Date(Date.now() + 9 * 3600 * 1000); // JST
  const ym = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}`;
  const hits: MonthRelease[] = [];
  for (const m of manga) {
    let best: { date: string; number: number | null; cover: string | null } | null = null;
    for (const ed of m.editions) {
      for (const v of ed.volumes) {
        if (v.release_date && v.release_date.startsWith(ym)) {
          if (!best || v.release_date < best.date)
            best = { date: v.release_date, number: v.number ?? null, cover: v.cover_url ?? null };
        }
      }
    }
    if (best) {
      // ★gif仮書影は書影なし扱い: 当月巻の実書影→作品代表の実書影→どちらも無ければ落とす
      const c = realCover(best.cover) ? best.cover : realCover(coverUrl(m)) ? coverUrl(m)! : null;
      if (c) hits.push({ m, ...best, cover: c });
    }
  }
  hits.sort((a, b) => a.date.localeCompare(b.date));
  const out = hits.slice(0, n);
  for (const m of fallback) {
    if (out.length >= n) break;
    if (!out.some((h) => h.m === m) && realCover(coverUrl(m)))
      out.push({ m, date: "", number: null, cover: coverUrl(m)! });
  }
  return out;
}

/** 発売日ラベル: "2026-07-15"→"7/15発売" / "2026-07"(月精度)→"7月発売" */
export function releaseDayLabel(date: string): string | null {
  if (!date) return null;
  const mm = Number(date.slice(5, 7));
  if (date.length >= 10) return `${mm}/${Number(date.slice(8, 10))}発売`;
  return `${mm}月発売`;
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

export function Cover({ m, sizes = "120px", src }: { m: Manga; sizes?: string; src?: string | null }) {
  const c = src ?? coverUrl(m);
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

// ★D3本採用(2026-08-13 ユーザGO): ナビは全ビルドでモノクロSVG線画(絵文字廃止)。
const NAV_D3 = true;

function NavSvg({ d, circle }: { d: string; circle?: [number, number, number] }) {
  return (
    <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" style={{ stroke: "var(--color-accent)", fill: "none", strokeWidth: 1.9 }}>
      {circle && <circle cx={circle[0]} cy={circle[1]} r={circle[2]} />}
      <path d={d} />
    </svg>
  );
}

// SVG線画アイコン(ラベル→パス)。D3Nav(home)と同じ絵柄=サイト内で統一
const NAV_SVG: Record<string, { d: string; circle?: [number, number, number] }> = {
  "ホーム": { d: "M3 11L12 3l9 8M6 10v11h12V10" },
  "検索": { d: "M15 15l6 6", circle: [10.5, 10.5, 6] },
  // 新作=今月の新刊一覧(/shinkan)。≡メニューの「今月の新刊一覧」タイル(box)と同じ絵柄
  "新作": { d: "M21 8l-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8" },
  "AI書評": { d: "M4 20l2-6L16 4l4 4L10 18l-6 2zM14 6l4 4" },
  "過去ログ": { d: "M12 7v5l3.5 2", circle: [12, 12, 8.5] },
  "使い方": { d: "M12 5c-2-1.6-5-1.6-8-.6V19c3-1 6-1 8 .6 2-1.6 5-1.6 8-.6V4.4c-3-1-6-1-8 .6zM12 5v14" },
};

export function DesignNav({ current: _current }: { current?: number }) {
  // ★2026-06-14: アイコン式の単一ナビ。 🏠ホームは左固定、 残りは右寄せクラスタ(≡メニュー含む)。
  //   全ページ共通。 旧テキスト行 + 旧 ScrollShortcutsMock を統合・廃止。
  // ★2026-09-02 ユーザ裁定: 「一覧」を外し、検索を先頭に・その右に「新作」(=今月の新刊一覧 /shinkan)。
  //   /list 自体は ≡メニュー「一覧表(全作品)」とフッターから引き続き到達可。home の D3Nav も同順に揃える。
  const cell =
    "spring-press flex flex-col items-center gap-0.5 active:scale-90";
  const right = [
    ["🔍", "検索", "/browse"],
    ["🆕", "新作", "/shinkan"],
    ["📝", "AI書評", "/column-ai-league"],
    ["🕘", "過去ログ", "/sansedai-archive"],
    ["🔰", "使い方", "/about"],
  ] as const;
  const Icon = ({ emoji, label }: { emoji: string; label: string }) =>
    NAV_D3 && NAV_SVG[label] ? (
      <NavSvg d={NAV_SVG[label].d} circle={NAV_SVG[label].circle} />
    ) : (
      <span className="text-[18px] leading-none">{emoji}</span>
    );
  return (
    <div className="flex items-center border-b border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-1.5">
      {/* 左固定 = ホーム */}
      <Link href="/" aria-label="ホーム" className={cell}>
        <Icon emoji="🏠" label="ホーム" />
        <span className="text-[9px] text-ink/55">ホーム</span>
      </Link>
      {/* 右寄せクラスタ */}
      <div className="ml-auto flex items-center gap-3.5">
        {right.map(([icon, label, href]) => (
          <Link key={label} href={href} aria-label={label} className={cell}>
            <Icon emoji={icon} label={label} />
            <span className="text-[9px] text-ink/55">{label}</span>
          </Link>
        ))}
        {/* ≡メニューは共通ヘッダー右端へ移設(2026-08-12 ユーザ裁定)=ナビ行は使い方が右端 */}
      </div>
    </div>
  );
}
