import ContactForm from "./ContactForm";

/** お問い合わせフォーム(2026-07-03)。 送信先メールアドレスはソースに含めない
 *  (= Worker /api/contact が受信箱へ中継。 スクレイピング耐性)。 */
export const metadata = { title: "お問い合わせ | MANGAL" };

export default function ContactPage() {
  return (
    <div className="mx-auto max-w-xl px-4 py-8">
      <div className="rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)]/75 p-5 shadow-[var(--shadow-soft)] backdrop-blur-md">
        <h1 className="text-xl font-bold">お問い合わせ</h1>
        <p className="mt-2 text-[13px] leading-relaxed text-ink/70">
          情報の誤り・削除依頼・ご意見などはこちらから。返信をご希望の場合はメールアドレスをご記入ください(任意)。
        </p>
        <p className="mt-1.5 text-[11px] leading-relaxed text-ink/50">
          ※お寄せいただいた内容はすべて確認していますが、個人運営のため、すべてのお問い合わせに返信できるとは限りません。あらかじめご了承ください。
        </p>
        <ContactForm />
      </div>
    </div>
  );
}
