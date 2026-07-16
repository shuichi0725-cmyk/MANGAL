import Link from "next/link";
import LikeButtonMock from "@/components/LikeButtonMock";
import FeaturedDaily from "@/components/FeaturedDaily";
import AnniversaryDaily from "@/components/AnniversaryDaily";
import DeluxeWeekly from "@/components/DeluxeWeekly";
import TimeMachine from "@/components/TimeMachine";
import DestinyPickMock from "@/components/DestinyPickMock";
import MonthReleasesClient from "@/components/MonthReleasesClient";
import CalendarView from "@/components/CalendarView";
import HomeSidebar from "@/components/HomeSidebar";
import { bundle, DesignNav, seeded, volCount, thisMonthReleases, releaseDayLabel } from "@/lib/homeDesign";
import WeekendFeature from "@/components/WeekendFeature";
import { coverUrl } from "@/lib/schema";
import { loadAiReviews } from "@/lib/loadData";
import AiLeagueTeaser from "@/components/AiLeagueTeaser";
import AnimeSeasonCorner from "@/components/AnimeSeasonCorner";

/** 案11: 編成C「リズム重視」 — 大(ヒーロー)→小(ことば)→中(棚)→小(豆知識)→… と
 *  コーナーの大小を交互に置いて縦読みのテンポを作る。 新パーツ: ことばカード/ジャンルルーレット/数字トリビア */
export default function Design11() {
  const { data, manga, byNew, completedClassics } = bundle();
  const genreList = data.genres.map((g: { key: string; name: string }) => ({ key: g.key, name: g.name }));
  // AI書評家リーグ: 週次順出しに合わせslim情報を全節渡す(選定はclient=AiLeagueTeaser)
  const aiSections = loadAiReviews().map((x) => ({ setsu: x.setsu, title: x.title, models: x.reviews.map((r) => r.model) }));
  const daySalt = Number(new Date().toISOString().slice(0, 10).replace(/-/g, ""));

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
          // ★py均等=行内文字を帯の上下センターに(旧pt-3のみ=下に詰まって見えた 2026-07-16)
          <div className="flex items-center gap-x-3 overflow-x-auto px-4 py-2.5 text-[11px] leading-none">
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

      {/* 1.【大】今季アニメの原作(★2026-07-12 ユーザ裁定: 旧「今週の一冊」ヒーローを廃止し
          アニメコーナーを最上段へ。表示は再読込ごとランダム=client側シャッフル) */}
      <AnimeSeasonCorner />

      {/* 1.5【中】今月の新刊(アニメ直下へ移動 2026-07-12)
          ★2026-07-15: 再読込ごとランダム入替(アニメコーナーと同方式)+リンクは当月巻フォーカス(#v)。
            当月巻の書影を出す(旧=1巻書影で「一年前の本?」と誤読された 2026-07-13) */}
      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <h2 className="text-[14px] font-bold">📦 今月の新刊</h2>
          <MonthReleasesClient
            pool={thisMonthReleases(manga, byNew, 60).map((r) => ({
              slug: r.m.slug,
              title: r.m.title,
              authors: (r.m.authors ?? []).map((a) => a.name).join("・"),
              number: r.number,
              sub: `${r.number ? `${r.number}巻` : "新刊"}${releaseDayLabel(r.date) ? `・${releaseDayLabel(r.date)}` : ""}`,
              cover: r.cover ?? coverUrl(r.m) ?? null,
            }))}
          />
        </Tile>
      </section>

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

      {/* 7.【中】特集(★2026-07-13 改修: 書影あり必須+週替わりrotation。旧=先頭6作固定でのらくろが出続けた) */}
      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <h2 className="border-l-4 border-[var(--color-accent)] pl-2.5 text-[14px] font-extrabold">
            特集: 週末で読み切る、全5巻以内の完結作
            <span className="ml-1.5 text-[10px] font-semibold text-ink/45">週替わり</span>
          </h2>
          <WeekendFeature
            pool={seeded(
              manga.filter((m) => m.status === "completed" && volCount(m) >= 3 && volCount(m) <= 5 && coverUrl(m)),
              (m) => m.slug,
              120,
              42,
            ).map((m) => ({
              slug: m.slug,
              title: m.title,
              authors: (m.authors ?? []).map((a) => a.name).join("・"),
              cover: coverUrl(m)!,
            }))}
          />
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
