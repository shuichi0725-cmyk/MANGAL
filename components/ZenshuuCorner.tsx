import Link from "next/link";
import view from "@/data/zenshuu-view.json";
import CoverImage from "./CoverImage";
import type { ZenshuuView } from "@/lib/zenshuu";

const V = (view as unknown as ZenshuuView).collections;

/** 📚 全集コーナー(トップ用・A-1案 2026-07-19)。
 *  全集を一覧ページ無しでその場で選ぶ=カード横スクロール(アニメ化コーナーと同型)。
 *  データ=data/zenshuu-view.json(_gen-zenshuu-data.py で再生成)。 */
export default function ZenshuuCorner() {
  if (V.length === 0) return null;
  return (
    <section className="mt-6">
      <div className="flex items-baseline gap-2 px-3.5">
        <span className="rounded bg-[var(--color-accent)] px-1.5 py-0.5 text-[10px] font-bold tracking-wider text-white">全集</span>
        <h2 className="text-[16px] font-black">📚 作家の全仕事、まるごと</h2>
      </div>
      <p className="px-3.5 pt-0.5 text-[10.5px] text-ink/55">巨匠の全集を一棚に。タップでその全集の全巻へ。</p>
      <ul className="-mx-3.5 mt-2.5 flex gap-3 overflow-x-auto no-scrollbar px-7 pb-1 snap-x scroll-pl-3.5">
        {V.map((c) => (
          <li key={c.key} className="w-[132px] shrink-0 snap-start">
            <Link href={`/zenshuu/${c.key}`} className="block group spring-press rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-2.5">
              <div className="relative mb-2 h-[88px]">
                {c.covers.slice(0, 3).map((u, i) =>
                  u ? (
                    <div
                      key={i}
                      className="absolute h-[78px] w-[56px] overflow-hidden rounded border border-black/10 bg-[var(--color-surface-2)] shadow"
                      style={{ left: i * 26 + 2, top: [6, 2, 7][i], transform: `rotate(${[-4, 3, 8][i]}deg)`, zIndex: i + 1 }}
                    >
                      <CoverImage src={u} alt={c.name} sizes="56px" size="card" />
                    </div>
                  ) : null,
                )}
              </div>
              <p className="min-h-[29px] text-[11px] font-extrabold leading-[1.3] group-hover:text-[var(--color-accent)]">{c.name}</p>
              <p className="mb-1 mt-0.5 text-[9.5px] text-ink/50">
                {c.publisher}・全{c.total}巻{c.guinness ? " 🏆" : ""}
              </p>
              {c.complete ? (
                <span className="inline-flex rounded-full border border-[#b9d8c1] bg-[#e8f3ea] px-2 py-0.5 text-[9.5px] font-bold text-[#256b3a]">✓ 全巻そろってます</span>
              ) : c.axis === "sets" ? (
                <span className="inline-flex rounded-full border border-[#ecd3ab] bg-[#fdf1e3] px-2 py-0.5 text-[9.5px] font-bold text-[#9a6414]">期セット全12期</span>
              ) : (
                <span className="inline-flex rounded-full border border-[#ecd3ab] bg-[#fdf1e3] px-2 py-0.5 text-[9.5px] font-bold text-[#9a6414]">{c.linked}巻〜 収録中</span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
