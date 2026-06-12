import Link from "next/link";
import LikeButtonMock from "@/components/LikeButtonMock";
import ScrollShortcutsMock from "@/components/ScrollShortcutsMock";
import { bundle, DesignNav, seeded, volCount, latestDate, Cover, CoverTile } from "@/lib/homeDesign";

/** 案10: 編成B「実用先行」 — 計器盤+新刊+検索例を上に、物語性コーナーは中段、索引が最深。
 *  浅→深: 計器盤 → 新刊 → 完結したて(新) → 今週の一冊 → 三世代 → 1巻完結棚(新) → 画集(新) → 入口群 */
export default function Design10() {
  const { manga, byNew, completedClassics, data } = bundle();
  const hero = completedClassics[1] ?? completedClassics[0];

  // 新パーツ: 完結したて(最新刊が新しい完結作)
  const justCompleted = manga
    .filter((m) => m.status === "completed" && volCount(m) >= 3)
    .sort((a, b) => (latestDate(b) ?? "").localeCompare(latestDate(a) ?? ""))
    .slice(0, 6);
  // 新パーツ: 1巻完結棚
  const oneShot = manga.filter((m) => volCount(m) === 1).slice(0, 8);
  // 新パーツ: 画集
  const artBooks = data.artBooks.slice(0, 6);

  const Tile = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
    <div className={`rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] shadow-sm ${className}`}>{children}</div>
  );

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-12">
      <DesignNav current={10} />
      <ScrollShortcutsMock />

      {/* 1. 計器盤+検索例(実用の顔) */}
      <div className="mt-4 px-4">
        <div className="flex items-center gap-2 rounded-full border border-[var(--color-line)] bg-white px-4 py-2.5 text-sm text-ink/45 shadow-sm">
          🔍 {manga.length.toLocaleString()}作品から検索…
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
          {["完結 全5巻以内", "90年代 スポーツ", "連載中 ファンタジー", "アニメ化済み"].map((t) => (
            <span key={t} className="rounded-full border border-[var(--color-line)] bg-[var(--color-surface-2)] px-2.5 py-1 text-ink/65">{t}</span>
          ))}
        </div>
      </div>

      {/* 2. 新刊(実用先行なので最上段) */}
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

      {/* 3. 🆕 完結したて(「いま全巻買える」=アフィ導線として強い) */}
      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[14px] font-extrabold">🏁 完結したて — いま一気読みできる</h2>
            <span className="text-[11px] text-ink/50">完結作品 →</span>
          </div>
          <ul className="mt-2.5 grid grid-cols-3 gap-3">
            {justCompleted.map((m) => (<li key={m.slug}><CoverTile m={m} sizes="104px" /></li>))}
          </ul>
        </Tile>
      </section>

      {/* 4. 今週の一冊(物語性は中段から) */}
      {hero && (
        <section className="mt-4 px-4">
          <Tile className="overflow-hidden">
            <Link href={`/manga/${hero.slug}`} className="flex gap-4 p-4 spring-press">
              <div className="w-28 shrink-0 rotate-[-2deg] shadow-xl"><Cover m={hero} sizes="112px" /></div>
              <div className="min-w-0 self-center">
                <p className="inline-block rounded bg-ink px-2 py-0.5 text-[10px] font-bold tracking-widest text-white">今週の一冊</p>
                <p className="mt-1.5 text-lg font-extrabold leading-snug line-clamp-2">{hero.title}</p>
                <p className="mt-1.5 border-l-2 border-[var(--color-accent)] pl-2 text-[12px] leading-relaxed text-ink/70 line-clamp-3">
                  {hero.synopsis ?? `${hero.authors.map((a) => a.name).join("・")}、全${volCount(hero)}巻。`}
                </p>
              </div>
            </Link>
          </Tile>
        </section>
      )}

      {/* 5. 三世代(フル3人) */}
      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[14px] font-extrabold">👥 三世代、今日の一冊</h2>
            <Link href="/sansedai-archive" className="text-[11px] font-semibold text-[var(--color-accent)]">過去ログ →</Link>
          </div>
          <div className="mt-2.5 space-y-2.5">
            {[
              { slug: "kimetsu-no-yaiba", persona: "ミナト(10-20代)", copy: "今さら?って言われても推す。1巻の絶望から全部が伏線🔥", likes: 128 },
              { slug: "slam-dunk", persona: "サオリ(30-40代)", copy: "バスケ漫画ではなく、青春の総量を描いた漫画です。", likes: 211 },
              { slug: "hokuto-no-ken", persona: "圭三(50代以上)", copy: "北斗は「強さ」ではなく「哀しみ」の漫画だと、歳を重ねるほどに分かります。", likes: 96 },
            ].map((p) => {
              const m = manga.find((x) => x.slug === p.slug);
              if (!m) return null;
              return (
                <Link key={p.slug} href={`/manga/${m.slug}`} className="spring-press flex gap-3 rounded-lg border border-[var(--color-line)]/70 bg-[var(--color-bg)]/50 p-2.5">
                  <div className="w-12 shrink-0 self-start"><Cover m={m} sizes="48px" /></div>
                  <div className="min-w-0">
                    <p className="text-[10px] font-bold text-[var(--color-accent)]">{p.persona}</p>
                    <p className="text-[13px] font-bold leading-snug">{m.title}</p>
                    <p className="mt-0.5 text-[12px] leading-relaxed text-ink/75 line-clamp-2">{p.copy}</p>
                    <div className="mt-1"><LikeButtonMock id={`d10:${p.slug}`} base={p.likes} /></div>
                  </div>
                </Link>
              );
            })}
          </div>
        </Tile>
      </section>

      {/* 6. 🆕 1巻完結棚(スキマ時間ニーズ) */}
      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[14px] font-extrabold">⚡ 1冊で完結 — 今夜読み切れる</h2>
            <span className="text-[11px] text-ink/50">1巻完結 →</span>
          </div>
          <ul className="-mx-3.5 mt-2.5 flex gap-3 overflow-x-auto px-3.5 pb-1 snap-x">
            {oneShot.map((m) => (
              <li key={m.slug} className="w-[96px] shrink-0 snap-start"><CoverTile m={m} sizes="96px" /></li>
            ))}
          </ul>
        </Tile>
      </section>

      {/* 7. 🆕 画集コーナー(別ストリームの出口) */}
      {artBooks.length > 0 && (
        <section className="mt-4 px-4">
          <Tile className="p-3.5">
            <div className="flex items-baseline justify-between">
              <h2 className="text-[14px] font-extrabold">🎨 画集の部屋</h2>
              <span className="text-[11px] text-ink/50">画集一覧 →</span>
            </div>
            <ul className="mt-2.5 grid grid-cols-3 gap-2 text-[11px]">
              {artBooks.map((ab) => (
                <li key={ab.slug} className="rounded border border-[var(--color-line)] bg-[var(--color-bg)]/60 p-2">
                  <p className="font-bold leading-snug line-clamp-2">{ab.title}</p>
                  <p className="mt-0.5 text-[10px] text-ink/50">{ab.artist}</p>
                </li>
              ))}
            </ul>
          </Tile>
        </section>
      )}

      {/* 8. 入口群 */}
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
