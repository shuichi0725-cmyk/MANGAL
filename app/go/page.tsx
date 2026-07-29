"use client";

import { Suspense, useEffect, useState } from "react";

/** ストア中継ページ (2026-07-29 ユーザ要望「電子書籍はアプリでなくブラウザで開く」)。
 *  Androidの App Links は <a href> タップを Amazon/楽天アプリに奪う(アプリ内ではKindle等を
 *  購入できない)。JSからの location.replace はアプリに奪われないため、自ドメインの本頁を
 *  経由して JS 遷移する([[kindle-link-browser-not-app]]の実装)。
 *  ★オープンリダイレクト防止: 許可ホストのみ遷移。それ以外は何もしない。 */
const ALLOW_HOSTS = new Set([
  "www.amazon.co.jp",
  "amazon.co.jp",
  "books.rakuten.co.jp",
  "hb.afl.rakuten.co.jp",
  "shopping.yahoo.co.jp",
]);

function GoInner() {
  const [state, setState] = useState<"loading" | "bad">("loading");
  const [dest, setDest] = useState<string>("");
  useEffect(() => {
    const u = new URLSearchParams(window.location.search).get("u") || "";
    try {
      const url = new URL(u);
      if (url.protocol === "https:" && ALLOW_HOSTS.has(url.hostname)) {
        setDest(u);
        // 直ちにJS遷移(リンククリックでないためアプリに奪われずブラウザ内で開く)
        window.location.replace(u);
        return;
      }
    } catch {
      /* fallthrough */
    }
    setState("bad");
  }, []);
  return (
    <main className="mx-auto max-w-md px-4 py-16 text-center text-sm text-ink/70">
      {state === "loading" ? (
        <>
          <p>ストアへ移動しています…</p>
          {dest && (
            <p className="mt-3 text-[12px]">
              自動で移動しない場合は{" "}
              <a className="font-bold text-[var(--color-accent)] underline" href={dest}>
                こちら
              </a>
            </p>
          )}
        </>
      ) : (
        <p>無効なリンクです。</p>
      )}
    </main>
  );
}

export default function GoPage() {
  return (
    <Suspense fallback={null}>
      <GoInner />
    </Suspense>
  );
}
