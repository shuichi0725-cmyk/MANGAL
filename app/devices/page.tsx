import Link from "next/link";
import type { Metadata } from "next";

/**
 * /devices = 電子書籍(漫画)を読むのにおすすめの端末(2026-11-24 ユーザ指示「電子書籍を読むのにおすすめのデバイスコーナー。
 *   この二つは私が使っているがとてもよい」)。 ★感想はユーザ(運営者)本人の言葉が芯 = 他サイトに無い価値。勝手に盛らない。
 * ★料金は書かない([[feedback_no_static_prices]])。 PR表記必須。 商品写真とリンクは Creators API getItems(2026-11-24)の
 *   images.primary.large / detailPageURL(tag 付き)をそのまま使う。 仕様は各商品ページの表記から。
 * 端末を足す時は DEVICES に1件足す(運営者が実際に使ったものだけ)。
 */
type Device = {
  id: string;
  name: string;
  kind: string;
  img: string;
  href: string;
  voice: string[];
  good: string[];
  weak: string[];
  spec: string[];
};

const DEVICES: Device[] = [
  {
    id: "ipad-mini",
    name: "Apple iPad mini(A20 Pro)",
    kind: "8.5インチ 有機EL タブレット",
    img: "https://m.media-amazon.com/images/I/41WCLGzfzFL._SL500_.jpg",
    href: "https://www.amazon.co.jp/dp/B0HPC6RSC9?tag=mangal08-22&linkCode=ogi&th=1&psc=1",
    voice: [
      "普段使いはもちろん、ベッドで部屋を暗くして読むのに、今まで使った中で一番優れていました。",
      "有機ELでバックライトが無いからか、文字が読める明るさまで下げた時に一番まぶしくありません。",
    ],
    good: [
      "暗い部屋で明るさを絞っても読みやすい(運営者の実感)",
      "有機ELで色があざやか = カラー漫画・カラー版がきれい",
      "片手で持てる大きさ(約195×133×5.4mm)",
      "Kindle・楽天Kobo・BookLive! など、どのストアのアプリも入る",
      "耐水・防塵(IP67)= お風呂やキッチンでも安心",
    ],
    weak: ["見開きを実寸で読むには画面が小さめ"],
    spec: ["8.5インチ Super Retina XDR(有機EL)", "A20 Pro チップ", "容量 128GB〜", "USB-C", "Wi-Fi 7"],
  },
  {
    id: "boox-go-color-7",
    name: "BOOX Go Color 7 Gen II",
    kind: "7インチ カラー電子ペーパー端末",
    img: "https://m.media-amazon.com/images/I/4121CNawZnL._SL500_.jpg",
    href: "https://www.amazon.co.jp/dp/B0F58ZHCX2?tag=mangal08-22&linkCode=ogi&th=1&psc=1",
    voice: [
      "電池持ちがとても良く、持ち歩くのに軽い。明るい所で見やすいです。",
      "暗い所ではバックライト(フロントライト)でかなり明るくなるので読めますが、目が疲れます。",
    ],
    good: [
      "電池持ちがとても良い(運営者の実感)",
      "軽くて持ち歩きやすい",
      "光を反射して見る電子ペーパーなので、明るい所・屋外で見やすい",
      "カラー表示(白黒300dpi・カラー150dpi)= カラー表紙・カラー版も色つきで",
      "中身は Android = Kindle 以外の電子書籍ストアのアプリも入る(Kindle 端末との大きな違い)",
    ],
    weak: [
      "暗い所はライトで読めるが目が疲れる(運営者の実感)",
      "ページをめくる時の表示の切り替えが液晶より遅い",
    ],
    spec: ["7インチ Kaleido 3(カラー電子ペーパー)", "白黒300dpi / カラー150dpi", "Android", "容量 64GB", "スタイラス対応(筆圧4096段階)"],
  },
];

export const metadata: Metadata = {
  alternates: { canonical: "/devices" },
  title: "電子書籍(漫画)を読むのにおすすめの端末 — iPad mini と BOOX Go Color 7",
  description:
    "MANGAL の運営者が実際に使っている、電子書籍・漫画を読むのにおすすめの端末を紹介します。" +
    "暗い部屋でもまぶしくない有機ELの iPad mini と、電池持ちが良く明るい所で見やすいカラー電子ペーパーの BOOX Go Color 7 Gen II。良い所も弱点も正直に。",
};

function Bullets({ items, mark, color }: { items: string[]; mark: string; color: string }) {
  return (
    <ul className="mt-1 space-y-1">
      {items.map((t) => (
        <li key={t} className="flex gap-2 text-[13.5px] leading-relaxed text-ink/85">
          <span className="shrink-0 font-bold" style={{ color }}>
            {mark}
          </span>
          <span>{t}</span>
        </li>
      ))}
    </ul>
  );
}

export default function DevicesPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-6 lg:mx-0">
      <p className="text-[11.5px] text-ink/60">
        <span className="mr-1.5 bg-[#ff8a3d] px-1.5 py-px text-[10.5px] font-bold text-black">PR</span>
        このページには Amazon アソシエイトのリンクが含まれます。リンクから購入されると MANGAL に紹介料が入ります。
      </p>
      <h1 className="mt-3 text-2xl font-bold md:text-3xl">電子書籍を読むのにおすすめの端末</h1>
      <p className="mt-1.5 text-sm leading-relaxed text-ink/65">
        MANGAL の運営者が実際に使って「とても良い」と感じた端末だけを載せています。感想は運営者本人のものです。
      </p>

      {/* どっちを選ぶ? 早見 */}
      <div className="mt-5 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <a href="#ipad-mini" className="border border-[var(--color-line)] bg-[var(--color-surface)] p-3">
          <p className="text-[11px] text-ink/55">寝る前・暗い部屋で / カラー漫画</p>
          <p className="mt-0.5 font-bold text-ink">
            iPad mini <span className="text-[var(--color-accent)]">›</span>
          </p>
        </a>
        <a href="#boox-go-color-7" className="border border-[var(--color-line)] bg-[var(--color-surface)] p-3">
          <p className="text-[11px] text-ink/55">外出先・明るい所で / 電池を気にせず</p>
          <p className="mt-0.5 font-bold text-ink">
            BOOX Go Color 7 <span className="text-[var(--color-accent)]">›</span>
          </p>
        </a>
      </div>

      <div className="mt-6 space-y-6">
        {DEVICES.map((d) => (
          <section
            key={d.id}
            id={d.id}
            className="border border-[var(--color-line)] border-t-[3px] border-t-[var(--color-accent)] bg-[var(--color-surface)] p-4"
          >
            <div className="flex gap-4">
              <a href={d.href} target="_blank" rel="sponsored noopener" className="shrink-0">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={d.img} width={500} height={500} alt={d.name} loading="lazy" className="h-28 w-28 bg-white object-contain p-1 sm:h-36 sm:w-36" />
              </a>
              <div className="min-w-0">
                <h2 className="text-[18px] font-bold leading-snug text-ink">{d.name}</h2>
                <p className="mt-0.5 text-[12px] text-[var(--color-accent)]">{d.kind}</p>
              </div>
            </div>

            <blockquote className="mt-4 border-l-[3px] border-[var(--color-accent)] bg-[var(--color-accent)]/10 px-3 py-2.5">
              <p className="mb-1 text-[11px] font-bold text-[var(--color-accent)]">運営者の感想</p>
              {d.voice.map((v) => (
                <p key={v} className="text-[14px] leading-relaxed text-ink">
                  {v}
                </p>
              ))}
            </blockquote>

            <h3 className="mt-4 text-[12.5px] font-bold tracking-wider text-ink/55">良い所</h3>
            <Bullets items={d.good} mark="○" color="var(--color-accent)" />
            <h3 className="mt-3 text-[12.5px] font-bold tracking-wider text-ink/55">弱点</h3>
            <Bullets items={d.weak} mark="△" color="#ff8a3d" />
            <h3 className="mt-3 text-[12.5px] font-bold tracking-wider text-ink/55">主な仕様</h3>
            <p className="mt-1 text-[12.5px] leading-relaxed text-ink/65">{d.spec.join(" ・ ")}</p>

            <a
              href={d.href}
              target="_blank"
              rel="sponsored noopener"
              className="spring-press mt-4 block bg-[var(--color-accent)] py-3 text-center font-extrabold text-black shadow-[3px_3px_0_rgba(0,0,0,0.45)]"
            >
              Amazon で見る
            </a>
          </section>
        ))}
      </div>

      <p className="mt-5 border-t border-[var(--color-line)] pt-3 text-[12px] leading-relaxed text-ink/60">
        価格は変わるため載せていません。最新の価格・在庫・容量や色の選択肢は Amazon の商品ページでご確認ください。
      </p>
      <p className="mt-3 text-sm">
        <Link href="/service" className="text-ink/60 hover:text-ink">
          読み放題・聴き放題のサービスは「Amazonのサービス」へ →
        </Link>
      </p>
    </div>
  );
}
