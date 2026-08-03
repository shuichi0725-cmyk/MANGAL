"use client";

import { useState } from "react";

/** 共有ボタン列(X / LINE / 共有)。作品詳細の説明文と関連作品の間に置く(2026-07-12 ユーザ指定位置)。
 *  X/LINE = intent URLへの素のリンク(JS不要・静的exportで確実)。
 *  共有 = Web Share API、非対応環境はクリップボードにコピーして「コピーしました」表示。
 *  ★2026-08-03 検索/一覧にも設置(ユーザ要望): これらはURLが絞り込みで刻々変わるため、
 *   `getUrl`(任意)を渡すと**押す直前に現在URLでhrefを差し替える**(mousedown/touchstart/focus)。
 *   素の<a>のまま=x.com App Links回避のtwitter.com intent実績を崩さない。
 *  `titleSuffix=false` で「 - MANGAL」の自動付与を止める(呼び側が完全な文言を渡す)。 */
export default function ShareButtons({ title, url, getUrl, className, titleSuffix = true }: {
  title: string;
  url: string;
  getUrl?: () => string;
  className?: string;
  titleSuffix?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const text = titleSuffix ? `${title} - MANGAL` : title;
  const enc = encodeURIComponent;
  const cur = () => (getUrl ? getUrl() : url);
  const xHref = (u: string) => `https://twitter.com/intent/tweet?text=${enc(text)}&url=${enc(u)}`;
  const lineHref = (u: string) => `https://social-plugins.line.me/lineit/share?url=${enc(u)}&text=${enc(text)}`;
  // 押す直前にhrefを現在URLへ(getUrl時のみ)。クリック本体はブラウザ標準遷移のまま
  const live = (mk: (u: string) => string) =>
    getUrl
      ? {
          onMouseDown: (e: { currentTarget: HTMLAnchorElement }) => { e.currentTarget.href = mk(cur()); },
          onTouchStart: (e: { currentTarget: HTMLAnchorElement }) => { e.currentTarget.href = mk(cur()); },
          onFocus: (e: { currentTarget: HTMLAnchorElement }) => { e.currentTarget.href = mk(cur()); },
        }
      : {};

  const onShare = async () => {
    const u = cur();
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({ title: text, url: u });
        return;
      } catch {
        // ユーザキャンセル等は無視(コピーにfallbackしない)
        return;
      }
    }
    try {
      await navigator.clipboard.writeText(u);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  const btn =
    "inline-flex items-center gap-1.5 rounded-full border border-[var(--color-line)] " +
    "bg-[var(--color-surface)] px-3.5 py-1.5 text-xs font-medium text-ink/75 " +
    "shadow-[var(--shadow-soft)] active:scale-95 transition hover:text-[var(--color-accent)]";

  return (
    <div className={className ?? "mt-6 flex flex-wrap items-center gap-2"}>
      {/* x.com/intent/post はアプリのApp Linksに拾われず失敗する端末がある(2026-07-12実害) → 旧twitter.comのintentが最も互換 */}
      <a
        href={xHref(url)}
        {...live(xHref)}
        target="_blank"
        rel="noopener nofollow"
        aria-label="Xで共有"
        className={btn}
      >
        {/* X ロゴ */}
        <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current" aria-hidden="true">
          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
        </svg>
        ポスト
      </a>
      <a
        href={lineHref(url)}
        {...live(lineHref)}
        target="_blank"
        rel="noopener nofollow"
        aria-label="LINEで共有"
        className={btn}
      >
        {/* LINE 吹き出しロゴ(簡略) */}
        <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current" aria-hidden="true">
          <path d="M12 2.5c-5.52 0-10 3.63-10 8.1 0 4.01 3.56 7.37 8.37 8-.05.02.33 1.4.36 1.62.05.28-.2 1.12.98.6 1.17-.5 6.3-3.7 8.6-6.35 1.07-1.17 1.69-2.42 1.69-3.87 0-4.47-4.48-8.1-10-8.1zM7.6 13.3H5.53a.5.5 0 0 1-.5-.5V8.9a.5.5 0 0 1 1 0v3.4H7.6a.5.5 0 0 1 0 1zm1.9-.5a.5.5 0 0 1-1 0V8.9a.5.5 0 0 1 1 0v3.9zm5.3 0a.5.5 0 0 1-.9.3l-2.1-2.86V12.8a.5.5 0 0 1-1 0V8.9a.5.5 0 0 1 .9-.3l2.1 2.86V8.9a.5.5 0 0 1 1 0v3.9zm3.7-2.45a.5.5 0 0 1 0 1h-1.57v.95h1.57a.5.5 0 0 1 0 1H16.4a.5.5 0 0 1-.5-.5V8.9a.5.5 0 0 1 .5-.5h2.1a.5.5 0 0 1 0 1h-1.6v.95h1.6z" />
        </svg>
        LINE
      </a>
      <button type="button" onClick={onShare} aria-label="このページを共有" className={btn}>
        {/* 共有アイコン */}
        <svg
          viewBox="0 0 24 24"
          className="h-3.5 w-3.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="18" cy="5" r="3" />
          <circle cx="6" cy="12" r="3" />
          <circle cx="18" cy="19" r="3" />
          <path d="M8.59 13.51l6.83 3.98M15.41 6.51l-6.82 3.98" />
        </svg>
        {copied ? "コピーしました" : "共有"}
      </button>
    </div>
  );
}
