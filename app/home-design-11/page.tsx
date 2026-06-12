import Link from "next/link";
import LikeButtonMock from "@/components/LikeButtonMock";
import MarqueeTitle from "@/components/MarqueeTitle";
import ScrollShortcutsMock from "@/components/ScrollShortcutsMock";
import { bundle, DesignNav, seeded, volCount, Cover, CoverTile } from "@/lib/homeDesign";

/** 案11: 編成C「リズム重視」 — 大(ヒーロー)→小(ことば)→中(棚)→小(豆知識)→… と
 *  コーナーの大小を交互に置いて縦読みのテンポを作る。 新パーツ: ことばカード/ジャンルルーレット/数字トリビア */
export default function Design11() {
  const { manga, byNew, completedClassics } = bundle();
  const daySalt = Number(new Date().toISOString().slice(0, 10).replace(/-/g, ""));
  const hero = completedClassics[2] ?? completedClassics[0];

  // 新パーツ: ことばカード = あらすじから今日の一文(synopsis 冒頭文を日替わり)
  const withSyn = manga.filter((m) => m.synopsis && m.synopsis.length > 40);
  const kotoba = seeded(withSyn, (m) => m.slug, 1, daySalt + 11)[0];
  // 新パーツ: ジャンルルーレット(日替わり1ジャンル)
  const genrePool = ["SF", "ミステリー", "スポーツ", "ファンタジー", "ホラー", "ドラマ"];
  const todayGenre = genrePool[daySalt % genrePool.length];
  // 新パーツ: 数字トリビア
  const longest = [...manga].sort((a, b) => volCount(b) - volCount(a))[0];

  const Tile = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
    <div className={`rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] shadow-sm ${className}`}>{children}</div>
  );

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-12">
      <DesignNav current={11} />
      <ScrollShortcutsMock />

      {/* 1.【大】今週の一冊 */}
      {hero && (
        <section className="mt-4 px-4">
          <Tile className="overflow-hidden">
            <Link href={`/manga/${hero.slug}`} className="flex gap-4 p-4 spring-press">
              <div className="w-28 shrink-0 rotate-[-2deg] shadow-xl"><Cover m={hero} sizes="112px" /></div>
              <div className="min-w-0 self-center">
                <p className="inline-block rounded bg-ink px-2 py-0.5 text-[10px] font-bold tracking-widest text-white">今週の一冊</p>
                <p className="mt-1.5 text-lg font-extrabold leading-snug line-clamp-2">{hero.title}</p>
                <p className="mt-1.5 border-l-2 border-[var(--color-accent)] pl-2 text-[12px] leading-relaxed text-ink/70 line-clamp-3">
                  {hero.synopsis ?? `全${volCount(hero)}巻。`}
                </p>
              </div>
            </Link>
          </Tile>
        </section>
      )}

      {/* 2.【小・新】ことばカード = あらすじの一文だけ大きく(縦読みの「息継ぎ」) */}
      {kotoba && (
        <section className="mt-4 px-4">
          <Link href={`/manga/${kotoba.slug}`} className="block rounded-xl bg-ink px-5 py-6 text-center shadow-md spring-press">
            <p className="text-[15px] font-bold leading-relaxed text-white">
              「{kotoba.synopsis!.split("。")[0]}。」
            </p>
            <p className="mt-2 text-[11px] text-white/60">— 今日のことば: 『{kotoba.title}』のあらすじから</p>
          </Link>
        </section>
      )}

      {/* 3.【中】新刊棚(★題=1行オートスクロール+下に作者。はみ出す題だけ動く) */}
      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[14px] font-bold">📦 今月の新刊</h2>
            <span className="text-[11px] text-ink/50">カレンダー →</span>
          </div>
          <ul className="-mx-3.5 mt-2.5 flex gap-3 overflow-x-auto px-3.5 pb-1 snap-x">
            {byNew.slice(0, 12).map((m) => (
              <li key={m.slug} className="w-[96px] shrink-0 snap-start">
                <Link href={`/manga/${m.slug}`} className="block group spring-press">
                  <Cover m={m} sizes="96px" />
                  <MarqueeTitle text={m.title} className="mt-1 text-[12px] leading-snug text-ink/85 group-hover:text-[var(--color-accent)]" />
                  <p className="truncate text-[10px] text-ink/50">{m.authors.map((a) => a.name).join("・")}</p>
                </Link>
              </li>
            ))}
          </ul>
        </Tile>
      </section>

      {/* 3.5【中・新】発売カレンダー(実データの日付から自動生成。本番=蒸留毎日運転で当月化) */}
      {(() => {
        const byDay = new Map<string, Map<number, number>>();
        for (const m of manga) {
          for (const ed of m.editions) {
            for (const v of ed.volumes) {
              const d = v.release_date || "";
              if (/^\d{4}-\d{2}-\d{2}$/.test(d) && d >= "2025-01") {
                const ym = d.slice(0, 7);
                const day = Number(d.slice(8, 10));
                if (!byDay.has(ym)) byDay.set(ym, new Map());
                const mm = byDay.get(ym)!;
                mm.set(day, (mm.get(day) ?? 0) + 1);
              }
            }
          }
        }
        const best = [...byDay.entries()].sort((a, b) => {
          const ca = [...a[1].values()].reduce((x, y) => x + y, 0);
          const cb = [...b[1].values()].reduce((x, y) => x + y, 0);
          return cb - ca || b[0].localeCompare(a[0]);
        })[0];
        if (!best) return null;
        const [ym, days] = best;
        const maxN = Math.max(...days.values());
        return (
          <section className="mt-4 px-4">
            <Tile className="p-3.5">
              <div className="flex items-baseline justify-between">
                <h2 className="text-[14px] font-extrabold">📅 発売カレンダー <span className="text-[11px] font-semibold text-ink/50">{ym.replace("-", "年")}月</span></h2>
                <span className="text-[10px] text-ink/45">●=発売あり(濃いほど多い)</span>
              </div>
              <div className="mt-2.5 grid grid-cols-7 gap-1 text-center">
                {["日", "月", "火", "水", "木", "金", "土"].map((w) => (
                  <span key={w} className="text-[9px] font-semibold text-ink/40">{w}</span>
                ))}
                {(() => {
                  const first = new Date(`${ym}-01T00:00:00`);
                  const pad = first.getDay();
                  const last = new Date(Number(ym.slice(0, 4)), Number(ym.slice(5, 7)), 0).getDate();
                  const cells = [];
                  for (let i = 0; i < pad; i++) cells.push(<span key={`p${i}`} />);
                  for (let d = 1; d <= last; d++) {
                    const n = days.get(d) ?? 0;
                    const op = n === 0 ? 0 : 0.25 + 0.75 * (n / maxN);
                    cells.push(
                      <span key={d} className="spring-press relative flex h-8 flex-col items-center justify-center rounded text-[10px] text-ink/70" style={n ? { backgroundColor: `color-mix(in srgb, var(--color-accent) ${Math.round(op * 28)}%, transparent)` } : undefined}>
                        {d}
                        {n > 0 && <span className="text-[8px] font-bold text-[var(--color-accent)]">{n}</span>}
                      </span>,
                    );
                  }
                  return cells;
                })()}
              </div>
              <p className="mt-2 text-[10px] text-ink/45">タップでその日の発売一覧へ(本番) ・ 蒸留を毎日運転すれば当月+来月の予約も載る</p>
            </Tile>
          </section>
        );
      })()}

      {/* 4.【小・新】数字トリビア */}
      {longest && (
        <section className="mt-4 px-4">
          <div className="flex items-center gap-3 rounded-xl border border-dashed border-[var(--color-line)] bg-[var(--color-surface-2)]/60 px-4 py-3">
            <span className="text-2xl">🔢</span>
            <p className="text-[12px] leading-relaxed text-ink/75">
              <b>きょうの数字:</b> 収録最長は『{longest.title}』の<b className="text-[var(--color-accent)]"> 全{volCount(longest)}巻</b>。1日1冊でも読破に{Math.ceil(volCount(longest) / 30)}ヶ月。
            </p>
          </div>
        </section>
      )}

      {/* 5.【中】三世代(★日替わり編成: 3人そろい/1人当番/2人ペア をローテーション) */}
      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          {(() => {
            const POOL = [
              { slug: "kimetsu-no-yaiba", persona: "ミナト(10-20代)", copy: "今さら?って言われても推す。1巻の絶望から全部が伏線🔥", likes: 128 },
              { slug: "slam-dunk", persona: "サオリ(30-40代)", copy: "「左手はそえるだけ」を超える最終話を、私はまだ知りません。青春の総量を描いた漫画です。", likes: 211 },
              { slug: "hokuto-no-ken", persona: "圭三(50代以上・古書店主)", copy: "昭和五十八年、ジャンプにこれが載った日のことを覚えております。北斗は「強さ」ではなく「哀しみ」の漫画だと、歳を重ねるほどに分かります。", likes: 96 },
            ];
            const mode = daySalt % 3; // 0=そろい踏み / 1=1人当番 / 2=ペア
            const pick = daySalt % POOL.length;
            const today = mode === 0 ? POOL : mode === 1 ? [POOL[pick]] : POOL.filter((_, i) => i !== pick);
            const label = mode === 0 ? "今日は3人そろい踏み" : mode === 1 ? "今日の当番" : "今日はペアでお届け";
            return (
              <>
                <div className="flex items-baseline justify-between">
                  <h2 className="text-[14px] font-extrabold">👥 三世代、今日の一冊 <span className="ml-1 text-[10px] font-semibold text-ink/45">{label}</span></h2>
                  <Link href="/sansedai-archive" className="text-[11px] font-semibold text-[var(--color-accent)]">過去ログ →</Link>
                </div>
                <div className="mt-2.5 space-y-2.5">
                  {today.map((p) => {
                    const m = manga.find((x) => x.slug === p.slug);
                    if (!m) return null;
                    return (
                      <Link key={p.slug} href={`/manga/${m.slug}`} className={`spring-press flex gap-3 ${today.length > 1 ? "rounded-lg border border-[var(--color-line)]/70 bg-[var(--color-bg)]/50 p-2.5" : "mt-1"}`}>
                        <div className="w-14 shrink-0 self-start"><Cover m={m} sizes="56px" /></div>
                        <div className="min-w-0">
                          <p className="text-[10px] font-bold text-[var(--color-accent)]">{p.persona}</p>
                          <p className="text-[13px] font-bold">{m.title}</p>
                          <p className={`mt-0.5 text-[12px] leading-relaxed text-ink/75 ${today.length === 1 ? "" : "line-clamp-2"}`}>{p.copy}</p>
                          <div className="mt-1"><LikeButtonMock id={`d11:${p.slug}`} base={p.likes} /></div>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              </>
            );
          })()}
        </Tile>
      </section>

      {/* 6.【小・新】ジャンルルーレット */}
      <section className="mt-4 px-4">
        <Link href={`/?genre=${todayGenre}`} className="block rounded-xl bg-gradient-to-r from-[var(--color-accent)] to-[var(--color-accent)]/80 px-4 py-3.5 text-white shadow-md spring-press">
          <p className="text-[13px] font-bold leading-snug">🎡 今日のジャンルルーレット: <span className="text-[16px] whitespace-nowrap">{todayGenre}</span></p>
          <p className="mt-0.5 text-right text-[11px] opacity-85">回ったジャンルの棚へ →</p>
        </Link>
      </section>

      {/* 7.【中】特集 */}
      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <h2 className="border-l-4 border-[var(--color-accent)] pl-2.5 text-[14px] font-extrabold">特集: 週末で読み切る、全5巻以内の完結作</h2>
          <ul className="mt-3 grid grid-cols-3 gap-3">
            {manga.filter((m) => m.status === "completed" && volCount(m) >= 3 && volCount(m) <= 5).slice(0, 6).map((m) => (
              <li key={m.slug}><CoverTile m={m} sizes="104px" /></li>
            ))}
          </ul>
        </Tile>
      </section>

      {/* 8.【小】運命の一冊 → 9.【深】入口群 */}
      {(() => {
        const r = seeded(manga, (m) => m.slug, 1, daySalt)[0];
        return r ? (
          <section className="mt-4 px-4">
            <Link href={`/manga/${r.slug}`} className="block spring-press">
              <Tile className="flex gap-3 p-3.5">
                <div className="w-14 shrink-0"><Cover m={r} sizes="56px" /></div>
                <div className="min-w-0 self-center">
                  <p className="text-[10px] font-bold tracking-widest text-[var(--color-accent)]">🎲 運命の一冊</p>
                  <p className="text-[13px] font-bold leading-snug line-clamp-2">{r.title}</p>
                </div>
                <span className="ml-auto self-center text-ink/30">↻</span>
              </Tile>
            </Link>
          </section>
        ) : null;
      })()}
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
