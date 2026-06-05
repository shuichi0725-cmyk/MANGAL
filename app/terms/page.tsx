import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "利用規約 — MANGAL",
  description: "MANGAL の利用規約・免責事項・著作権について。",
};

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <Link href="/" className="text-sm text-ink/60 hover:text-ink">
        ← トップへ戻る
      </Link>

      <h1 className="mt-6 text-2xl md:text-3xl font-bold">利用規約</h1>
      <p className="mt-2 text-xs text-ink/50">最終更新: 2026年4月</p>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">1. 適用範囲</h2>
        <p>
          本規約は、MANGAL（以下「本サイト」）の利用に関する条件を、本サイトを利用するすべての方（以下「利用者」）と運営者の間で定めるものです。利用者は本サイトの利用をもって本規約に同意したものとみなします。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">2. 掲載情報の正確性</h2>
        <p>
          本サイトに掲載されている書誌情報・発売日・出版社名・ジャンル等は、公開データソースおよび編集部による調査に基づきますが、その正確性・完全性・最新性を保証するものではありません。
        </p>
        <p>
          実際に書籍を購入される際は、必ず Amazon.co.jp その他販売ページの情報をご確認のうえご判断ください。情報の誤りに気付かれた場合は、お問い合わせいただければ随時修正します。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">3. 著作権・知的財産権</h2>
        <p>
          本サイトに掲載されている各漫画作品のタイトル・著者名・あらすじ・表紙画像等は、各権利者に帰属します。本サイトは書誌情報として再構成して掲載しているのみであり、各作品の権利を主張するものではありません。
        </p>
        <p>
          表紙画像は openBD（再配布可）から取得したもの、または Amazon.co.jp の商品ページへリンクするものです。
        </p>
        <p>
          本サイト独自のコード・文章・デザインの著作権は運営者に帰属します。一部のコードはオープンソースとして公開する予定です。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">4. リンクについて</h2>
        <p>
          本サイトへのリンクは原則自由です。ただし、本サイトの内容を歪めて伝える形でのリンク・引用、公序良俗に反するサイトからのリンクはご遠慮ください。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">5. 免責事項</h2>
        <p>
          本サイトの利用により利用者または第三者に発生した損害について、運営者は一切の責任を負いません。Amazon.co.jp その他外部サイトの利用は、各サイトの利用規約に従ってください。
        </p>
        <p>
          本サイトの外部リンクから遷移した先での取引は、すべて当該販売事業者と利用者との間で完結します。本サイトはその取引に関与しません。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">6. サイトの変更・停止</h2>
        <p>
          運営者は予告なく本サイトの内容を変更・更新・停止することがあります。これによって生じた損害について責任を負いません。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">7. 規約の変更</h2>
        <p>
          本規約は予告なく変更されることがあります。変更後の内容は、本ページに掲載した時点で効力を生じます。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">8. 準拠法・管轄裁判所</h2>
        <p>
          本規約の解釈および本サイトの利用に関して紛争が生じた場合は、日本法を準拠法とし、運営者の所在地を管轄する裁判所を第一審の専属的合意管轄とします。
        </p>
      </section>
    </div>
  );
}
