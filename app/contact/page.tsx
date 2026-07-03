import ContactForm from "./ContactForm";

/** お問い合わせフォーム(2026-07-03)。 送信先メールアドレスはソースに含めない
 *  (= Worker /api/contact が受信箱へ中継。 スクレイピング耐性)。 */
export const metadata = { title: "お問い合わせ | MANGAL" };

export default function ContactPage() {
  return (
    <div className="mx-auto max-w-xl px-4 py-8">
      <h1 className="text-2xl font-bold">お問い合わせ</h1>
      <p className="mt-2 text-sm leading-relaxed text-ink/70">
        情報の誤り・削除依頼・ご意見などはこちらから。返信が必要な場合はメールアドレスをご記入ください(任意)。
      </p>
      <ContactForm />
    </div>
  );
}
