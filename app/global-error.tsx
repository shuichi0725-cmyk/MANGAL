"use client";

import { useEffect } from "react";

// ★root layout ごと落ちた時の最終防衛 (= app/error.tsx と同じ一回自動リロード方針)。
//   global-error は html/body を自前で持つ規約。
const KEY = "mangal-err-reload-at";

export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    try {
      const last = Number(sessionStorage.getItem(KEY) || 0);
      if (Date.now() - last > 30_000) {
        sessionStorage.setItem(KEY, String(Date.now()));
        window.location.reload();
      }
    } catch {}
  }, []);
  return (
    <html lang="ja">
      <body>
        <div style={{ minHeight: "60vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, padding: 24, textAlign: "center", fontFamily: "sans-serif" }}>
          <p style={{ fontSize: 18, fontWeight: 700 }}>ページの読み込みに失敗しました</p>
          <p style={{ fontSize: 13, color: "#666" }}>サイト更新の直後はこの画面が出ることがあります。再読み込みで直ります。</p>
          <button
            type="button"
            onClick={() => {
              try {
                sessionStorage.removeItem(KEY);
              } catch {}
              reset();
              window.location.reload();
            }}
            style={{ borderRadius: 999, background: "#111", color: "#fff", padding: "8px 24px", fontSize: 14, fontWeight: 700, border: 0, cursor: "pointer" }}
          >
            再読み込み
          </button>
        </div>
      </body>
    </html>
  );
}
