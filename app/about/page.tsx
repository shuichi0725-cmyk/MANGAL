import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "MANGAL について",
  description:
    "MANGAL は日本の漫画を出版年・著者・出版社・分野・ジャンルから絞り込めるカタログサイトです。",
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <Link href="/" className="text-sm text-black/60 hover:text-black">
        ← トップへ戻る
      </Link>

      <h1 className="mt-6 text-2xl md:text-3xl font-bold">MANGAL について</h1>

      <section className="mt-8 space-y-4 text-sm leading-relaxed text-black/80">
        <h2 className="text-base font-semibold text-black">サイトの目的</h2>
        <p>
          MANGAL は日本の漫画を「出版年」「著者・原作者」「出版社・連載誌」「分野（少年・青年・少女・女性 など）」「ジャンル（ギャグ・ラブコメ・SF など）」から絞り込んで閲覧できるカタログサイトです。
          各作品の詳細ページには、巻ごとの発売日と表紙、Amazon の商品ページへのリンクを掲載しています。
        </p>
      </section>

      <section className="mt-8 space-y-4 text-sm leading-relaxed text-black/80">
        <h2 className="text-base font-semibold text-black">データソース</h2>
        <p>本サイトに掲載している書誌情報は、以下の公開データを基に構築しています。</p>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            <a
              href="https://openbd.jp/"
              target="_blank"
              rel="noopener"
              className="text-[var(--color-accent)] underline"
            >
              openBD
            </a>
            （書誌・表紙画像。再配布可）
          </li>
          <li>
            <a
              href="https://www.wikidata.org/"
              target="_blank"
              rel="noopener"
              className="text-[var(--color-accent)] underline"
            >
              Wikidata
            </a>
            （CC0 ライセンス）
          </li>
          <li>各出版社の公式情報・編集部による手動補完</li>
        </ul>
        <p>
          ジャンル分類および分野（少年/青年/etc）は、編集部による手動付与です。誤りがありましたらご連絡ください。
        </p>
      </section>

      <section className="mt-8 space-y-4 text-sm leading-relaxed text-black/80">
        <h2 className="text-base font-semibold text-black">アフィリエイトについて</h2>
        <p>
          各作品の購入リンクは Amazon.co.jp の商品ページへ誘導するもので、Amazon
          アソシエイト・プログラムを利用しています。詳しくは
          <Link href="/privacy" className="text-[var(--color-accent)] underline">
            プライバシーポリシー
          </Link>
          をご覧ください。
        </p>
      </section>

      <section className="mt-8 space-y-4 text-sm leading-relaxed text-black/80">
        <h2 className="text-base font-semibold text-black">運営</h2>
        <p>
          運営者: （運営者名）
          <br />
          お問い合わせ: （連絡先メールアドレス）
        </p>
      </section>

      <section className="mt-8 space-y-4 text-sm leading-relaxed text-black/80">
        <h2 className="text-base font-semibold text-black">関連ページ</h2>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            <Link href="/privacy" className="text-[var(--color-accent)] underline">
              プライバシーポリシー
            </Link>
          </li>
          <li>
            <Link href="/terms" className="text-[var(--color-accent)] underline">
              利用規約
            </Link>
          </li>
        </ul>
      </section>
    </div>
  );
}
