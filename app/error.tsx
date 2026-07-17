"use client";

import { useEffect } from "react";

// ★クライアント例外の自動復旧 (= 2026-07-18 版ズレ対策)。
//   デプロイ直後は edge の stale-while-revalidate で旧ビルドHTMLが一度配られ、
//   旧JS×新形式索引で例外→英語の「Application error」素画面になっていた。
//   再読込で直る性質(裏で再検証済み)なので、一度だけ自動リロードして透過復旧する。
//   30秒以内の再発(=真のバグ)はループさせず日本語の案内を出す。
const KEY = "mangal-err-reload-at";

function tryAutoReload(): boolean {
  try {
    const last = Number(sessionStorage.getItem(KEY) || 0);
    if (Date.now() - last > 30_000) {
      sessionStorage.setItem(KEY, String(Date.now()));
      window.location.reload();
      return true;
    }
  } catch {
    /* sessionStorage不可なら案内表示へ */
  }
  return false;
}

export default function Error({ reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    tryAutoReload();
  }, []);
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="text-lg font-bold">ページの読み込みに失敗しました</p>
      <p className="text-sm text-gray-500">
        サイト更新の直後はこの画面が出ることがあります。再読み込みで直ります。
      </p>
      <button
        type="button"
        onClick={() => {
          try {
            sessionStorage.removeItem(KEY);
          } catch {}
          reset();
          window.location.reload();
        }}
        className="rounded-full bg-gray-900 px-6 py-2 text-sm font-bold text-white"
      >
        再読み込み
      </button>
    </div>
  );
}
