"use client";

import type { CSSProperties } from "react";
import type { MangaListItem } from "@/lib/schema";
import { yearStatusLabel } from "@/lib/format";
import { useRailMasters } from "@/lib/useRailMasters";
import { komaCatchSize, komaNarration, komaTitleSize, komaVolumes } from "./compass";

/**
 * 真ん中の本を押すと、舞台が漫画の1ページになる(案6「漫画のコマ割り」・2026-10-06 ユーザ裁定)。
 * 中心の本の索引データ(題名・著者・連載・巻数・掲載誌・ジャンル・要素・キャッチ・書影)を流し込むだけ = 作品ごとの手作業なし。
 * コマは順に入る: 書影 → 題名の書き文字 → キャッチの吹き出し → 書誌。 欠けている項目のコマは詰める
 * (キャッチが無い本 = 書誌から言えることだけのナレーション箱)。 出版社名だけは重いマスタなので押した時に取る(取れなければ出さない)。
 */
export default function KomaPage({
  item,
  magName,
  genreName,
  demoName,
  href,
  onDetail,
  onClose,
}: {
  item: MangaListItem;
  magName: (key: string) => string;
  genreName: (key: string) => string;
  demoName: (key: string) => string;
  href: string;
  onDetail: () => void;
  onClose: () => void;
}) {
  const { publishers } = useRailMasters(true);
  const pub = publishers.find((p) => p.key === item.publisher)?.name ?? null;
  // ヨミは題が長い(17字以上)と題名のコマを埋め尽くすので出さない
  const kana = item.title_kana && item.title_kana !== item.title && [...item.title].length <= 16 ? item.title_kana : null;
  const authors = [...new Set((item.authors ?? []).map((a) => a.name).filter(Boolean))];
  const originals = [...new Set((item.original_authors ?? []).map((a) => a.name).filter(Boolean))];
  const vols = komaVolumes(item);
  // ★ジャンル・要素は全部出す(2026-10-06 ユーザ指示「全部表示・足りなければ枠を縦に伸ばす」)。 書誌のコマは中身の高さで伸びる
  const themes = [...new Set(item.themes ?? [])];
  const meta = [item.magazine ? magName(item.magazine) : null, pub, item.demographic ? demoName(item.demographic) : null].filter(Boolean);
  const d = (i: number) => ({ "--d": `${120 + i * 140}ms` }) as CSSProperties;

  return (
    <div className="cp-koma-wrap" onClick={onClose} role="dialog" aria-label={`${item.title}の紹介`}>
      <div className="cp-koma" onClick={(e) => e.stopPropagation()}>
        {/* 1. 書影のコマ */}
        <div className="ck ck-cov" style={d(0)}>
          {item.cover ? (
            // eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク(images.unoptimized)
            <img
              src={item.cover.includes("thumbnail.image.rakuten.co.jp") ? item.cover.replace(/\?_ex=\d+x\d+$/, "") + "?_ex=400x400" : item.cover}
              alt=""
              className="bg-white"
              draggable={false}
            />
          ) : (
            <div className="ck-noimg">{item.title}</div>
          )}
        </div>
        {/* 2. 題名の書き文字 */}
        <div className="ck ck-title" style={d(1)}>
          <div className="ck-t" style={{ fontSize: komaTitleSize(item.title) }}>
            {item.title}
          </div>
          {kana && <div className="ck-kana">{kana}</div>}
          <div className="ck-auth">
            {originals.length > 0 && <span>原作 {originals.slice(0, 2).join("・")}</span>}
            {authors.length > 0 && <span>{authors.slice(0, 2).join("・")}{authors.length > 2 ? " ほか" : ""}</span>}
          </div>
        </div>
        {/* 3. キャッチの吹き出し(無ければナレーション箱) */}
        <div className="ck ck-say" style={d(2)}>
          {item.catch ? (
            <div className="ck-bubble" style={{ fontSize: komaCatchSize(item.catch) }}>
              {item.catch}
            </div>
          ) : (
            <div className="ck-narr">{komaNarration(item, magName)}</div>
          )}
        </div>
        {/* 4. 書誌のコマ */}
        <div className="ck ck-data" style={d(3)}>
          <div className="ck-row">
            <b className="ck-years">{yearStatusLabel(item)}</b>
            {vols && <b className="ck-vols">{vols}</b>}
            {item.anime_adapted && <span className="ck-stamp">アニメ化</span>}
          </div>
          {meta.length > 0 && <div className="ck-meta">{meta.join(" ・ ")}</div>}
          {(item.genres?.length ?? 0) + themes.length > 0 && (
            <div className="ck-tags">
              {(item.genres ?? []).map((k) => (
                <span key={`g:${k}`} className="ck-tag g">
                  {genreName(k)}
                </span>
              ))}
              {themes.map((t) => (
                <span key={`t:${t}`} className="ck-tag">
                  {t}
                </span>
              ))}
            </div>
          )}
          <div className="ck-btns">
            <a className="ck-detail" href={href} onClick={onDetail}>
              詳細 ›
            </a>
            <button type="button" className="ck-close" onClick={onClose}>
              閉じる
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
