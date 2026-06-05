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
      <Link href="/" className="text-sm text-ink/60 hover:text-ink">
        ← トップへ戻る
      </Link>

      <h1 className="mt-6 text-2xl md:text-3xl font-bold">MANGAL について</h1>

      <section className="mt-8 space-y-4 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">サイトの目的</h2>
        <p>
          MANGAL は日本の漫画を「出版年」「著者・原作者」「出版社・連載誌」「分野（少年・青年・少女・女性 など）」「ジャンル（ギャグ・ラブコメ・SF など）」から絞り込んで閲覧できるカタログサイトです。
          各作品の詳細ページには、巻ごとの発売日と Amazon の商品ページへのリンクを掲載しています。
        </p>
      </section>

      <section className="mt-8 space-y-4 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">データソース</h2>
        <p>本サイトに掲載している書誌情報は、以下の公開データを基に構築しています。表紙画像は使用していません（Amazon 公式画像の連携を予定）。</p>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            <a
              href="https://ndlsearch.ndl.go.jp/"
              target="_blank"
              rel="noopener"
              className="text-[var(--color-accent)] underline"
            >
              国立国会図書館サーチ (NDL)
            </a>
            （巻 ISBN・タイトル・出版社・発売日 等の主力書誌情報）
          </li>
          <li>
            <a
              href="https://ja.wikipedia.org/"
              target="_blank"
              rel="noopener"
              className="text-[var(--color-accent)] underline"
            >
              ウィキペディア日本語版
            </a>
            （CC BY-SA。連載誌・ジャンル・あらすじ等の補完）
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
            （CC0。漫画家リストのソース）
          </li>
          <li>
            <a
              href="https://openbd.jp/"
              target="_blank"
              rel="noopener"
              className="text-[var(--color-accent)] underline"
            >
              openBD
            </a>
            （書誌情報の照合用に参照）
          </li>
          <li>各出版社の公式情報・編集部による手動補完</li>
        </ul>
        <p>
          ジャンル分類および分野（少年/青年/etc）は、編集部による手動付与・補正を含みます。誤りがありましたらご連絡ください。
        </p>
      </section>

      <section className="mt-8 space-y-4 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">アフィリエイトについて</h2>
        <p>
          各作品の購入リンクは Amazon.co.jp 等の商品ページへ誘導します。将来的に
          アフィリエイト・プログラム（Amazon アソシエイト等）を利用する場合があります。詳しくは
          <Link href="/privacy" className="text-[var(--color-accent)] underline">
            プライバシーポリシー
          </Link>
          をご覧ください。
        </p>
      </section>

      <section className="mt-8 space-y-4 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">運営</h2>
        <p>
          運営者: （運営者名）
          <br />
          お問い合わせ: （連絡先メールアドレス）
        </p>
      </section>

      <section className="mt-8 space-y-4 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">関連ページ</h2>
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
