"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { Halftone } from "@/app/compass/halftone";
// ★見た目は専用CSSへ(Tailwind の新しいクラスを書くと全頁の共通CSSが変わる)。
import "./tone-band.css";

/** 巻の一覧(VolumeCoverflow)で巻を選んだ時に投げる。 detail = その巻の書影URL。 */
export const VOL_COVER_EVENT = "mangal:vol-cover";

/** 楽天の書影は 300×300 で取り直す(網点に敷くので大きめ・サイトの書影解像度の方針と同じ)。 */
function bigger(u: string): string {
  return u.includes("thumbnail.image.rakuten.co.jp") ? u.replace(/\?_ex=\d+x\d+$/, "") + "?_ex=300x300" : u;
}

/** 地の色が暗いか(明るい表示=白い紙の網点 / 暗い表示=黒地の網点 を切り替える)。 */
function isDarkPaper(el: HTMLElement): boolean {
  const c = getComputedStyle(el).backgroundColor.match(/\d+(\.\d+)?/g);
  if (!c || c.length < 3) return false;
  const [r, g, b] = c.map(Number);
  return 0.299 * r + 0.587 * g + 0.114 * b < 110;
}

/**
 * 作品頁の「題名の背景の帯」= 選んでいる巻の書影の網点(2026-09-30 ユーザ裁定: 案1。 2026-10-04 本番にも出す)。
 * 最初は1巻、巻の一覧で巻を選ぶと、その巻の書影へ「ばらばら」の出方で約1秒かけて入れ替わる。
 * 網点の描き方は羅針盤と同じ部品(app/compass/halftone.ts: 画素を読まずに点の形でくり抜く=
 * 楽天の書影でも動く)。 サーバ描画は子(題名など)だけ = 網点は水和後に描く。
 */
export default function ToneBand({ cover, children }: { cover: string | null; children: ReactNode }) {
  if (!cover) return <>{children}</>;
  return <Band cover={cover}>{children}</Band>;
}

function Band({ cover, children }: { cover: string; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  const bg = useRef<HTMLDivElement>(null);
  const cv = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const el = box.current;
    const back = bg.current;
    const canvas = cv.current;
    if (!el || !back || !canvas) return;
    const ht = new Halftone(canvas);
    ht.fixedTone = "scatter";
    ht.overscan = 0;
    ht.reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // 地の色は網点の箱(背景 = 頁の地 --color-paper)で見る。 外枠は透明なので見ても分からない
    const theme = () => el.setAttribute("data-tone", isDarkPaper(back) ? "dark" : "light");
    const fit = () => {
      const r = back.getBoundingClientRect();
      ht.resize(Math.round(r.width), Math.round(r.height), r.width / 2, r.height / 2);
    };
    theme();
    fit();
    ht.setCover(bigger(cover));
    const ro = new ResizeObserver(fit);
    ro.observe(back);
    // 表示の切替(明るい/暗い・電子モードの地の色)に追従
    const mo = new MutationObserver(theme);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-theme", "data-purchase-mode"] });
    mo.observe(document.body, { attributes: true, attributeFilter: ["class"] });
    const onVol = (e: Event) => {
      const url = (e as CustomEvent<string | null>).detail;
      if (url) ht.setCover(bigger(url));
    };
    window.addEventListener(VOL_COVER_EVENT, onVol);
    return () => {
      window.removeEventListener(VOL_COVER_EVENT, onVol);
      ro.disconnect();
      mo.disconnect();
      ht.destroy();
    };
  }, [cover]);
  // ★包むのは題名の行だけ(本番の木を1バイトも変えないため、作品頁は題名の行1つを三項で差し替えるだけ)。
  //   網点は後ろに絶対配置で、頁の上端〜副題・読みの行の下まで伸ばす(tone-band.css)。
  return (
    <div ref={box} className="tone-band">
      <div ref={bg} className="tone-band-bg" aria-hidden="true">
        <canvas ref={cv} className="tone-band-cv" />
      </div>
      <div className="tone-band-in">{children}</div>
    </div>
  );
}
