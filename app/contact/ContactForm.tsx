"use client";

import { useState } from "react";

/** 送信先アドレス非公開のフォーム: POST /api/contact → Worker が受信箱(KV)へ保存
 *  (将来: ドメイン設定後に Email Routing でメール転送)。 honeypot でbot対策。 */
export default function ContactForm() {
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  return state === "done" ? (
    <div className="mt-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
      送信しました。ありがとうございます。返信先の記載がある場合は、確認のうえご連絡します。
    </div>
  ) : (
    <form
      className="mt-6 space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        const f = e.currentTarget;
        const fd = new FormData(f);
        if (String(fd.get("website") || "")) return; // honeypot
        setState("sending");
        const payload = JSON.stringify({
          name: String(fd.get("name") || ""),
          email: String(fd.get("email") || ""),
          body: String(fd.get("body") || ""),
        });
        const post = (url: string) =>
          fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: payload });
        try {
          let r = await post("/api/contact").catch(() => null);
          if (!r || !r.ok) {
            // preview等 API 無し環境 → 本番Workerへ直接(CORS許可済)
            r = await post("https://mangal-db.com/api/contact");
          }
          setState(r.ok ? "done" : "error");
        } catch {
          setState("error");
        }
      }}
    >
      <div>
        <label className="text-xs font-semibold text-ink/60">お名前(任意)</label>
        <input
          name="name"
          maxLength={80}
          className="mt-1 w-full rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-2 text-sm focus:border-[var(--color-accent)] focus:outline-none"
        />
      </div>
      <div>
        <label className="text-xs font-semibold text-ink/60">返信先メールアドレス(任意)</label>
        <input
          name="email"
          type="email"
          maxLength={120}
          className="mt-1 w-full rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-2 text-sm focus:border-[var(--color-accent)] focus:outline-none"
        />
      </div>
      <div>
        <label className="text-xs font-semibold text-ink/60">内容(必須)</label>
        <textarea
          name="body"
          required
          rows={6}
          maxLength={4000}
          placeholder="例: 「作品名」の発売日が誤っています / この作品を掲載してほしい 等"
          className="mt-1 w-full rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-2 text-sm focus:border-[var(--color-accent)] focus:outline-none"
        />
      </div>
      {/* honeypot(botのみが埋める) */}
      <input name="website" tabIndex={-1} autoComplete="off" className="hidden" aria-hidden="true" />
      {state === "error" && (
        <p className="text-xs text-rose-600">送信に失敗しました。時間をおいて再度お試しください。</p>
      )}
      <button
        type="submit"
        disabled={state === "sending"}
        className="spring-press w-full rounded-full bg-[var(--color-accent)] py-2.5 text-sm font-bold text-white disabled:opacity-50"
      >
        {state === "sending" ? "送信中…" : "送信する"}
      </button>
    </form>
  );
}
