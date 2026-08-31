"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useMangaIndex } from "@/lib/useMangaIndex";
import { dotGothic } from "@/lib/fonts";
import { amazonDpUrlFromIsbn13, amazonSearchUrl } from "@/lib/amazon";

/** 今月の新刊・全冊一覧 (2026-08-25 ユーザ改修指示で1行リスト型へ):
 *  - 漫画ごとに1行: 書影+題(→Amazon)+巻数+著者+出版社・レーベル+「詳細」(→自サイト作品頁)
 *  - 横スクロール/展開ボタン無し=上下スクロールだけで月の全冊
 *  - 月はURLに持つ(/shinkan?m=2026-07)。2025-01まで遡り可・未来は+2ヶ月
 *    (2026-08-31 ユーザ要望: 月タブが増え指定しにくい→年チップ+月チップの2段ナビへ)
 *  - 共有ボタンは月に1つ(ヘッダー)。Web Share API→X intent fallback
 *  - データ: /shinkan/{ym}.json ([slug,vol,title,cover,isbn13,authors,publisher,imprint])
 *  - 死リンク防止: 「詳細」リンクは一覧索引に居る作品のみ(preview=subsetでも安全) */
type Item = [string, number | null, string, string | null, string | null, string, string, string];
type MonthData = { days: Record<string, Item[]>; unknown: Item[] };

const WEEK = ["日", "月", "火", "水", "木", "金", "土"];
const FLOOR = "2025-01";
const AMZ_TAG = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";

function jstYm(offset = 0): string {
  const t = new Date(Date.now() + 9 * 3600 * 1000);
  const m = t.getUTCMonth() + offset;
  const y = t.getUTCFullYear() + Math.floor(m / 12);
  return `${y}-${String(((m % 12) + 12) % 12 + 1).padStart(2, "0")}`;
}

function yearRange(): number[] {
  // FLOOR(2025-01)の年〜(当月+2)の年
  const out: number[] = [];
  for (let y = Number(FLOOR.slice(0, 4)); y <= Number(jstYm(2).slice(0, 4)); y++) out.push(y);
  return out;
}

function monthsOfYear(year: number): string[] {
  // その年のうち FLOOR〜当月+2 に収まる月だけ(YYYY-MM は文字列比較で正しく順序づく)
  const end = jstYm(2);
  const out: string[] = [];
  for (let m = 1; m <= 12; m++) {
    const ym = `${year}-${String(m).padStart(2, "0")}`;
    if (ym >= FLOOR && ym <= end) out.push(ym);
  }
  return out;
}

function weekday(ym: string, day: string): string {
  return WEEK[new Date(`${ym}-${day.padStart(2, "0")}T12:00:00+09:00`).getUTCDay()];
}

function jstDay(): number {
  return new Date(Date.now() + 9 * 3600 * 1000).getUTCDate();
}

/** 高速スムーススクロール(既定のsmoothは長距離で遅い→~8px/msの短時間アニメ。ユーザ要望「高速スクロールする感じ」) */
function fastScrollTo(el: HTMLElement) {
  const target = el.getBoundingClientRect().top + window.scrollY;
  const start = window.scrollY;
  const dist = target - start;
  const dur = Math.min(900, Math.max(300, Math.abs(dist) / 8));
  const t0 = performance.now();
  const ease = (t: number) => 1 - Math.pow(1 - t, 3);
  const step = (now: number) => {
    const p = Math.min(1, (now - t0) / dur);
    window.scrollTo(0, start + dist * ease(p));
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

export default function ShinkanClient() {
  const [ym, setYmState] = useState(jstYm());
  const [data, setData] = useState<Record<string, MonthData | null>>({});
  const index = useMangaIndex();
  const known = useMemo(() => new Set((index ?? []).map((it) => it.slug)), [index]);

  const [goToday, setGoToday] = useState(false);

  // ★月はURLで共有可能に(?m=YYYY-MM)。初回=URLから復元、切替=replaceState
  useEffect(() => {
    try {
      const sp = new URLSearchParams(location.search);
      const m = sp.get("m");
      if (m && /^\d{4}-\d{2}$/.test(m)) setYmState(m);
      // ★?go=today = ホーム「全部見る」からの遷移: 今日の日付へ高速スクロール(2026-08-27 ユーザ要望)
      if (sp.get("go") === "today") setGoToday(true);
    } catch {}
  }, []);
  const setYm = (m: string) => {
    setYmState(m);
    try { history.replaceState(null, "", `/shinkan?m=${m}`); } catch {}
  };
  // ★年チップ: 同じ月番号を保って年だけ替える(その年に無い月なら端へ寄せる)
  const curYear = Number(ym.slice(0, 4));
  const setYear = (y: number) => {
    if (y === curYear) return;
    const ms = monthsOfYear(y);
    if (!ms.length) return;
    const want = `${y}-${ym.slice(5)}`;
    setYm(ms.includes(want) ? want : y < curYear ? ms[ms.length - 1] : ms[0]);
  };

  useEffect(() => {
    if (data[ym] !== undefined) return;
    fetch(`/shinkan/${ym}.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setData((p) => ({ ...p, [ym]: d })))
      .catch(() => setData((p) => ({ ...p, [ym]: null })));
  }, [ym, data]);

  const month = data[ym];
  const days = month ? Object.keys(month.days).sort((a, b) => Number(a) - Number(b)) : [];
  const total = month ? days.reduce((s, d) => s + month.days[d].length, 0) + (month.unknown?.length ?? 0) : 0;
  const monthLabel = `${ym.slice(0, 4)}年${Number(ym.slice(5))}月`;

  // ★go=today: 当月データ描画後に「今日(無ければ直近の前の発売日)」のセクションへ高速スクロール
  useEffect(() => {
    if (!goToday || !month || ym !== jstYm()) return;
    const today = jstDay();
    const nums = days.map(Number);
    const target = [...nums].reverse().find((n) => n <= today) ?? nums[0];
    if (target == null) return;
    setGoToday(false);
    requestAnimationFrame(() => {
      const el = document.getElementById(`day-${target}`);
      if (el) fastScrollTo(el);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [goToday, month, ym]);

  const scrollToDay = (d: string) => {
    const el = document.getElementById(`day-${Number(d)}`);
    if (el) fastScrollTo(el);
  };

  const share = () => {
    const url = `https://mangal-db.com/shinkan?m=${ym}`;
    const text = `${monthLabel}の漫画新刊 ${total.toLocaleString()}冊一覧 | MANGAL`;
    if (typeof navigator !== "undefined" && navigator.share) {
      navigator.share({ title: text, url }).catch(() => {});
    } else {
      window.open(`https://x.com/intent/post?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`, "_blank");
    }
  };

  const Row = ({ it }: { it: Item }) => {
    const [slug, vol, title, cover, isbn, authors, publisher, imprint] = it;
    const amz = (isbn && amazonDpUrlFromIsbn13(isbn, AMZ_TAG)) ||
      amazonSearchUrl(`${title} ${vol ?? ""}`.trim(), AMZ_TAG);
    // 表示150px高に合わせ楽天サムネイルを300x300へ格上げ(120/200のままだとぼやける)
    const coverHi = cover ? cover.replace(/_ex=(120x120|200x200)/, "_ex=300x300") : null;
    return (
      <div className="flex items-start gap-3 border-b border-[#1d1d1d] px-3 py-2">
        {/* 書影+題 → Amazon(参考サイト同型・アフィ。サイズも参考サイトの_SL160_相当=約105×150) */}
        <a href={amz} target="_blank" rel="nofollow sponsored noopener" className="spring-press flex min-w-0 flex-1 items-start gap-3" title={`${title} をAmazonで見る`}>
          <span className="relative block h-[150px] w-[105px] shrink-0 overflow-hidden bg-[#1a1a1a]">
            {coverHi ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={coverHi} alt={title} loading="lazy" className="h-full w-full object-cover" />
            ) : (
              <span className="flex h-full w-full items-center justify-center text-[10px] font-bold text-ink/40">NO IMG</span>
            )}
          </span>
          <span className="min-w-0">
            <span className="block text-[14px] font-bold leading-snug">
              {title}
              {vol ? <span className="ml-1 bg-[var(--color-accent)] px-1 text-[9.5px] font-black text-[#0d0d0d] align-[1px]">{vol}巻</span> : null}
              {vol === 1 ? <span className="ml-1 border border-[var(--color-accent)] px-1 text-[9px] font-black text-[var(--color-accent)] align-[1px]">新刊1巻</span> : null}
            </span>
            {/* ★2026-08-27 ユーザ要望: 作者(複数でも1行)/会社/レーベル を1行ずつ */}
            {authors ? <span className="mt-1 block truncate text-[11.5px] leading-snug text-ink/60">{authors}</span> : null}
            {publisher ? <span className="mt-0.5 block truncate text-[10.5px] leading-snug text-ink/45">{publisher}</span> : null}
            {imprint ? <span className="mt-0.5 block truncate text-[10.5px] leading-snug text-ink/45">{imprint}</span> : null}
          </span>
        </a>
        {known.has(slug) && (
          <Link href={`/manga/${slug}`} className="spring-press shrink-0 border border-[var(--color-line)] px-1.5 py-0.5 text-[10px] font-bold text-ink/65">
            詳細
          </Link>
        )}
      </div>
    );
  };

  return (
    <div className="mx-auto w-full max-w-[720px] pb-12">
      <div className="border-b-[3px] border-[var(--color-accent)] px-4 py-3">
        <div className="flex items-center gap-2">
          <h1 className={`${dotGothic.className} text-[22px] font-black`}>
            📦 {monthLabel}の新刊
          </h1>
          {total > 0 && (
            <span className="border border-[var(--color-line)] px-2 py-0.5 text-[12px] font-black text-ink/75">
              全{total.toLocaleString()}冊
            </span>
          )}
          <button onClick={share} aria-label="この月を共有"
            className="spring-press ml-auto border-2 border-[var(--color-accent)] px-2.5 py-1 text-[11px] font-black text-[var(--color-accent)]">
            共有
          </button>
        </div>
        <p className="mt-0.5 text-[11px] text-ink/55">
          発売日ごとに全冊掲載。スクロールだけで全部見られます。書影・題はAmazonへ、「詳細」で作品ページへ。
        </p>
        {/* ★年×月の2段ナビ(2026-08-31): 年を選ぶ→その年の月チップ。月が増えても指定しやすい */}
        <div className="mt-2 flex gap-1.5 overflow-x-auto pb-0.5">
          {yearRange().map((y) => (
            <button key={y} onClick={() => setYear(y)}
              className={`shrink-0 px-2.5 py-1 text-[11.5px] font-black ${y === curYear ? "bg-[var(--color-accent)] text-[#0d0d0d]" : "border border-[var(--color-line)] text-ink/70"}`}>
              {y}年
            </button>
          ))}
        </div>
        <div className="mt-1.5 flex gap-1.5 overflow-x-auto pb-0.5">
          {monthsOfYear(curYear).map((t) => (
            <button key={t} onClick={() => setYm(t)}
              className={`shrink-0 px-2.5 py-1 text-[11.5px] font-black ${t === ym ? "bg-[var(--color-accent)] text-[#0d0d0d]" : "border border-[var(--color-line)] text-ink/70"}`}>
              {Number(t.slice(5))}月
            </button>
          ))}
        </div>
      </div>

      {month === undefined ? (
        <p className="p-6 text-[12px] text-ink/50">読み込み中…</p>
      ) : month === null ? (
        <p className="p-6 text-[12px] text-ink/50">この月のデータはまだありません。</p>
      ) : (
        <>
          {days.map((d, di) => (
            <section key={d} id={`day-${Number(d)}`}>
              <div className="sticky top-0 z-10 flex items-center gap-2 border-b-2 border-[var(--color-accent)] bg-[color-mix(in_srgb,var(--color-bg)_92%,transparent)] px-3.5 pb-1.5 pt-2 backdrop-blur-[2px]">
                <span className={`${dotGothic.className} text-[19px] font-black leading-none text-[var(--color-accent)]`}>
                  {Number(ym.slice(5))}/{d.padStart(2, "0")}
                </span>
                <span className="text-[11px] text-ink/55">({weekday(ym, d)})</span>
                {/* ★日送りボタン(2026-08-27 ユーザ要望: 日付と冊数の間に前の日/次の日) */}
                <span className="mx-auto flex items-center gap-1.5">
                  {di > 0 && (
                    <button onClick={() => scrollToDay(days[di - 1])}
                      className="spring-press border border-[var(--color-line)] px-2 py-0.5 text-[10.5px] font-bold text-ink/65">
                      ↑前の日
                    </button>
                  )}
                  {di < days.length - 1 && (
                    <button onClick={() => scrollToDay(days[di + 1])}
                      className="spring-press border border-[var(--color-line)] px-2 py-0.5 text-[10.5px] font-bold text-ink/65">
                      ↓次の日
                    </button>
                  )}
                </span>
                <span className="text-[11px] text-ink/45">{month.days[d].length}冊</span>
              </div>
              {month.days[d].map((it, i) => (
                <Row key={`${it[0]}-${i}`} it={it} />
              ))}
            </section>
          ))}
          {month.unknown?.length > 0 && (
            <section>
              <div className="sticky top-0 z-10 flex items-baseline gap-2 border-b-2 border-[var(--color-accent)] bg-[color-mix(in_srgb,var(--color-bg)_92%,transparent)] px-3.5 pb-1.5 pt-2 backdrop-blur-[2px]">
                <span className={`${dotGothic.className} text-[15px] font-black text-[var(--color-accent)]`}>日付未定</span>
                <span className="ml-auto text-[11px] text-ink/45">{month.unknown.length}冊</span>
              </div>
              {month.unknown.map((it, i) => (
                <Row key={`u-${it[0]}-${i}`} it={it} />
              ))}
            </section>
          )}
          <p className="px-4 pt-3 text-[10px] text-ink/40">[PR] Amazonリンクにはアフィリエイト広告を含みます</p>
        </>
      )}
    </div>
  );
}
