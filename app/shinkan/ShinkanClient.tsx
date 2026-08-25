"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useMangaIndex } from "@/lib/useMangaIndex";
import { dotGothic } from "@/lib/fonts";
import { amazonDpUrlFromIsbn13, amazonSearchUrl } from "@/lib/amazon";

/** 今月の新刊・全冊一覧 (2026-08-25 ユーザ改修指示で1行リスト型へ):
 *  - 漫画ごとに1行: 書影+題(→Amazon)+巻数+著者+出版社・レーベル+「詳細」(→自サイト作品頁)
 *  - 横スクロール/展開ボタン無し=上下スクロールだけで月の全冊
 *  - 月はURLに持つ(/shinkan?m=2026-07)。2026-06まで遡り可・未来は+2ヶ月
 *  - 共有ボタンは月に1つ(ヘッダー)。Web Share API→X intent fallback
 *  - データ: /shinkan/{ym}.json ([slug,vol,title,cover,isbn13,authors,publisher,imprint])
 *  - 死リンク防止: 「詳細」リンクは一覧索引に居る作品のみ(preview=subsetでも安全) */
type Item = [string, number | null, string, string | null, string | null, string, string, string];
type MonthData = { days: Record<string, Item[]>; unknown: Item[] };

const WEEK = ["日", "月", "火", "水", "木", "金", "土"];
const FLOOR = "2026-06";
const AMZ_TAG = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";

function jstYm(offset = 0): string {
  const t = new Date(Date.now() + 9 * 3600 * 1000);
  const m = t.getUTCMonth() + offset;
  const y = t.getUTCFullYear() + Math.floor(m / 12);
  return `${y}-${String(((m % 12) + 12) % 12 + 1).padStart(2, "0")}`;
}

function monthRange(): string[] {
  // FLOOR(2026-06)〜当月+2
  const out: string[] = [];
  const end = jstYm(2);
  let y = Number(FLOOR.slice(0, 4));
  let m = Number(FLOOR.slice(5));
  for (let i = 0; i < 48; i++) {
    const ym = `${y}-${String(m).padStart(2, "0")}`;
    out.push(ym);
    if (ym === end) break;
    m++;
    if (m > 12) { m = 1; y++; }
  }
  return out;
}

function weekday(ym: string, day: string): string {
  return WEEK[new Date(`${ym}-${day.padStart(2, "0")}T12:00:00+09:00`).getUTCDay()];
}

export default function ShinkanClient() {
  const [ym, setYmState] = useState(jstYm());
  const [data, setData] = useState<Record<string, MonthData | null>>({});
  const index = useMangaIndex();
  const known = useMemo(() => new Set((index ?? []).map((it) => it.slug)), [index]);

  // ★月はURLで共有可能に(?m=YYYY-MM)。初回=URLから復元、切替=replaceState
  useEffect(() => {
    try {
      const m = new URLSearchParams(location.search).get("m");
      if (m && /^\d{4}-\d{2}$/.test(m)) setYmState(m);
    } catch {}
  }, []);
  const setYm = (m: string) => {
    setYmState(m);
    try { history.replaceState(null, "", `/shinkan?m=${m}`); } catch {}
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
    const pubLine = [publisher, imprint].filter(Boolean).join("・");
    return (
      <div className="flex items-center gap-3 border-b border-[#1d1d1d] px-3 py-2">
        {/* 書影+題 → Amazon(参考サイト同型・アフィ。サイズも参考サイトの_SL160_相当=約105×150) */}
        <a href={amz} target="_blank" rel="nofollow sponsored noopener" className="spring-press flex min-w-0 flex-1 items-center gap-3" title={`${title} をAmazonで見る`}>
          <span className="relative block h-[150px] w-[105px] shrink-0 overflow-hidden bg-[#1a1a1a]">
            {coverHi ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={coverHi} alt={title} loading="lazy" className="h-full w-full object-cover" />
            ) : (
              <span className="flex h-full w-full items-center justify-center text-[10px] font-bold text-ink/40">NO IMG</span>
            )}
          </span>
          <span className="min-w-0">
            <span className="line-clamp-2 text-[14px] font-bold leading-snug">
              {title}
              {vol ? <span className="ml-1 bg-[var(--color-accent)] px-1 text-[9.5px] font-black text-[#0d0d0d] align-[1px]">{vol}巻</span> : null}
              {vol === 1 ? <span className="ml-1 border border-[var(--color-accent)] px-1 text-[9px] font-black text-[var(--color-accent)] align-[1px]">新刊1巻</span> : null}
            </span>
            <span className="mt-1 block text-[11.5px] leading-relaxed text-ink/55">
              {authors}
              {authors && pubLine ? <span className="text-ink/30">|</span> : null}
              {pubLine ? <span className="ml-1 text-ink/45">{pubLine}</span> : null}
            </span>
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
        <div className="flex items-center justify-between">
          <h1 className={`${dotGothic.className} text-[22px] font-black`}>
            📦 {monthLabel}の新刊
          </h1>
          <button onClick={share} aria-label="この月を共有"
            className="spring-press border-2 border-[var(--color-accent)] px-2.5 py-1 text-[11px] font-black text-[var(--color-accent)]">
            共有
          </button>
        </div>
        <p className="mt-0.5 text-[11px] text-ink/55">
          発売日ごとに全{total.toLocaleString()}冊。スクロールだけで全部見られます。書影・題はAmazonへ、「詳細」で作品ページへ。
        </p>
        <div className="mt-2 flex gap-1.5 overflow-x-auto pb-0.5">
          {monthRange().map((t) => (
            <button key={t} onClick={() => setYm(t)}
              className={`shrink-0 px-2.5 py-1 text-[11.5px] font-black ${t === ym ? "bg-[var(--color-accent)] text-[#0d0d0d]" : "border border-[var(--color-line)] text-ink/70"}`}>
              {t.slice(0, 4) !== jstYm().slice(0, 4) ? `${t.slice(2, 4)}/${Number(t.slice(5))}` : `${Number(t.slice(5))}月`}
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
          {days.map((d) => (
            <section key={d}>
              <div className="sticky top-0 z-10 flex items-baseline gap-2 border-b-2 border-[var(--color-accent)] bg-[color-mix(in_srgb,var(--color-bg)_92%,transparent)] px-3.5 pb-1.5 pt-2 backdrop-blur-[2px]">
                <span className={`${dotGothic.className} text-[19px] font-black text-[var(--color-accent)]`}>
                  {Number(ym.slice(5))}/{d.padStart(2, "0")}
                </span>
                <span className="text-[11px] text-ink/55">({weekday(ym, d)})</span>
                <span className="ml-auto text-[11px] text-ink/45">{month.days[d].length}冊</span>
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
