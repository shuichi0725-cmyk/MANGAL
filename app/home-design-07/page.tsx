import Link from "next/link";
import { bundle, DesignNav, seeded, volCount, Cover, CoverTile } from "@/lib/homeDesign";

/** 案7: 合成案 — ホーム=コーナーの目次。ヒーロー(3)+新刊棚(2)+特集(3)+運命の一冊(5)+入口群(4/6) */
export default function Design07() {
  const { manga, byNew, completedClassics } = bundle();
  const hero = completedClassics[0];
  const newShelf = byNew.slice(0, 12);
  const fiveVols = manga.filter((m) => m.status === "completed" && volCount(m) >= 3 && volCount(m) <= 5).slice(0, 6);
  const random1 = seeded(manga, (m) => m.slug, 1, 23)[0];

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-12">
      <DesignNav current={7} />

      {/* ── ヘッダー: ロゴ+検索は薄く(コーナーの邪魔をしない) ── */}
      <header className="px-4 pb-3 pt-5">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-extrabold tracking-tight">
            MANGAL<span className="text-[var(--color-accent)]">.</span>
            <span className="ml-2 align-middle text-[11px] font-medium text-ink/50">日本の漫画データベース</span>
          </h1>
          <span className="text-lg">≡</span>
        </div>
        <div className="mt-3 flex items-center gap-2 rounded-full border border-[var(--color-line)] bg-white px-4 py-2 text-sm text-ink/45 shadow-sm">
          🔍 {manga.length.toLocaleString()}作品から検索…
        </div>
      </header>

      {/* ── コーナー1: 今週の一冊(案3のヒーロー) ── */}
      {hero && (
        <section className="mt-2 border-y border-[var(--color-line)] bg-[var(--color-surface)] px-4 py-5">
          <Link href={`/manga/${hero.slug}`} className="flex gap-4 spring-press">
            <div className="w-28 shrink-0 rotate-[-2deg] shadow-xl">
              <Cover m={hero} sizes="112px" />
            </div>
            <div className="min-w-0 self-center">
              <p className="inline-block bg-ink px-2 py-0.5 text-[10px] font-bold tracking-widest text-white">今週の一冊</p>
              <p className="mt-1.5 text-lg font-extrabold leading-snug line-clamp-2">{hero.title}</p>
              <p className="mt-1.5 border-l-2 border-[var(--color-accent)] pl-2 text-[12px] leading-relaxed text-ink/70 line-clamp-4">
                {hero.synopsis ?? `${hero.authors.map((a) => a.name).join("・")}、全${volCount(hero)}巻。`}
              </p>
            </div>
          </Link>
        </section>
      )}

      {/* ── コーナー2: 新刊棚(案2の棚を1本だけ) ── */}
      <section className="mt-7 px-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-[15px] font-bold">📦 今月の新刊</h2>
          <span className="text-[11px] text-ink/50">新刊カレンダー →</span>
        </div>
        <ul className="-mx-4 mt-2.5 flex gap-3 overflow-x-auto px-4 pb-2 snap-x">
          {newShelf.map((m) => (
            <li key={m.slug} className="w-[104px] shrink-0 snap-start">
              <CoverTile m={m} sizes="104px" />
            </li>
          ))}
        </ul>
      </section>

      {/* ── コーナー3: 特集(案3、自動生成・週替わり) ── */}
      <section className="mt-7 px-4">
        <h2 className="border-l-4 border-[var(--color-accent)] pl-2.5 text-[15px] font-extrabold">
          特集: 週末で読み切る、全5巻以内の完結作
        </h2>
        <p className="mt-1 pl-3.5 text-[11.5px] text-ink/60">短いのに濃い。一気読みの満足感で選んだ6作。</p>
        <ul className="mt-3 grid grid-cols-3 gap-3">
          {fiveVols.map((m) => (
            <li key={m.slug}><CoverTile m={m} sizes="110px" /></li>
          ))}
        </ul>
        <p className="mt-2 text-right text-[11px] text-ink/50">過去の特集を見る →</p>
      </section>

      {/* ── コーナー4: 運命の一冊(案5の切り出し) ── */}
      {random1 && (
        <section className="mt-7 px-4">
          <Link href={`/manga/${random1.slug}`} className="flex gap-3 rounded-xl border border-[var(--color-line)] bg-gradient-to-r from-[var(--color-surface)] to-[var(--color-surface-2)] p-3.5 shadow-sm">
            <div className="w-16 shrink-0"><Cover m={random1} sizes="64px" /></div>
            <div className="min-w-0 self-center">
              <p className="text-[10px] font-bold tracking-widest text-[var(--color-accent)]">🎲 運命の一冊</p>
              <p className="mt-0.5 text-[14px] font-bold leading-snug line-clamp-2">{random1.title}</p>
              <p className="text-[11px] text-ink/55">{random1.authors.map((a) => a.name).join("・")} ・ 全{volCount(random1)}巻</p>
            </div>
            <span className="ml-auto self-center text-ink/30">↻</span>
          </Link>
        </section>
      )}

      {/* ── コーナー5: 入口群(4の索引と6の一覧表は専用ページへの扉に) ── */}
      <section className="mt-8 px-4">
        <h2 className="text-[13px] font-bold text-ink/60">じっくり探す</h2>
        <div className="mt-2.5 grid grid-cols-2 gap-2.5">
          {[
            ["📋 一覧表で探す", "全作品をソート・フィルター(案6)"],
            ["🏷️ ジャンルから", "スポーツ/SF/恋愛/ホラー…"],
            ["あ 50音さくいん", "題名・著者名から(案4)"],
            ["📚 あなたの本棚", "所持巻を記録(登録不要)"],
          ].map(([t, d]) => (
            <div key={t} className="rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] p-3 shadow-sm">
              <p className="text-[13px] font-bold text-ink/85">{t}</p>
              <p className="mt-0.5 text-[10.5px] leading-snug text-ink/50">{d}</p>
            </div>
          ))}
        </div>
      </section>

      <p className="mt-9 text-center text-[10px] tracking-widest text-ink/35">
        コーナーは編成替え可能 ・ 特集は自動生成で週替わり
      </p>
    </div>
  );
}
