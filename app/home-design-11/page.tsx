import Link from "next/link";
import LikeButtonMock from "@/components/LikeButtonMock";
import DestinyPickMock from "@/components/DestinyPickMock";
import MarqueeTitle from "@/components/MarqueeTitle";
import ReleaseCalendarMock from "@/components/ReleaseCalendarMock";
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

  // ★三世代 v2(ユーザ設計 2026-06-12): ライター名簿=三世代×各2人(増員可・3の倍数)。
  //   毎日「各世代から1人ずつ」の3人が掲載。載り方が日替わり(0=3人一緒/1=ソロ+ペア/2=3ヶ所ソロ)。
  //   ★どのカードを押しても過去ログ(/sansedai-archive)へ。
  const WRITERS = [
    { gen: 0, persona: "ミナト(10-20代)", slug: "kimetsu-no-yaiba", copy: "今さら?って言われても推す。1巻の絶望から全部が伏線🔥 週末で完走できるよ", likes: 128 },
    { gen: 0, persona: "リコ(10-20代・美大生)", slug: "rozen-maiden", copy: "ドレスの皺一本まで「設定」じゃなくて「執念」。画集レベルの線を毎話やってるの、冷静に考えてやばい。", likes: 84 },
    { gen: 1, persona: "サオリ(30-40代)", slug: "slam-dunk", copy: "「左手はそえるだけ」を超える最終話を、私はまだ知りません。青春の総量を描いた漫画です。", likes: 211 },
    { gen: 1, persona: "タケル(30-40代・元書店員)", slug: "berserk", copy: "蝕の夜を越えて、それでも生きる方を選ぶ。店頭で何百回すすめたか分からない一作です。", likes: 188 },
    { gen: 2, persona: "圭三(50代以上・古書店主)", slug: "hokuto-no-ken", copy: "昭和五十八年、ジャンプにこれが載った日のことを覚えております。北斗は「強さ」ではなく「哀しみ」の漫画です。", likes: 96 },
    { gen: 2, persona: "静江(50代以上・喫茶店ママ)", slug: "urusei-yatsura", copy: "ラムちゃんの「ダーリン」で青春を過ごした身としては、何度読み返しても店の仕込みが止まるのよね。", likes: 102 },
  ];
  const sansedaiToday = [0, 1, 2].map((g) => {
    const pool = WRITERS.filter((w) => w.gen === g);
    return pool[(daySalt + g) % pool.length];
  });
  const sansedaiMode = daySalt % 3; // 0=3人一緒 / 1=ソロ+ペア / 2=3ヶ所ソロ
  const soloIdx = daySalt % 3;
  // slot A(ことばカード後)/ B(数字トリビア後)/ C(特集後) への振り分け
  const slotA = sansedaiMode === 0 ? [] : sansedaiMode === 1 ? [sansedaiToday[soloIdx]] : [sansedaiToday[0]];
  const slotB = sansedaiMode === 0 ? sansedaiToday : sansedaiMode === 2 ? [sansedaiToday[1]] : [];
  const slotC = sansedaiMode === 1 ? sansedaiToday.filter((_, i) => i !== soloIdx) : sansedaiMode === 2 ? [sansedaiToday[2]] : [];

  const SansedaiSlot = ({ group }: { group: typeof WRITERS }) => {
    if (group.length === 0) return null;
    const label = group.length === 3 ? "今日は3人そろい踏み" : group.length === 2 ? "ペアでお届け" : "の推し";
    return (
      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[14px] font-extrabold">
              👥 三世代、今日の一冊
              <span className="ml-1 text-[10px] font-semibold text-ink/45">
                {group.length === 1 ? `${group[0].persona.split("(")[0]}${label}` : label}
              </span>
            </h2>
            <span className="text-[11px] font-semibold text-[var(--color-accent)]">過去ログ →</span>
          </div>
          <div className="mt-2.5 space-y-2.5">
            {group.map((p) => {
              const m = manga.find((x) => x.slug === p.slug);
              if (!m) return null;
              return (
                <Link key={p.persona} href="/sansedai-archive" className={`spring-press flex gap-3 ${group.length > 1 ? "rounded-lg border border-[var(--color-line)]/70 bg-[var(--color-bg)]/50 p-2.5" : "mt-1"}`}>
                  <div className="w-14 shrink-0 self-start"><Cover m={m} sizes="56px" /></div>
                  <div className="min-w-0">
                    <p className="text-[10px] font-bold text-[var(--color-accent)]">{p.persona}</p>
                    <p className="text-[13px] font-bold">{m.title}</p>
                    <p className={`mt-0.5 text-[12px] leading-relaxed text-ink/75 ${group.length === 1 ? "" : "line-clamp-2"}`}>{p.copy}</p>
                    <div className="mt-1"><LikeButtonMock id={`d11:${p.slug}`} base={p.likes} /></div>
                  </div>
                </Link>
              );
            })}
          </div>
        </Tile>
      </section>
    );
  };

  const Tile = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
    <div className={`rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] shadow-sm ${className}`}>{children}</div>
  );

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-12">
      <DesignNav current={11} />
      <ScrollShortcutsMock />

      {/* 0.【極小】統計ストリップ: 場所を取らない1行、各数字タップでフィルター絞り込みへ */}
      {(() => {
        const books = manga.reduce((s, m) => s + m.editions.reduce((x, e) => x + e.volumes.length, 0), 0);
        const ongoing = manga.filter((m) => m.status !== "completed").length;
        const done = manga.length - ongoing;
        const S = ({ href, label, n }: { href: string; label: string; n: number }) => (
          <Link href={href} className="spring-press whitespace-nowrap">
            <span className="text-ink/50">{label}</span>{" "}
            <b className="tabular-nums text-ink/85">{n.toLocaleString()}</b>
          </Link>
        );
        return (
          <div className="flex items-center gap-x-3 overflow-x-auto px-4 pt-3 text-[11px]">
            <S href="/" label="作品" n={manga.length} />
            <span className="text-ink/25">|</span>
            <S href="/" label="漫画本" n={books} />
            <span className="text-ink/25">|</span>
            <S href="/?status=ongoing" label="連載中" n={ongoing} />
            <span className="text-ink/25">|</span>
            <S href="/?status=completed" label="完結" n={done} />
            <span className="ml-auto shrink-0 text-[10px] text-ink/40">タップで絞り込み</span>
          </div>
        );
      })()}

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

      {/* 2.5【三世代 slot A】ソロ or 散開時の1人目 */}
      <SansedaiSlot group={slotA} />

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

      {/* 3.5【中・新】発売カレンダー(日付タップ→直下に一覧展開。月データ埋込=完全静的) */}
      {(() => {
        const byDay = new Map<string, Map<number, Array<{ slug: string; title: string; authors: string }>>>();
        for (const m of manga) {
          for (const ed of m.editions) {
            for (const v of ed.volumes) {
              const d = v.release_date || "";
              if (/^\d{4}-\d{2}-\d{2}$/.test(d) && d >= "2025-01") {
                const ym = d.slice(0, 7);
                const day = Number(d.slice(8, 10));
                if (!byDay.has(ym)) byDay.set(ym, new Map());
                const mm = byDay.get(ym)!;
                if (!mm.has(day)) mm.set(day, []);
                mm.get(day)!.push({ slug: m.slug, title: m.title, authors: m.authors.map((a) => a.name).join("・") });
              }
            }
          }
        }
        const best = [...byDay.entries()].sort((a, b) => {
          const ca = [...a[1].values()].reduce((x, y) => x + y.length, 0);
          const cb = [...b[1].values()].reduce((x, y) => x + y.length, 0);
          return cb - ca || b[0].localeCompare(a[0]);
        })[0];
        if (!best) return null;
        const [ym, dmap] = best;
        const days = [...dmap.entries()].map(([d, items]) => ({ d, items }));
        return (
          <section className="mt-4 px-4">
            <Tile className="p-3.5">
              <div className="flex items-baseline justify-between">
                <h2 className="text-[14px] font-extrabold">📅 発売カレンダー <span className="spring-press text-[11px] font-semibold text-[var(--color-accent)]">{ym.replace("-", "年")}月 →</span></h2>
                <span className="text-[10px] text-ink/45">日付タップで一覧</span>
              </div>
              <ReleaseCalendarMock ym={ym} days={days} />
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

      {/* 5.【三世代 slot B】そろい踏み or 散開時の2人目 */}
      <SansedaiSlot group={slotB} />

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

      {/* 7.5【三世代 slot C】ペア or 散開時の3人目 */}
      <SansedaiSlot group={slotC} />

      {/* 8.【小】運命の一冊(★ガチャ化: ↻で再抽選・確率演出。候補プール埋込=通信ゼロ) */}
      <section className="mt-4 px-4">
        <Tile>
          <DestinyPickMock
            items={seeded(manga, (m) => m.slug, 60, daySalt).map((m) => ({
              slug: m.slug,
              title: m.title,
              authors: m.authors.map((a) => a.name).join("・"),
              vols: volCount(m),
            }))}
            initialIndex={daySalt % 60}
            total={manga.length}
          />
        </Tile>
      </section>
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
