import Link from "next/link";
import { bundle, DesignNav, seeded, volCount, Cover, CoverTile } from "@/lib/homeDesign";

/** 案8: 7のコーナー編成 × 5のコックピット質感 + ヘッダーショートカット(確定済ヘッダーUI設計を反映)。
 *  アイコン下ラベルは「初回訪問時のみ表示」想定の状態で見せている。 */
export default function Design08() {
  const { manga, byNew, completedClassics } = bundle();
  const hero = completedClassics[0];
  const newShelf = byNew.slice(0, 12);
  const fiveVols = manga.filter((m) => m.status === "completed" && volCount(m) >= 3 && volCount(m) <= 5).slice(0, 6);
  const random1 = seeded(manga, (m) => m.slug, 1, 23)[0];
  const serializing = manga.filter((m) => m.status !== "completed").length;

  const Tile = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
    <div className={`rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] shadow-sm ${className}`}>{children}</div>
  );

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-12">
      <DesignNav current={8} />

      {/* ── ヘッダー: ロゴ + ショートカットアイコン群(一覧/書庫/使い方/検索 + ≡) ── */}
      <header className="sticky top-[37px] z-40 border-b border-[var(--color-line)] bg-[var(--color-surface)]/95 px-4 pb-2.5 pt-3.5 backdrop-blur">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-extrabold tracking-tight">
            MANGAL<span className="text-[var(--color-accent)]">.</span>
          </h1>
          <div className="flex items-start gap-4">
            {[
              ["📋", "一覧"],
              ["📚", "書庫"],
              ["🔰", "使い方"],
              ["🔍", "検索"],
              ["≡", "メニュー"],
            ].map(([icon, label]) => (
              <button key={label} className="flex flex-col items-center gap-0.5">
                <span className="text-[19px] leading-none">{icon}</span>
                <span className="text-[9px] text-ink/50">{label}</span>
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* ── 計器盤: 数字タイル(案5) ── */}
      <div className="mt-4 grid grid-cols-3 gap-2.5 px-4">
        <Tile className="p-3">
          <p className="text-[10px] font-semibold text-ink/55">収録作品</p>
          <p className="mt-0.5 text-lg font-black tabular-nums">{manga.length.toLocaleString()}</p>
        </Tile>
        <Tile className="p-3">
          <p className="text-[10px] font-semibold text-ink/55">連載中</p>
          <p className="mt-0.5 text-lg font-black tabular-nums text-emerald-700">{serializing}</p>
        </Tile>
        <Tile className="p-3">
          <p className="text-[10px] font-semibold text-ink/55">今月の新刊</p>
          <p className="mt-0.5 text-lg font-black tabular-nums text-[var(--color-accent)]">{newShelf.length}</p>
        </Tile>
      </div>

      {/* ── コーナー1: 今週の一冊(タイル化) ── */}
      {hero && (
        <section className="mt-4 px-4">
          <Tile className="overflow-hidden">
            <Link href={`/manga/${hero.slug}`} className="flex gap-4 p-4">
              <div className="w-28 shrink-0 rotate-[-2deg] shadow-xl">
                <Cover m={hero} sizes="112px" />
              </div>
              <div className="min-w-0 self-center">
                <p className="inline-block rounded bg-ink px-2 py-0.5 text-[10px] font-bold tracking-widest text-white">今週の一冊</p>
                <p className="mt-1.5 text-lg font-extrabold leading-snug line-clamp-2">{hero.title}</p>
                <p className="mt-1.5 border-l-2 border-[var(--color-accent)] pl-2 text-[12px] leading-relaxed text-ink/70 line-clamp-4">
                  {hero.synopsis ?? `${hero.authors.map((a) => a.name).join("・")}、全${volCount(hero)}巻。`}
                </p>
              </div>
            </Link>
          </Tile>
        </section>
      )}

      {/* ── コーナー2: 新刊棚 ── */}
      <section className="mt-5 px-4">
        <Tile className="p-3.5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[14px] font-bold">📦 今月の新刊</h2>
            <span className="text-[11px] text-ink/50">カレンダー →</span>
          </div>
          <ul className="-mx-3.5 mt-2.5 flex gap-3 overflow-x-auto px-3.5 pb-1 snap-x">
            {newShelf.map((m) => (
              <li key={m.slug} className="w-[96px] shrink-0 snap-start">
                <CoverTile m={m} sizes="96px" />
              </li>
            ))}
          </ul>
        </Tile>
      </section>

      {/* ── コーナー3: 特集 ── */}
      <section className="mt-5 px-4">
        <Tile className="p-3.5">
          <h2 className="border-l-4 border-[var(--color-accent)] pl-2.5 text-[14px] font-extrabold">
            特集: 週末で読み切る、全5巻以内の完結作
          </h2>
          <p className="mt-1 pl-3.5 text-[11.5px] text-ink/60">短いのに濃い。一気読みの満足感で選んだ6作。</p>
          <ul className="mt-3 grid grid-cols-3 gap-3">
            {fiveVols.map((m) => (
              <li key={m.slug}><CoverTile m={m} sizes="104px" /></li>
            ))}
          </ul>
        </Tile>
      </section>

      {/* ── コーナー3.5: 三世代の今日の一冊(ペルソナ別AIコピー=seed焼き込み想定のモック) ── */}
      <section className="mt-5 px-4">
        <Tile className="p-3.5">
          <h2 className="text-[14px] font-extrabold">👥 三世代、今日の一冊</h2>
          <p className="mt-0.5 text-[10.5px] text-ink/50">世代別の案内人が毎日1冊ずつ。口調も長さも三者三様。</p>
          <div className="mt-3 space-y-3">
            {[
              {
                slug: "kimetsu-no-yaiba",
                persona: "ミナト(10代・20代担当)",
                tone: "text-[12.5px]",
                copy: "今さら?って言われても推す。鬼滅はマジで1巻の絶望から全部が伏線。アニメ勢こそ原作の「間」を見てほしい、全23巻だから週末で完走できるよ🔥",
              },
              {
                slug: "slam-dunk",
                persona: "サオリ(30代・40代担当)",
                tone: "text-[12.5px]",
                copy: "「左手はそえるだけ」を超える最終話を、私はまだ知りません。あの頃ジャンプで読んだ人も、新装再編版で読み返すと桜木の成長線の引き方に唸るはず。バスケ漫画ではなく、青春の総量を描いた漫画です。",
              },
              {
                slug: "hokuto-no-ken",
                persona: "圭三(50代以上担当・古書店主)",
                tone: "text-[12.5px]",
                copy: "昭和五十八年、週刊少年ジャンプにこれが載った日のことを覚えております。世紀末という言葉がまだ遠い未来だった時代に、原哲夫の筆は荒野の風の匂いまで描いておりました。ラオウ昇天の回を店先で立ち読みして泣いた高校生も、いまや良い歳でしょう。読み返すなら、ぜひ通しで。北斗は「強さ」ではなく「哀しみ」の漫画だと、歳を重ねるほどに分かります。",
              },
            ].map((p) => {
              const m = manga.find((x) => x.slug === p.slug);
              if (!m) return null;
              return (
                <Link key={p.slug} href={`/manga/${m.slug}`} className="flex gap-3 rounded-lg border border-[var(--color-line)]/70 bg-[var(--color-bg)]/50 p-2.5">
                  <div className="w-14 shrink-0 self-start"><Cover m={m} sizes="56px" /></div>
                  <div className="min-w-0">
                    <p className="text-[10px] font-bold text-[var(--color-accent)]">{p.persona}</p>
                    <p className="text-[13px] font-bold leading-snug">{m.title}</p>
                    <p className={`mt-1 leading-relaxed text-ink/75 ${p.tone}`}>{p.copy}</p>
                  </div>
                </Link>
              );
            })}
          </div>
          <p className="mt-2.5 text-right text-[10px] text-ink/45">コピーはAI生成をseedに貯めて日替わり(ランタイムコスト0)</p>
        </Tile>
      </section>

      {/* ── コーナー4: 運命の一冊 ── */}
      {random1 && (
        <section className="mt-5 px-4">
          <Link href={`/manga/${random1.slug}`}>
            <Tile className="flex gap-3 !bg-gradient-to-r from-[var(--color-surface)] to-[var(--color-surface-2)] p-3.5">
              <div className="w-16 shrink-0"><Cover m={random1} sizes="64px" /></div>
              <div className="min-w-0 self-center">
                <p className="text-[10px] font-bold tracking-widest text-[var(--color-accent)]">🎲 運命の一冊</p>
                <p className="mt-0.5 text-[14px] font-bold leading-snug line-clamp-2">{random1.title}</p>
                <p className="text-[11px] text-ink/55">{random1.authors.map((a) => a.name).join("・")} ・ 全{volCount(random1)}巻</p>
              </div>
              <span className="ml-auto self-center text-ink/30">↻</span>
            </Tile>
          </Link>
        </section>
      )}

      {/* ── コーナー5: 入口タイル群 ── */}
      <section className="mt-5 px-4">
        <div className="grid grid-cols-2 gap-2.5">
          {[
            ["📋 一覧表で探す", "全作品をソート・フィルター"],
            ["🏷️ ジャンルから", "スポーツ/SF/恋愛/ホラー…"],
            ["あ 50音さくいん", "題名・著者名から"],
            ["📚 あなたの本棚", "所持巻を記録(登録不要)"],
          ].map(([t, d]) => (
            <Tile key={t} className="p-3">
              <p className="text-[13px] font-bold text-ink/85">{t}</p>
              <p className="mt-0.5 text-[10.5px] leading-snug text-ink/50">{d}</p>
            </Tile>
          ))}
        </div>
      </section>
    </div>
  );
}
