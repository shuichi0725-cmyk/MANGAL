import Link from "next/link";
import { bundle, DesignNav, latestDate, volCount } from "@/lib/homeDesign";

/** 案6: テキスト表型 — スプレッドシートが主役の尖り案(他サイトに無い密度=差別化) */
export default function Design06() {
  const { manga } = bundle();
  const rows = [...manga].sort((a, b) => (a.title_kana || "").localeCompare(b.title_kana || "", "ja"));
  return (
    <div className="min-h-screen bg-white pb-10">
      <DesignNav current={6} />
      <header className="flex items-baseline justify-between border-b-2 border-ink px-3 py-3">
        <h1 className="text-base font-extrabold">MANGAL<span className="text-[var(--color-accent)]">.</span> 一覧表</h1>
        <span className="text-[11px] text-ink/55">{manga.length.toLocaleString()}件 ・ 列タップで並べ替え</span>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse text-[12px]">
          <thead className="sticky top-[41px] bg-[var(--color-surface-2)] text-left text-[11px] text-ink/65">
            <tr className="[&>th]:border-b [&>th]:border-[var(--color-line)] [&>th]:px-2 [&>th]:py-2">
              <th className="cursor-pointer">題名 <span className="text-ink/35">▲</span></th>
              <th className="cursor-pointer">著者</th>
              <th className="cursor-pointer w-12 text-right">巻</th>
              <th className="cursor-pointer w-14 text-right">開始</th>
              <th className="cursor-pointer w-12">状態</th>
              <th className="cursor-pointer w-20 text-right">最新刊</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 60).map((m, i) => (
              <tr key={m.slug} className={i % 2 ? "bg-[var(--color-surface)]/60" : ""}>
                <td className="max-w-[200px] border-b border-[var(--color-line)]/60 px-2 py-1.5">
                  <Link href={`/manga/${m.slug}`} className="block truncate font-medium text-[#1f4e79] underline-offset-2 active:underline">
                    {m.title}
                  </Link>
                </td>
                <td className="max-w-[120px] truncate border-b border-[var(--color-line)]/60 px-2 py-1.5 text-ink/75">
                  {(m.authors ?? []).map((a) => a.name).join("・")}
                </td>
                <td className="border-b border-[var(--color-line)]/60 px-2 py-1.5 text-right tabular-nums">{volCount(m)}</td>
                <td className="border-b border-[var(--color-line)]/60 px-2 py-1.5 text-right tabular-nums text-ink/70">{m.year_started ?? "—"}</td>
                <td className="border-b border-[var(--color-line)]/60 px-2 py-1.5">
                  {m.status === "completed" ? (
                    <span className="text-ink/60">完結</span>
                  ) : (
                    <span className="font-semibold text-emerald-700">連載</span>
                  )}
                </td>
                <td className="border-b border-[var(--color-line)]/60 px-2 py-1.5 text-right tabular-nums text-ink/60">
                  {latestDate(m)?.slice(0, 7) ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="px-3 py-3 text-[11px] text-ink/50">
        ※ 横スクロールで全列。実装時は列ソート・フィルター・無限スクロール対応。グリッド表示とはタブで切替。
      </p>
    </div>
  );
}
