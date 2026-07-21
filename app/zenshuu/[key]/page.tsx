import Link from "next/link";
import { notFound } from "next/navigation";
import view from "@/data/zenshuu-view.json";
import CoverImage from "@/components/CoverImage";
import type { ZenshuuView, ZenshuuCollection, ZenshuuWork } from "@/lib/zenshuu";

const V = (view as unknown as ZenshuuView).collections;

/** 全集の中身ページ(C6=表紙壁+作品ジャンプ。2026-07-19 A-1コーナーとセットで新設)。
 *  コーナーから直接ここへ(一覧ページ無し)。 石ノ森=期セット型の特別レイアウト。 */
export function generateStaticParams() {
  return V.map((c) => ({ key: c.key }));
}

export async function generateMetadata({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const c = V.find((x) => x.key === key);
  return {
    title: c ? `${c.name}(全${c.total}巻) | MANGAL` : "全集 | MANGAL",
    alternates: { canonical: `/zenshuu/${key}` },
  };
}

function Band({ c }: { c: ZenshuuCollection }) {
  const done = c.axis === "sets" ? null : c.complete;
  return (
    <div className={`mx-3.5 mb-3 rounded-xl p-3.5 text-white ${c.axis === "sets" ? "bg-gradient-to-br from-[#26436b] to-[#122238]" : "bg-gradient-to-br from-[#2c5138] to-[#16311f]"}`}>
      <h1 className="text-[15px] font-black">{c.name}</h1>
      <p className="mt-1 text-[10.5px] leading-relaxed opacity-85">
        {c.publisher}・{c.years}・全{c.total}巻{c.axis === "sets" ? "・770作品(全12期の予約購読直販)" : ""}
      </p>
      {done !== null && (
        <div className="mt-2 flex items-center gap-2 text-[10px]">
          <span>{done ? "✓ 完備" : "作品ページ連携"}</span>
          <div className="h-[5px] flex-1 overflow-hidden rounded-full bg-white/25">
            <i className="block h-full rounded-full bg-[#ffd76a]" style={{ width: `${Math.min(100, Math.round(((c.linked || 0) / c.total) * 100))}%` }} />
          </div>
          <span>{done ? `${c.total}/${c.total}` : `${c.linked}/${c.total}`}</span>
        </div>
      )}
    </div>
  );
}

function VolCell({ v }: { v: ZenshuuWork["vols"][number] }) {
  const body = (
    <div className={`relative aspect-[5/7] w-full overflow-hidden rounded border border-[var(--color-line)] bg-[var(--color-surface-2)] ${v.nm ? "opacity-75" : ""}`}>
      {v.c ? (
        <CoverImage src={v.c} alt={v.t} sizes="80px" size="card" />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center p-1.5 text-center text-[9px] leading-tight text-ink/50">{v.t.slice(0, 24)}</div>
      )}
      {v.c && (
        <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 to-transparent px-1 pb-0.5 pt-3 text-[8.5px] leading-tight text-white">{v.t.slice(0, 20)}</span>
      )}
      {v.n ? <span className="absolute right-1 top-0.5 rounded bg-black/45 px-1 text-[8px] font-bold text-white">{String(v.n).padStart(3, "0")}</span> : null}
    </div>
  );
  return v.s ? (
    <Link href={`/manga/${v.s}${v.n ? `#v${v.n}` : ""}`} className="block spring-press">{body}</Link>
  ) : (
    <div title="単独ページ未収載">{body}</div>
  );
}

export default async function ZenshuuPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const c = V.find((x) => x.key === key);
  if (!c) notFound();

  return (
    <main className="pb-16 pt-3">
      <nav className="px-3.5 pb-2 text-[10px] text-ink/55">
        <Link href="/">ホーム</Link> › <span>全集</span> › <b className="text-[var(--color-accent)]">{c.name}</b>
      </nav>
      <Band c={c} />

      {c.guinness && (
        <div className="mx-3.5 mb-3 rounded-lg border border-[#e6d9b0] bg-[#fdf8e7] px-3 py-2 text-[10.5px] leading-relaxed">
          🏆 <b className="text-[#8a6d1a]">ギネス世界記録</b>「一人の著者による最多コミック出版」認定(2008年)——この全500巻がその記録。
        </div>
      )}

      {c.axis === "sets" ? (
        <div className="flex flex-col gap-2.5 px-3.5">
          {(c.sets ?? []).map((s) => (
            <section key={s.n} className="overflow-hidden rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)]">
              <div className="flex items-center gap-3 p-3">
                <div className="relative h-[64px] w-[46px] shrink-0 overflow-hidden rounded border border-black/10 bg-[var(--color-surface-2)]">
                  <CoverImage src={s.cover ?? null} alt={s.name} sizes="46px" size="card" />
                </div>
                <div>
                  <h2 className="text-[13px] font-extrabold">{s.name}</h2>
                  <p className="mt-0.5 text-[10px] text-ink/55">{s.date}発売</p>
                </div>
              </div>
              <div className="border-t border-dashed border-[var(--color-line)] px-3 py-2 text-[10.5px] leading-[1.8] text-ink/80">
                {s.lineup ? (
                  <><b>収録: </b>{s.lineup}</>
                ) : (
                  <span className="text-ink/45">収録リストは調査中(当時の直販資料が現存せず)。判明分から順次追記します。</span>
                )}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <>
          {/* ★グループジャンプ(2026-07-21修正): 旧実装はfilter後の連番でhrefを作り、
              飛び先idは全グループ通し番号=単巻が挟まるたびにズレ跳び/無反応(ユーザ報告)。
              元indexを保持して一致させる。24個capも撤廃(後半グループのチップが無かった)。 */}
          <div className="mb-2.5 flex gap-1.5 overflow-x-auto no-scrollbar px-3.5">
            {(c.works ?? [])
              .map((w, i) => ({ w, i }))
              .filter(({ w }) => w.vols.length >= 2)
              .map(({ w, i }) => (
                <a key={i} href={`#w${i}`} className="shrink-0 rounded-full border border-[var(--color-line)] bg-[var(--color-surface)] px-2.5 py-1 text-[10px] font-bold">
                  {w.name.slice(0, 12)}
                </a>
              ))}
          </div>
          {(c.works ?? []).map((w, i) => (
            <section key={i} id={w.vols.length >= 2 ? `w${i}` : undefined} className="mb-3.5 scroll-mt-14">
              <div className="flex items-baseline gap-2 px-3.5 pb-1.5">
                <h2 className="text-[13px] font-bold">{w.name}</h2>
                <span className="text-[10px] text-ink/50">
                  {w.vols.length}冊{w.vols.every((v) => v.nm) ? "・非漫画巻(特例掲載)" : ""}
                </span>
              </div>
              <div className="grid grid-cols-5 gap-1.5 px-3.5">
                {w.vols.map((v, j) => (
                  <VolCell key={j} v={v} />
                ))}
              </div>
            </section>
          ))}
        </>
      )}
    </main>
  );
}
