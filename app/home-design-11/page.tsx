import Link from "next/link";
import LikeButtonMock from "@/components/LikeButtonMock";
import FeaturedDaily from "@/components/FeaturedDaily";
import AnniversaryDaily from "@/components/AnniversaryDaily";
import DeluxeWeekly from "@/components/DeluxeWeekly";
import TimeMachine from "@/components/TimeMachine";
import DestinyPickMock from "@/components/DestinyPickMock";
import MarqueeTitle from "@/components/MarqueeTitle";
import CalendarView from "@/components/CalendarView";
import HomeSidebar from "@/components/HomeSidebar";
import { bundle, DesignNav, seeded, volCount, Cover, CoverTile, thisMonthReleases } from "@/lib/homeDesign";
import { coverUrl } from "@/lib/schema";
import { loadAiReviews } from "@/lib/loadData";
import AiLeagueTeaser from "@/components/AiLeagueTeaser";

/** 案11: 編成C「リズム重視」 — 大(ヒーロー)→小(ことば)→中(棚)→小(豆知識)→… と
 *  コーナーの大小を交互に置いて縦読みのテンポを作る。 新パーツ: ことばカード/ジャンルルーレット/数字トリビア */
export default function Design11() {
  const { data, manga, byNew, completedClassics } = bundle();
  const genreList = data.genres.map((g: { key: string; name: string }) => ({ key: g.key, name: g.name }));
  // AI書評家リーグ: 週次順出しに合わせslim情報を全節渡す(選定はclient=AiLeagueTeaser)
  const aiSections = loadAiReviews().map((x) => ({ setsu: x.setsu, title: x.title, models: x.reviews.map((r) => r.model) }));
  const daySalt = Number(new Date().toISOString().slice(0, 10).replace(/-/g, ""));
  // ★今週の一冊 = 完結の名作上位から週(=ビルド)替わり(固定だった bug 修正)
  const hero = seeded(completedClassics.slice(0, 40), (m) => m.slug, 1, daySalt + 70)[0] ?? completedClassics[0];

  // 新パーツ: ことばカード = あらすじから今日の一文(synopsis 冒頭文を日替わり)
  const withSyn = manga.filter((m) => m.synopsis && m.synopsis.length > 40);
  const kotoba = seeded(withSyn, (m) => m.slug, 1, daySalt + 11)[0];
  // ジャンルルーレット: ★master(data.genres)から選び key でリンク(旧=日本語ラベルを
  //   ?genre= に投げて 0件 になる bug を修正)。 表示は name、 リンクは key。
  const todayGenreObj = data.genres.length
    ? data.genres[daySalt % data.genres.length]
    : { key: "action", name: "アクション" };
  // 数字トリビア: ★日替わり(固定だった bug 修正。 複数 fact を daySalt で回す)
  const longest = [...manga].sort((a, b) => volCount(b) - volCount(a))[0];
  const totalBooks = manga.reduce((s, m) => s + m.editions.reduce((x, e) => x + e.volumes.length, 0), 0);
  const oldest = [...manga].filter((m) => m.year_started).sort((a, b) => a.year_started - b.year_started)[0];
  const trivia = [
    longest && `収録最長は『${longest.title}』の 全${volCount(longest)}巻。1日1冊でも読破に${Math.ceil(volCount(longest) / 30)}ヶ月。`,
    `登録は ${manga.length.toLocaleString()} 作品、漫画本は合計 ${totalBooks.toLocaleString()} 冊。`,
    oldest && `最も古い収録作は『${oldest.title}』(${oldest.year_started}年〜)。`,
  ].filter(Boolean) as string[];
  const todayTrivia = trivia[daySalt % trivia.length];

  const Tile = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
    <div className={`rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] shadow-sm ${className}`}>{children}</div>
  );

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-12">
      <DesignNav current={11} />
      {/* ★PCレイアウト(2026-07-06): lg+=左サイドバー(検索常駐)+640pxコンテンツ列の2カラム。
          モバイル=従来の1カラム(サイドバー非表示)。 */}
      <div className="mx-auto flex w-full max-w-[960px] justify-center gap-6 lg:px-4">
      <HomeSidebar genres={genreList} />
      <div className="w-full max-w-[640px] min-w-0">

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
            <S href="/browse" label="作品" n={manga.length} />
            <span className="text-ink/25">|</span>
            <S href="/browse" label="漫画本" n={books} />
            <span className="text-ink/25">|</span>
            <S href="/browse?status=ongoing" label="連載中" n={ongoing} />
            <span className="text-ink/25">|</span>
            <S href="/browse?status=completed" label="完結" n={done} />
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
      <FeaturedDaily slot={0} />

      {/* 2.7【新・自動】周年: 今日で連載開始N年(anniversaries.json週次再生成) */}
      <AnniversaryDaily />

      {/* 3.【中】新刊棚(★題=1行オートスクロール+下に作者。はみ出す題だけ動く) */}
      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <h2 className="text-[14px] font-bold">📦 今月の新刊</h2>
          <ul className="-mx-3.5 mt-2.5 flex gap-3 overflow-x-auto px-3.5 pb-1 snap-x">
            {thisMonthReleases(manga, byNew, 12).map((m) => (
              <li key={m.slug} className="w-[96px] shrink-0 snap-start">
                <Link href={`/manga/${m.slug}`} className="block group spring-press">
                  <Cover m={m} sizes="96px" />
                  <MarqueeTitle text={m.title} className="mt-1 text-[12px] leading-snug text-ink/85 group-hover:text-[var(--color-accent)]" />
                  <p className="truncate text-[10px] text-ink/50">{(m.authors ?? []).map((a) => a.name).join("・")}</p>
                </Link>
              </li>
            ))}
          </ul>
        </Tile>
      </section>

      {/* 3.5【中】発売/創刊カレンダー(2ビュー・データ駆動 = public/calendar を遅延fetch・index join) */}
      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <div className="mb-1 flex items-baseline justify-between">
            <h2 className="text-[14px] font-extrabold">📅 カレンダー</h2>
            <span className="text-[10px] text-ink/45">今月〜3ヶ月先+未定</span>
          </div>
          <CalendarView />
        </Tile>
      </section>

      {/* 3.6【新・自動】タイムマシン: N年前の今日発売(全期間カレンダー流用) */}
      <TimeMachine />

      {/* 3.7【新・自動】豪華版: 特装・限定版の週替わりshowcase(価格表示禁止) */}
      <DeluxeWeekly />

      {/* 4.【小・新】数字トリビア */}
      {todayTrivia && (
        <section className="mt-4 px-4">
          <div className="flex items-center gap-3 rounded-xl border border-dashed border-[var(--color-line)] bg-[var(--color-surface-2)]/60 px-4 py-3">
            <span className="text-2xl">🔢</span>
            <p className="text-[12px] leading-relaxed text-ink/75">
              <b>きょうの数字:</b> {todayTrivia}
            </p>
          </div>
        </section>
      )}

      {/* 5.【今日の一冊 slot1】日替わり分散(散開日の2人目/1+2の2冊側) */}
      <FeaturedDaily slot={1} />

      {/* 6.【小・新】ジャンルルーレット */}
      <section className="mt-4 px-4">
        <Link href={`/browse?genre=${encodeURIComponent(todayGenreObj.key)}`} className="block rounded-xl bg-gradient-to-r from-[var(--color-accent)] to-[var(--color-accent)]/80 px-4 py-3.5 text-white shadow-md spring-press">
          <p className="text-[13px] font-bold leading-snug">🎡 今日のジャンルルーレット: <span className="text-[16px] whitespace-nowrap">{todayGenreObj.name}</span></p>
          <p className="mt-0.5 text-right text-[11px] opacity-85">回ったジャンルの棚へ →</p>
        </Link>
      </section>

      {/* 6.5【今日の一冊 slot2】日替わり分散(バラバラ日の3人目/2+1の1冊側) */}
      <FeaturedDaily slot={2} />

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

      {/* 7.3【深・新】AI書評家リーグ(週刊・完結作・ネタバレなし。AIを名前ごと前面に=ユーザ発案) */}
      <section className="mt-4 px-4">
        <Link href="/column-ai-league" className="spring-press block">
          <Tile className="overflow-hidden">
            <AiLeagueTeaser sections={aiSections} />
          </Tile>
        </Link>
      </section>

      {/* 7.5【三世代 slot C】ペア or 散開時の3人目 */}

      {/* 8.【小】運命の一冊(★ガチャ化: ↻で再抽選・確率演出。候補プール埋込=通信ゼロ) */}
      <section className="mt-4 px-4">
        <Tile>
          <DestinyPickMock
            items={seeded(manga, (m) => m.slug, 60, daySalt).map((m) => ({
              slug: m.slug,
              title: m.title,
              authors: (m.authors ?? []).map((a) => a.name).join("・"),
              vols: volCount(m),
              cover: coverUrl(m),
            }))}
            initialIndex={daySalt % 60}
            total={manga.length}
          />
        </Tile>
      </section>
      <section className="mt-5 px-4">
        <div className="grid grid-cols-2 gap-2.5">
          {([
            ["📋 一覧表で探す", "全作品をソート・絞り込み", "/list"],
            ["🏷️ ジャンルから", "グリッド検索へ", "/browse"],
            ["あ 50音さくいん", "題名・著者名から", "/browse"],
            ["📚 あなたの本棚", "所持巻を記録(準備中)", null],
          ] as const).map(([t, d, href]) =>
            href ? (
              <Link key={t} href={href} className="spring-press block">
                <Tile className="p-3"><p className="text-[13px] font-bold text-ink/85">{t}</p><p className="mt-0.5 text-[10.5px] text-ink/50">{d}</p></Tile>
              </Link>
            ) : (
              <Tile key={t} className="p-3 opacity-70"><p className="text-[13px] font-bold text-ink/85">{t}</p><p className="mt-0.5 text-[10.5px] text-ink/50">{d}</p></Tile>
            ),
          )}
        </div>
      </section>
      </div>
      </div>
    </div>
  );
}
