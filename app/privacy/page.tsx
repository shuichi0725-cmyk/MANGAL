import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "プライバシーポリシー — MANGAL",
  description:
    "MANGAL における個人情報・Cookie の取り扱い、アフィリエイト広告に関する開示。",
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
          MANGAL（以下「本サイト」）は会員登録を設けておらず、閲覧にあたって個人情報の入力を求めることはありません。お問い合わせフォームでは、任意でお名前・返信先メールアドレスをご記入いただけます。ご記入いただいた情報は、お問い合わせ内容の確認とご返信の目的にのみ使用し、目的を終えたものは削除します。第三者に提供することはありません。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">2. Cookie の利用</h2>
        <p>
          リンク先の事業者（楽天・Amazon.co.jp 等）およびアフィリエイト計測（楽天アフィリエイト）が、遷移時に Cookie を発行することがあります。これらの Cookie は本サイトが直接管理するものではなく、各事業者のプライバシーポリシーに従って取り扱われます。
        </p>
        <p>
          Cookie の受け入れを希望されない場合は、お使いのブラウザの設定で Cookie を無効化することで拒否できます。Cookie を無効化しても本サイトの閲覧に支障はありません。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">3. アフィリエイトプログラムについて</h2>
        <p>
          当サイトは楽天アフィリエイトを利用しており、店舗リンク（楽天等）にはアフィリエイト広告を含みます（該当箇所に [PR] を表示）。今後、Amazon アソシエイト等ほかのプログラムを追加する場合も、開始時に本ページへ開示します。
        </p>
        <p>
          各作品の購入ボタンをクリックすると楽天ブックス等の商品ページに遷移し、その後の購入に応じて運営者に紹介料が支払われる場合があります。リンクのクリックによって読者が追加の費用を負担することはありません。
        </p>
      </section>

      <section className="mt-8 space-y-3 text-sm leading-relaxed text-ink/80">
        <h2 className="text-base font-semibold text-ink">4. いいね機能</h2>
        <p>
          「いいね（♥）」は匿名の集計カウンタで、個人を特定する情報は取得・保存しません。押した状態の記憶にはブラウザのローカルストレージのみを使用します。
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
          本ポリシーに関するご質問は、
          <a href="/contact" className="text-[var(--color-accent)] underline">お問い合わせフォーム</a>
          からご連絡ください。
        </p>
      </section>
    </div>
  );
}
