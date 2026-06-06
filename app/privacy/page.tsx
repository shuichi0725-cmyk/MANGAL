import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "プライバシーポリシー — MANGAL",
  description:
    "MANGAL における個人情報・Cookie の取り扱い、Amazon アソシエイトに関する開示。",
};

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <Link href="/" className="text-sm text-ink/60 hover:text-ink">
        ← トップへ戻る
      </Link>

      <h1 className="mt-6 text-2xl md:text-3xl font-bold">プライバシーポリシー</h1>
      <p className="mt-2 text-xs text-ink/50">最終更新: 2026年4月</p>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">1. 個人情報の収集について</h2>
        <p>
          MANGAL（以下「本サイト」）はユーザの個人情報を能動的に収集していません。会員登録・お問い合わせフォーム等を設置していないため、お名前・メールアドレス・連絡先の入力を求めることはありません。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">2. Cookie の利用</h2>
        <p>
          リンク先の事業者（Amazon.co.jp 等）が、遷移時に Cookie を発行することがあります。これらの Cookie は本サイトが直接管理するものではなく、各事業者のプライバシーポリシーに従って取り扱われます。将来的にアフィリエイト計測を導入する場合も同様です。
        </p>
        <p>
          Cookie の受け入れを希望されない場合は、お使いのブラウザの設定で Cookie を無効化することで拒否できます。Cookie を無効化しても本サイトの閲覧に支障はありません。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">3. アフィリエイトプログラムについて</h2>
        <p>
          当サイトは将来的に、Amazon アソシエイト・プログラム等のアフィリエイトプログラムを利用する場合があります。利用を開始した際は、運営規約所定の開示文を本ページに掲載します。現時点では、商品リンクは外部サイトの該当ページへ遷移するのみです。
        </p>
        <p>
          各作品の購入ボタンをクリックすると Amazon.co.jp の商品ページに遷移し、その後の購入に応じて運営者に紹介料が支払われる場合があります。リンクのクリックによって読者が追加の費用を負担することはありません。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">4. 第三者への開示</h2>
        <p>
          本サイトはユーザに関する情報を第三者へ開示・販売することはありません。法令に基づく開示請求等があった場合に限り、必要な範囲で対応する場合があります。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">5. プライバシーポリシーの変更</h2>
        <p>
          本ポリシーの内容は、必要に応じて変更することがあります。変更があった場合は、本ページにて告知します。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">6. お問い合わせ</h2>
        <p>
          本ポリシーに関するご質問は、（連絡先メールアドレス）までご連絡ください。
        </p>
      </section>
    </div>
  );
}
