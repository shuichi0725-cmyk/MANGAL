import Link from "next/link";
import { bundle, DesignNav, volCount } from "@/lib/homeDesign";

export const metadata = { robots: { index: false, follow: false } };  // 実験頁=非索引

/** 案4: 図書館型 — 索引が主役。50音・ジャンル・年代の静かな目録(serif基調) */
export default function Design04() {
  const { manga } = bundle();
  const rows = "あかさたなはまやらわ".split("");
  const byKana = (r: string) => {
    const head: Record<string, string> = { あ: "アイウエオ", か: "カキクケコガギグゲゴ", さ: "サシスセソザジズゼゾ", た: "タチツテトダヂヅデド", な: "ナニヌネノ", は: "ハヒフヘホバビブベボパピプペポ", ま: "マミムメモ", や: "ヤユヨ", ら: "ラリルレロ", わ: "ワヲン" };
    return manga.filter((m) => m.title_kana && head[r]?.includes(m.title_kana[0])).length;
  };
  const recent = [...manga].sort((a, b) => (b.year_started ?? 0) - (a.year_started ?? 0)).slice(0, 8);
  return (
    <div className="min-h-screen bg-[#f7f4ec] pb-12" style={{ fontFamily: "'Noto Serif JP', serif" }}>
      <DesignNav current={4} />
      <header className="px-5 pb-6 pt-8 text-center">
        <h1 className="text-2xl font-bold tracking-[0.3em] text-[#3a3226]">MANGAL 書庫</h1>
        <p className="mt-2 text-[12px] tracking-widest text-[#3a3226]/60">— 日本の漫画、{manga.length.toLocaleString()}冊の目録 —</p>
        <div className="mx-auto mt-4 h-px w-24 bg-[#3a3226]/30" />
      </header>
      <section className="px-5">
        <h2 className="text-sm font-bold tracking-widest text-[#3a3226]/80">五十音から引く</h2>
        <div className="mt-3 grid grid-cols-5 gap-2">
          {rows.map((r) => (
            <Link key={r} href={`/?kana=${r}`} className="rounded border border-[#3a3226]/20 bg-white/70 py-3 text-center shadow-sm active:bg-[#3a3226]/5">
              <span className="text-lg font-bold text-[#3a3226]">{r}</span>
              <span className="block text-[10px] text-[#3a3226]/50">{byKana(r)}冊</span>
            </Link>
          ))}
        </div>
      </section>
      <section className="mt-8 px-5">
        <h2 className="text-sm font-bold tracking-widest text-[#3a3226]/80">主題から引く</h2>
        <div className="mt-3 flex flex-wrap gap-x-1 gap-y-2 text-[13px] leading-relaxed">
          {["スポーツ", "野球", "サッカー", "ファンタジー", "SF", "ミステリー", "ホラー", "恋愛", "歴史", "料理", "音楽", "医療", "日常", "戦記"].map((g, i) => (
            <span key={g}>
              <Link href={`/?genre=${g}`} className="text-[#1f4e79] underline decoration-[#1f4e79]/30 underline-offset-4">{g}</Link>
              {i < 13 && <span className="text-[#3a3226]/30"> ・ </span>}
            </span>
          ))}
        </div>
      </section>
      <section className="mt-8 px-5">
        <h2 className="text-sm font-bold tracking-widest text-[#3a3226]/80">新着の受け入れ</h2>
        <ul className="mt-3 divide-y divide-[#3a3226]/10 border-y border-[#3a3226]/15 bg-white/50">
          {recent.map((m) => (
            <li key={m.slug}>
              <Link href={`/manga/${m.slug}`} className="flex items-baseline gap-3 px-3 py-2.5">
                <span className="text-[11px] tabular-nums text-[#3a3226]/45">{m.year_started}</span>
                <span className="min-w-0 flex-1 truncate text-[14px] text-[#3a3226]">{m.title}</span>
                <span className="text-[11px] text-[#3a3226]/50">全{volCount(m)}巻</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
      <p className="mt-10 text-center text-[11px] tracking-widest text-[#3a3226]/40">どうぞ、ごゆっくり。</p>
    </div>
  );
}
