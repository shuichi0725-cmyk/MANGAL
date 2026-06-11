import Link from "next/link";
import { bundle, DesignNav, seeded, volCount, Cover } from "@/lib/homeDesign";

/** 案5: ダッシュボード型 — タイルで一望。数字+ランダム1冊+新着+ジャンル分布 */
export default function Design05() {
  const { manga, byNew } = bundle();
  const random1 = seeded(manga, (m) => m.slug, 1, 23)[0];
  const serializing = manga.filter((m) => m.status !== "completed").length;
  const completed = manga.length - serializing;
  const Tile = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
    <div className={`rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm ${className}`}>{children}</div>
  );
  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-10">
      <DesignNav current={5} />
      <header className="flex items-center justify-between px-4 py-4">
        <h1 className="text-lg font-extrabold">MANGAL<span className="text-[var(--color-accent)]">.</span> <span className="text-xs font-medium text-ink/50">コックピット</span></h1>
        <span className="rounded-full border border-[var(--color-line)] px-3 py-1 text-[11px] text-ink/60">🔍 検索</span>
      </header>
      <div className="grid grid-cols-2 gap-3 px-4">
        <Tile>
          <p className="text-[11px] font-semibold text-ink/55">収録作品</p>
          <p className="mt-1 text-2xl font-black tabular-nums text-ink">{manga.length.toLocaleString()}</p>
          <p className="text-[10px] text-ink/45">本番 68,789</p>
        </Tile>
        <Tile>
          <p className="text-[11px] font-semibold text-ink/55">連載中 / 完結</p>
          <p className="mt-1 text-2xl font-black tabular-nums text-ink">{serializing}<span className="text-sm font-bold text-ink/40"> / {completed}</span></p>
          <p className="text-[10px] text-ink/45">完結率 {Math.round((completed / manga.length) * 100)}%</p>
        </Tile>
        {random1 && (
          <Link href={`/manga/${random1.slug}`} className="col-span-2">
            <Tile className="flex gap-3 !bg-gradient-to-r from-[var(--color-surface)] to-[var(--color-surface-2)]">
              <div className="w-16 shrink-0"><Cover m={random1} sizes="64px" /></div>
              <div className="min-w-0 self-center">
                <p className="text-[10px] font-bold tracking-widest text-[var(--color-accent)]">🎲 運命の一冊</p>
                <p className="mt-0.5 text-[14px] font-bold leading-snug line-clamp-2">{random1.title}</p>
                <p className="text-[11px] text-ink/55">{random1.authors.map((a) => a.name).join("・")} ・ 全{volCount(random1)}巻</p>
              </div>
            </Tile>
          </Link>
        )}
        <Tile className="col-span-2">
          <div className="flex items-baseline justify-between">
            <p className="text-[12px] font-bold text-ink/75">📦 今月の新刊</p>
            <span className="text-[10px] text-ink/45">すべて →</span>
          </div>
          <ul className="mt-2 space-y-1.5">
            {byNew.slice(0, 5).map((m) => (
              <li key={m.slug}>
                <Link href={`/manga/${m.slug}`} className="flex items-baseline gap-2">
                  <span className="h-1.5 w-1.5 shrink-0 translate-y-[-1px] rounded-full bg-[var(--color-accent)]" />
                  <span className="min-w-0 flex-1 truncate text-[13px] text-ink/85">{m.title}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Tile>
        <Tile>
          <p className="text-[12px] font-bold text-ink/75">ジャンル横断</p>
          <div className="mt-2 flex flex-wrap gap-1">
            {["スポーツ", "SF", "恋愛", "ホラー", "歴史", "料理"].map((g) => (
              <span key={g} className="rounded bg-[var(--color-surface-2)] px-1.5 py-0.5 text-[10px] text-ink/70">{g}</span>
            ))}
          </div>
        </Tile>
        <Tile>
          <p className="text-[12px] font-bold text-ink/75">📅 続刊カレンダー</p>
          <p className="mt-1.5 text-[11px] leading-relaxed text-ink/55">フォロー作品の発売日を .ics で購読(予定)</p>
        </Tile>
        <Tile className="col-span-2">
          <p className="text-[12px] font-bold text-ink/75">🏷️ 本棚(ローカル保存・登録不要)</p>
          <p className="mt-1.5 text-[11px] text-ink/55">所持巻を記録して「あと何冊」を一目で。サーバには何も送りません。</p>
        </Tile>
      </div>
    </div>
  );
}
