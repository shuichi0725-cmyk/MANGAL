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
        <p>数ある漫画サイトの中から MANGAL を見つけていただき、ありがとうございます。</p>
        <p>
          MANGAL は「日本で発売された漫画を、ひとりで自由に探せる」ことをコンセプトにしたサイトです。
          ユーザー同士のつながりは SNS に任せて、ここは“あなたのまだ知らない漫画に出会える検索”に特化しています。
        </p>
        <p>
          正確さや使いやすさにはまだ改善の余地がありますが、情報量と検索の自由度は、他ではなかなか味わえないものになっていると思います。
        </p>
        <p>
          まずは「検索」ボタンを押して、色々いじってみてください。きっと気になる漫画に出会えるはずです。
          ——なぜなら、日本で発売された漫画のほとんど（全部ではありませんが）が、いまあなたの目の前にあるからです。
        </p>
      </section>

      <section className="mt-8 space-y-4 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">できること</h2>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            <strong>キーワード検索</strong> — 作品名・著者名から（ヨミでも探せます）
          </li>
          <li>
            <strong>絞り込み</strong> —
            分野（少年・青年・少女・女性）／ジャンル（ラブコメ・SF など）／要素タグ／連載状態／出版社／連載誌／創刊年代（年代→年→月）／著者（五十音）
          </li>
          <li>
            <strong>並び替え</strong> — 発売年代順・タイトル五十音順・巻数順
          </li>
          <li>
            <strong>作品ページ</strong> — 巻ごとの発売日・書影・版違い（文庫版・完全版など）・書店へのリンク
          </li>
        </ul>
      </section>

      <section className="mt-8 space-y-4 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">データソース</h2>
        <p>本サイトに掲載している書誌情報は、以下の公開データを基に構築しています。表紙画像は楽天ブックス提供の書影を使用しています。</p>
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
            （巻 ISBN・タイトル・出版社・発売日・タイトルヨミ 等の主力書誌情報）
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
              href="https://books.rakuten.co.jp/"
              target="_blank"
              rel="noopener"
              className="text-[var(--color-accent)] underline"
            >
              楽天ブックス
            </a>
            （書影・商品情報。店舗リンクは [PR] アフィリエイト広告を含みます）
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
          運営者: MANGAL
          <br />
          お問い合わせ: <Link href="/contact" className="text-[var(--color-accent)] underline">お問い合わせフォーム</Link>
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
