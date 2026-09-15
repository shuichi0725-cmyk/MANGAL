import ContactForm from "./ContactForm";

/** お問い合わせフォーム(2026-07-03)。 送信先メールアドレスはソースに含めない
 *  (= Worker /api/contact が受信箱へ中継。 スクレイピング耐性)。 */
export const metadata = {
  alternates: { canonical: "/contact" },
  title: "お問い合わせ",
  // ★description が既定のままだった(2026-09-15 番人 _check-ssr-content.py が検出)。
  description:
    "MANGAL への掲載内容の誤りのご指摘・削除依頼・その他のお問い合わせはこちらから。" +
    "書誌データの訂正は、作品名と巻数を添えていただけると確認が早くなります。",
};

export default function ContactPage() {
  return (
    <>
    <div className="mx-auto max-w-xl px-4 py-8 lg:mx-0">
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
    </>
  );
}
