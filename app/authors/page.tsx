import Link from "next/link";
import { authorMap } from "@/lib/authors";
import { DesignNav } from "@/lib/homeDesign";

/** 著者50音索引(2026-08-10 preview試作)。著者静的ページへのクロール導線+回遊ハブ。 */

export const metadata = {
  title: "著者一覧(50音順)",
  description: "掲載中の漫画家・原作者を50音順で一覧。著者ページから全作品の巻一覧・発売日情報へ。",
  alternates: { canonical: "https://mangal-db.com/authors" },
};

const GYO: [string, RegExp][] = [
  ["あ", /^[あ-おア-オヴ]/], ["か", /^[か-ごカ-ゴ]/], ["さ", /^[さ-ぞサ-ゾ]/],
  ["た", /^[た-どタ-ド]/], ["な", /^[な-のナ-ノ]/], ["は", /^[は-ぽハ-ポ]/],
  ["ま", /^[ま-もマ-モ]/], ["や", /^[やゆよヤユヨ]/], ["ら", /^[ら-ろラ-ロ]/],
  ["わ", /^[わ-んワ-ン]/],
];

export default function AuthorsIndexPage() {
  const all = [...authorMap().values()];
  const groups = new Map<string, typeof all>();
  for (const [g] of GYO) groups.set(g, []);
  groups.set("英数他", []);
  for (const a of all) {
    const head = (a.kana || a.name).charAt(0);
    const hit = GYO.find(([, re]) => re.test(head));
    groups.get(hit ? hit[0] : "英数他")!.push(a);
  }
  return (
    <div>
      <DesignNav />
      <div className="mx-auto max-w-4xl px-4 py-8">
        <h1 className="text-2xl font-extrabold">著者一覧</h1>
        <p className="mt-1 text-[12.5px] text-ink/60">{all.length.toLocaleString()}名を50音順で掲載。名前から全作品の一覧へ。</p>
        <nav className="mt-4 flex flex-wrap gap-2">
          {[...groups.keys()].map((g) => (
            <a key={g} href={`#g-${g}`} className="rounded-full border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-1 text-[13px] font-bold hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]">
              {g}
            </a>
          ))}
        </nav>
        {[...groups.entries()].map(([g, list]) =>
          list.length ? (
            <section key={g} id={`g-${g}`} className="mt-8">
              <h2 className="text-lg font-bold">{g}</h2>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5">
                {list.map((a) => (
                  <Link key={a.key} href={`/author/${a.key}`} className="text-[13px] hover:text-[var(--color-accent)]">
                    {a.name}
                    <span className="ml-1 text-[10px] text-ink/40">{a.works.length + a.originals.length}</span>
                  </Link>
                ))}
              </div>
            </section>
          ) : null,
        )}
      </div>
    </div>
  );
}
