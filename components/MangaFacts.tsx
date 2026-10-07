import Link from "next/link";
import { Fragment, type ReactNode } from "react";
import { manyPeople, pickDescription, stackPeople } from "@/lib/mangaFacts";
// ★見た目は専用CSSへ(Tailwind の新しいクラスを書くと全頁の共通CSSが変わる)。
import "./manga-facts.css";

export type FactLink = { name: string; href: string };

/**
 * 作品頁の基本情報欄 = 見本その2「D3 コマ割り」(2026-10-07 ユーザ裁定。 旧 = 見出し列+灰色の枠の <dl>)。
 * 3段のコマ: 出版年 / 著者 | 連載誌(無ければ出版社)の斜めの2コマ / ジャンル・要素。
 * 各コマの左上の写植箱が羅針盤の糸の色 = 押した先も羅針盤の糸と同じ(作者の作品・同じ雑誌・同じ年・ジャンル・要素)。
 * ★SEO の約束: 文字・リンク先・リンクの本数は旧 <dl> と同じ(出版年/著者/原作/その他/出版社/連載誌/分野/ジャンル/要素)。
 *   見た目は CSS だけ(サーバ描画・JS なし)。 並びは「連載誌」と「出版社」が入れ替わるだけ。
 * 判断(縦に積むか・名前が多いか)は lib/mangaFacts.ts。
 */
export default function MangaFacts({
  year,
  authors,
  originals,
  credits,
  publisher,
  magazine,
  demographic,
  genres,
  elems,
  tail,
}: {
  year: FactLink;
  authors: FactLink[];
  originals: FactLink[];
  /** その他(監修・編集など)= 文字だけ(リンク無しは従来どおり) */
  credits: { role: string; names: string[] }[];
  publisher: FactLink;
  magazine: FactLink | null;
  demographic: FactLink | null;
  /** href 無し = マスタ外のジャンル(押せない) */
  genres: { name: string; href: string | null }[];
  elems: FactLink[];
  /** 同ジャンル検索・羅針盤マーク(作品頁が組む) */
  tail: ReactNode;
}) {
  const join = (xs: FactLink[]) =>
    xs.map((x, i) => (
      <Fragment key={i}>
        {i > 0 && "・"}
        <Link href={x.href}>{x.name}</Link>
      </Fragment>
    ));
  // 著者が居なければ原作を主役に(索引ガードで著者は空にならない想定だが、念のため)
  const lead = authors.length > 0 ? { cap: "著者", people: authors } : originals.length > 0 ? { cap: "原作", people: originals } : null;
  const subOriginals = authors.length > 0 ? originals : [];
  const stack =
    !lead || stackPeople(lead.people.map((a) => a.name), subOriginals.map((a) => a.name), credits);
  const right = magazine
    ? { cls: "mf-c-mg", cap: "連載誌", main: magazine, pub: publisher as FactLink | null }
    : { cls: "mf-c-nt", cap: "出版社", main: publisher, pub: null };

  return (
    <div className="mf">
      <dl className="mf-p mf-tone mf-c-yr">
        <div className="mf-main">
          <dt className="mf-cap">出版年</dt>
          <dd className="mf-big">
            <Link href={year.href}>{year.name}</Link>
          </dd>
        </div>
      </dl>

      <div className={stack ? "mf-row mf-stack" : "mf-row"}>
        {lead && (
          <div className="mf-sl mf-c-au">
            <dl className="mf-in">
              <div className="mf-main">
                <dt className="mf-cap">{lead.cap}</dt>
                <dd className={manyPeople(lead.people.map((a) => a.name)) ? "mf-big mf-many" : "mf-big"}>{join(lead.people)}</dd>
              </div>
              {subOriginals.length > 0 && (
                <div className="mf-kv">
                  <dt>原作</dt>
                  <dd>{join(subOriginals)}</dd>
                </div>
              )}
              {credits.map((c) => (
                <div key={c.role} className="mf-kv">
                  <dt>{c.role}</dt>
                  <dd>{c.names.join(" / ")}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}
        <div className={`mf-sr ${right.cls}`}>
          <dl className="mf-in">
            <div className="mf-main">
              <dt className="mf-cap">{right.cap}</dt>
              <dd className="mf-big">
                <Link href={right.main.href}>{right.main.name}</Link>
              </dd>
            </div>
            {right.pub && (
              <div className="mf-kv">
                <dt>出版社</dt>
                <dd>
                  <Link href={right.pub.href}>{right.pub.name}</Link>
                </dd>
              </div>
            )}
            {demographic && (
              <div className="mf-kv">
                <dt>分野</dt>
                <dd>
                  <Link href={demographic.href}>{demographic.name}</Link>
                </dd>
              </div>
            )}
          </dl>
        </div>
      </div>

      {(genres.length > 0 || elems.length > 0) && (
        <dl className="mf-p mf-tg">
          {genres.length > 0 && (
            <div className="mf-tl mf-c-gn">
              <dt>ジャンル</dt>
              <dd>
                {genres.map((g, i) =>
                  g.href ? (
                    <Link key={i} href={g.href} className="mf-chip">
                      {g.name}
                    </Link>
                  ) : (
                    <span key={i} className="mf-chip mf-off">
                      {g.name}
                    </span>
                  ),
                )}
              </dd>
            </div>
          )}
          {elems.length > 0 && (
            <div className="mf-tl mf-c-el">
              <dt>要素</dt>
              <dd>
                {elems.map((e, i) => (
                  <Link key={i} href={e.href} className="mf-chip">
                    {e.name}
                  </Link>
                ))}
              </dd>
            </div>
          )}
        </dl>
      )}

      {tail && <div className="mf-btns">{tail}</div>}
    </div>
  );
}

/**
 * 説明文のコマ = 見本「B あらすじのコマ」(2026-10-08 ユーザ裁定)。 基本情報欄の続きのコマで、
 * 左上の写植箱は生成り(羅針盤に糸の無い項目と同じ)。 見出しは h2(頁の見出し = h1 題名 → h2 あらすじ → h2 通常版)。
 * 何を出すかは lib/mangaFacts.ts の pickDescription(説明文が主役・無い時だけキャッチ)。
 * ★説明文は全文を最初から見せる(畳まない)= SEO の約束。
 */
export function MangaSynopsis({ synopsis, catchCopy }: { synopsis?: string | null; catchCopy?: string | null }) {
  const d = pickDescription(synopsis, catchCopy);
  if (!d) return null;
  return (
    <section className="mf-syn">
      <h2>{d.label}</h2>
      <p>{d.text}</p>
    </section>
  );
}
