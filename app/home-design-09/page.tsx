import Link from "next/link";
import LikeButtonMock from "@/components/LikeButtonMock";
import ScrollShortcutsMock from "@/components/ScrollShortcutsMock";
import { bundle, DesignNav, seeded, volCount, Cover, CoverTile } from "@/lib/homeDesign";

export const metadata = { robots: { index: false, follow: false } };  // 実験頁=非索引

/** 案9: 編成A「出会い重視」 — 人格と物語性を上に、実用は下に。
 *  浅→深: 今週の一冊 → 三世代 → 特集 → 新刊 → 作家特集(新) → 連載誌の棚(新) → 入口群 */
export default function Design09() {
  const { manga, byNew, completedClassics } = bundle();
  const daySalt = Number(new Date().toISOString().slice(0, 10).replace(/-/g, ""));
  const hero = completedClassics[0];
  const fiveVols = manga.filter((m) => m.status === "completed" && volCount(m) >= 3 && volCount(m) <= 5).slice(0, 6);

  // 新パーツ: 今日の作家(同一作者の作品が2作以上ある作家を日替わり)
  const byAuthor = new Map<string, typeof manga>();
  for (const m of manga) {
    for (const a of m.authors) {
      byAuthor.set(a.name, [...(byAuthor.get(a.name) ?? []), m]);
    }
  }
  const authors = [...byAuthor.entries()].filter(([, ws]) => ws.length >= 2);
  const todayAuthor = seeded(authors, ([n]) => n, 1, daySalt + 3)[0];

  // 新パーツ: 連載誌の棚
  const byMag = new Map<string, typeof manga>();
  for (const m of manga) {
    if (m.magazine) byMag.set(m.magazine, [...(byMag.get(m.magazine) ?? []), m]);
  }
  const topMag = [...byMag.entries()].sort((a, b) => b[1].length - a[1].length)[0];

  const Tile = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
    <div className={`rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] shadow-sm ${className}`}>{children}</div>
  );

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-12">
      <DesignNav current={9} />
      <ScrollShortcutsMock />

      {/* 1. ヒーロー: 今週の一冊 */}
      {hero && (
        <section className="mt-4 px-4">
          <Tile className="overflow-hidden">
            <Link href={`/manga/${hero.slug}`} className="flex gap-4 p-4 spring-press">
              <div className="w-28 shrink-0 rotate-[-2deg] shadow-xl"><Cover m={hero} sizes="112px" /></div>
              <div className="min-w-0 self-center">
                <p className="inline-block rounded bg-ink px-2 py-0.5 text-[10px] font-bold tracking-widest text-white">今週の一冊</p>
                <p className="mt-1.5 text-lg font-extrabold leading-snug line-clamp-2">{hero.title}</p>
                <p className="mt-1.5 border-l-2 border-[var(--color-accent)] pl-2 text-[12px] leading-relaxed text-ink/70 line-clamp-4">
                  {hero.synopsis ?? `${(hero.authors ?? []).map((a) => a.name).join("・")}、全${volCount(hero)}巻。`}
                </p>
              </div>
            </Link>
          </Tile>
        </section>
      )}

      {/* 2. 三世代(ダイジェスト1人=日替わりで交代、 タップで3人版へ) */}
      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[14px] font-extrabold">👥 三世代、今日の一冊</h2>
            <Link href="/sansedai-archive" className="text-[11px] font-semibold text-[var(--color-accent)]">過去ログ →</Link>
          </div>
          {(() => {
            const m = manga.find((x) => x.slug === "slam-dunk");
            if (!m) return null;
            return (
              <Link href={`/manga/${m.slug}`} className="mt-2.5 flex gap-3 spring-press">
                <div className="w-14 shrink-0"><Cover m={m} sizes="56px" /></div>
                <div className="min-w-0">
                  <p className="text-[10px] font-bold text-[var(--color-accent)]">サオリ(30代・40代担当)</p>
                  <p className="text-[13px] font-bold">{m.title}</p>
                  <p className="mt-0.5 text-[12px] leading-relaxed text-ink/75 line-clamp-2">「左手はそえるだけ」を超える最終話を、私はまだ知りません。青春の総量を描いた漫画です。</p>
                  <div className="mt-1"><LikeButtonMock id="d9:slam-dunk" base={211} /></div>
                </div>
              </Link>
            );
          })()}
          <p className="mt-2 text-[10px] text-ink/45">他2人の推薦は過去ログで(ホームでは日替わり交代制)</p>
        </Tile>
      </section>

      {/* 3. 特集 */}
      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <h2 className="border-l-4 border-[var(--color-accent)] pl-2.5 text-[14px] font-extrabold">特集: 週末で読み切る、全5巻以内の完結作</h2>
          <ul className="mt-3 grid grid-cols-3 gap-3">
            {fiveVols.map((m) => (<li key={m.slug}><CoverTile m={m} sizes="104px" /></li>))}
          </ul>
        </Tile>
      </section>

      {/* 4. 新刊棚(実用は中段へ) */}
      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[14px] font-bold">📦 今月の新刊</h2>
            <span className="text-[11px] text-ink/50">カレンダー →</span>
          </div>
          <ul className="-mx-3.5 mt-2.5 flex gap-3 overflow-x-auto px-3.5 pb-1 snap-x">
            {byNew.slice(0, 12).map((m) => (
              <li key={m.slug} className="w-[96px] shrink-0 snap-start"><CoverTile m={m} sizes="96px" /></li>
            ))}
          </ul>
        </Tile>
      </section>

      {/* 5. 🆕 今日の作家(深掘りゾーン開始) */}
      {todayAuthor && (
        <section className="mt-4 px-4">
          <Tile className="p-3.5">
            <h2 className="text-[14px] font-extrabold">✒️ 今日の作家: {todayAuthor[0]}</h2>
            <p className="mt-0.5 text-[10.5px] text-ink/50">収録 {todayAuthor[1].length} 作品 — 全作品リストへ →</p>
            <ul className="-mx-3.5 mt-2.5 flex gap-3 overflow-x-auto px-3.5 pb-1 snap-x">
              {todayAuthor[1].slice(0, 8).map((m) => (
                <li key={m.slug} className="w-[96px] shrink-0 snap-start"><CoverTile m={m} sizes="96px" /></li>
              ))}
            </ul>
          </Tile>
        </section>
      )}

      {/* 6. 🆕 連載誌の棚 */}
      {topMag && (
        <section className="mt-4 px-4">
          <Tile className="p-3.5">
            <div className="flex items-baseline justify-between">
              <h2 className="text-[14px] font-extrabold">📰 連載誌の棚: {topMag[0]}</h2>
              <span className="text-[11px] text-ink/50">他の雑誌 →</span>
            </div>
            <ul className="mt-2.5 grid grid-cols-3 gap-3">
              {topMag[1].slice(0, 6).map((m) => (<li key={m.slug}><CoverTile m={m} sizes="104px" /></li>))}
            </ul>
          </Tile>
        </section>
      )}

      {/* 7. 入口群(最下部=いちばん深い人向け) */}
      <section className="mt-5 px-4">
        <div className="grid grid-cols-2 gap-2.5">
          {[
            ["📋 一覧表で探す", "全作品をソート・フィルター"],
            ["🏷️ ジャンルから", "スポーツ/SF/恋愛/ホラー…"],
            ["あ 50音さくいん", "題名・著者名から"],
            ["📚 あなたの本棚", "所持巻を記録(登録不要)"],
          ].map(([t, d]) => (
            <Tile key={t} className="p-3 spring-press"><p className="text-[13px] font-bold text-ink/85">{t}</p><p className="mt-0.5 text-[10.5px] text-ink/50">{d}</p></Tile>
          ))}
        </div>
      </section>
    </div>
  );
}
