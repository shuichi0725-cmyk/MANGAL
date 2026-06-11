import Link from "next/link";
import LikeButtonMock from "@/components/LikeButtonMock";
import { bundle, DesignNav, Cover } from "@/lib/homeDesign";

/** 「三世代、今日の一冊」過去ログ(モック)。 本実装 = seed JSON(date×persona×slug×copy)から
 *  静的生成 = 毎日コンテンツが増えるSEO資産。 ペルソナは増設可能で、 いいね集計が人気指標になる。 */

const PERSONAS = [
  { id: "minato", name: "ミナト", target: "10代・20代", desc: "口語・短文・テンション高め" },
  { id: "saori", name: "サオリ", target: "30代・40代", desc: "落ち着いた書評調" },
  { id: "keizo", name: "圭三", target: "50代以上", desc: "古書店主・回顧長文" },
  { id: "ramen", name: "麺道ヤスコ", target: "グルメ漫画専門", desc: "拡張ペルソナ例: 食漫画だけ語る" },
  { id: "kaigai", name: "Jess", target: "海外ファン目線", desc: "拡張ペルソナ例: 英語圏の人気を語る" },
];

const LOG: Array<{ date: string; persona: string; slug: string; copy: string; likes: number }> = [
  { date: "2026-06-12", persona: "minato", slug: "kimetsu-no-yaiba", copy: "今さら?って言われても推す。鬼滅はマジで1巻の絶望から全部が伏線。週末で完走できるよ🔥", likes: 128 },
  { date: "2026-06-12", persona: "saori", slug: "slam-dunk", copy: "「左手はそえるだけ」を超える最終話を、私はまだ知りません。バスケ漫画ではなく、青春の総量を描いた漫画です。", likes: 211 },
  { date: "2026-06-12", persona: "keizo", slug: "hokuto-no-ken", copy: "昭和五十八年、ジャンプにこれが載った日のことを覚えております。北斗は「強さ」ではなく「哀しみ」の漫画だと、歳を重ねるほどに分かります。", likes: 96 },
  { date: "2026-06-11", persona: "minato", slug: "tokyo-ghoul", copy: "グール側の「正しさ」に途中から飲まれるやつ。カネキの髪が白くなる理由、原作で確かめて。", likes: 87 },
  { date: "2026-06-11", persona: "saori", slug: "yu-yu-hakusho", copy: "仙水編だけでも読み直す価値があります。少年漫画が「正義の限界」を描いた、最初期の到達点。", likes: 154 },
  { date: "2026-06-11", persona: "keizo", slug: "urusei-yatsura", copy: "ラムちゃんに振り回された世代として申し上げますが、高橋留美子の発明は「日常が祭になる」構造そのものでした。", likes: 73 },
  { date: "2026-06-10", persona: "minato", slug: "one-piece", copy: "長い?うん長い。でもアラバスタまででいいから読んで。そこで刺さらなかったら諦めていい。", likes: 142 },
  { date: "2026-06-10", persona: "saori", slug: "berserk", copy: "蝕の夜を越えてなお「それでも生きる」を選ぶガッツに、大人になってから何度も救われました。", likes: 188 },
  { date: "2026-06-10", persona: "keizo", slug: "bar-lemon-heart", copy: "酒場の漫画はいくつもありますが、酒「で」人を描いた漫画はこれが随一。一晩一話、お湯割りと共に。", likes: 64 },
];

export default function SansedaiArchive() {
  const { manga } = bundle();
  const find = (s: string) => manga.find((m) => m.slug === s);
  const byDate = new Map<string, typeof LOG>();
  for (const l of LOG) {
    byDate.set(l.date, [...(byDate.get(l.date) ?? []), l]);
  }
  const pname = (id: string) => PERSONAS.find((p) => p.id === id);

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-12">
      <DesignNav current={8} />
      <header className="px-4 pb-4 pt-6">
        <h1 className="text-xl font-extrabold">👥 三世代、今日の一冊 — 過去ログ</h1>
        <p className="mt-1 text-[12px] text-ink/55">案内人の推薦を全部さかのぼれます。♥で「この人の推し、良い」を教えてください(匿名・登録不要)。</p>
        {/* ペルソナ一覧 = 人気統計の器(♥集計でランキング化) */}
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
          {PERSONAS.map((p) => (
            <span key={p.id} className="shrink-0 rounded-full border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-1.5 text-[11px]">
              <b>{p.name}</b> <span className="text-ink/50">({p.target})</span>
            </span>
          ))}
          <span className="shrink-0 rounded-full border border-dashed border-[var(--color-line)] px-3 py-1.5 text-[11px] text-ink/45">+ ペルソナは増設可</span>
        </div>
      </header>

      {[...byDate.entries()].map(([date, items]) => (
        <section key={date} className="mt-4 px-4">
          <h2 className="text-[12px] font-bold tracking-widest text-ink/50">{date}</h2>
          <div className="mt-2 space-y-2.5">
            {items.map((l) => {
              const m = find(l.slug);
              const p = pname(l.persona);
              if (!m || !p) return null;
              return (
                <div key={l.persona + l.slug} className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3 shadow-sm">
                  <Link href={`/manga/${m.slug}`} className="flex gap-3">
                    <div className="w-12 shrink-0 self-start"><Cover m={m} sizes="48px" /></div>
                    <div className="min-w-0">
                      <p className="text-[10px] font-bold text-[var(--color-accent)]">{p.name}({p.target})</p>
                      <p className="text-[13px] font-bold leading-snug">{m.title}</p>
                      <p className="mt-1 text-[12px] leading-relaxed text-ink/75">{l.copy}</p>
                    </div>
                  </Link>
                  <div className="mt-2 flex items-center justify-between pl-[60px]">
                    <LikeButtonMock id={`${l.date}:${l.persona}`} base={l.likes} />
                    <span className="text-[10px] text-ink/40">#{p.name}の推薦一覧 →</span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ))}

      <p className="mt-8 px-4 text-center text-[10.5px] leading-relaxed text-ink/45">
        本実装: コピーはAI月次バッチ→seed焼き(静的・毎日増えるSEO資産)<br />
        ♥はWorker+KVの匿名カウンタ(PIIゼロ) ・ ペルソナ人気ランキングに集計
      </p>
    </div>
  );
}
