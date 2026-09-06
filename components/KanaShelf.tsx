"use client";

import { useMemo } from "react";

/** 本屋の棚札ふうの50音索引つきリスト(2026-09-06 ユーザ要望
 *  「本屋みたいに簡単でよいので索引を付けたい。ローマ字/あ/い みたいな。
 *    3つをみっちり並べるより見やすく発見できるように」)。
 *
 *  - 索引 = ローマ字 + あ〜ん の**中身がある頭文字だけ**をチップで出す(空の棚札は出さない)。
 *  - 本文 = 頭文字ごとのセクション。中身は書影サムネ+題+著者+版情報の**1件1行**
 *    (旧=書影3列びっしり。ユーザいわく発見しづらい)。
 *  - 濁点・半濁点・小書きは親文字に寄せる(が→か、ぁ→あ)= 本屋の棚と同じ。
 *  ★並べ替えは呼び出し側の責任(= 既に50音順で渡す)。ここは束ねて見出しを付けるだけ。 */

/** [カタカナ, 表示ラベル(ひらがな), アンカーid] */
const KANA: Array<[string, string, string]> = [
  ["ア", "あ", "a"], ["イ", "い", "i"], ["ウ", "う", "u"], ["エ", "え", "e"], ["オ", "お", "o"],
  ["カ", "か", "ka"], ["キ", "き", "ki"], ["ク", "く", "ku"], ["ケ", "け", "ke"], ["コ", "こ", "ko"],
  ["サ", "さ", "sa"], ["シ", "し", "shi"], ["ス", "す", "su"], ["セ", "せ", "se"], ["ソ", "そ", "so"],
  ["タ", "た", "ta"], ["チ", "ち", "chi"], ["ツ", "つ", "tsu"], ["テ", "て", "te"], ["ト", "と", "to"],
  ["ナ", "な", "na"], ["ニ", "に", "ni"], ["ヌ", "ぬ", "nu"], ["ネ", "ね", "ne"], ["ノ", "の", "no"],
  ["ハ", "は", "ha"], ["ヒ", "ひ", "hi"], ["フ", "ふ", "fu"], ["ヘ", "へ", "he"], ["ホ", "ほ", "ho"],
  ["マ", "ま", "ma"], ["ミ", "み", "mi"], ["ム", "む", "mu"], ["メ", "め", "me"], ["モ", "も", "mo"],
  ["ヤ", "や", "ya"], ["ユ", "ゆ", "yu"], ["ヨ", "よ", "yo"],
  ["ラ", "ら", "ra"], ["リ", "り", "ri"], ["ル", "る", "ru"], ["レ", "れ", "re"], ["ロ", "ろ", "ro"],
  ["ワ", "わ", "wa"], ["ン", "ん", "n"],
];
const ROMAJI: [string, string, string] = ["#", "ローマ字", "az"];

/** 濁点・半濁点・小書き・旧かなを親文字へ寄せる(棚札の正規化) */
const FOLD: Record<string, string> = {
  ガ: "カ", ギ: "キ", グ: "ク", ゲ: "ケ", ゴ: "コ",
  ザ: "サ", ジ: "シ", ズ: "ス", ゼ: "セ", ゾ: "ソ",
  ダ: "タ", ヂ: "チ", ヅ: "ツ", デ: "テ", ド: "ト",
  バ: "ハ", ビ: "ヒ", ブ: "フ", ベ: "ヘ", ボ: "ホ",
  パ: "ハ", ピ: "ヒ", プ: "フ", ペ: "ヘ", ポ: "ホ",
  ァ: "ア", ィ: "イ", ゥ: "ウ", ェ: "エ", ォ: "オ",
  ャ: "ヤ", ュ: "ユ", ョ: "ヨ", ッ: "ツ", ヮ: "ワ", ヵ: "カ", ヶ: "ケ",
  ヴ: "ウ", ヰ: "イ", ヱ: "エ", ヲ: "オ",
};

/** 見出しかな(カタカナ1文字)を返す。かな以外(英字・数字・記号)は "#" = ローマ字棚。 */
export function kanaHead(s: string): string {
  const c0 = (s || "").trim().charAt(0);
  if (!c0) return "#";
  // ひらがな → カタカナ
  const c = c0 >= "ぁ" && c0 <= "ゖ" ? String.fromCharCode(c0.charCodeAt(0) + 0x60) : c0;
  const f = FOLD[c] ?? c;
  return KANA.some(([k]) => k === f) ? f : "#";
}

type Props<T> = {
  /** 既に50音順に並べ終えた行 */
  items: T[];
  /** その行のヨミ(title_kana)。空なら題名で代替して渡す */
  kanaOf: (t: T) => string;
  keyOf: (t: T) => string;
  render: (t: T) => React.ReactNode;
  /** 索引チップの上に出す説明(件数など) */
  caption?: React.ReactNode;
};

export default function KanaShelf<T>({ items, kanaOf, keyOf, render, caption }: Props<T>) {
  const groups = useMemo(() => {
    const by = new Map<string, T[]>();
    for (const it of items) {
      const h = kanaHead(kanaOf(it));
      const a = by.get(h);
      if (a) a.push(it);
      else by.set(h, [it]);
    }
    // 表示順 = ローマ字 → あ〜ん(中身がある棚だけ)
    return [ROMAJI, ...KANA]
      .map(([k, label, id]) => [label, id, by.get(k) ?? []] as [string, string, T[]])
      .filter(([, , list]) => list.length > 0);
  }, [items, kanaOf]);

  if (items.length === 0) return <p className="text-[13px] text-ink/60">該当なし</p>;

  return (
    <div>
      <div id="kana-index" className="scroll-mt-3 rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-2.5">
        {caption ? <p className="mb-1.5 text-[11px] text-ink/50">{caption}</p> : null}
        <nav aria-label="50音索引" className="flex flex-wrap gap-1">
          {groups.map(([label, id, list]) => (
            <a
              key={id}
              href={`#shelf-${id}`}
              className="spring-press rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)] px-2 py-1 text-[12px] font-bold leading-none hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
            >
              {label}
              <span className="ml-1 align-middle text-[9.5px] font-semibold tabular-nums text-ink/40">{list.length}</span>
            </a>
          ))}
        </nav>
      </div>

      {groups.map(([label, id, list]) => (
        <section key={id} id={`shelf-${id}`} className="mt-5 scroll-mt-3">
          <div className="flex items-center gap-2 border-b-2 border-[var(--color-accent)] pb-1">
            <span className="rounded bg-[var(--color-accent)] px-2 py-0.5 text-[13px] font-black leading-none text-[var(--color-on-accent)]">
              {label}
            </span>
            <span className="text-[11px] font-semibold tabular-nums text-ink/45">{list.length}点</span>
            <a href="#kana-index" className="ml-auto text-[10.5px] font-semibold text-ink/40 hover:text-[var(--color-accent)]">
              ↑ 索引
            </a>
          </div>
          <ul className="mt-2 grid grid-cols-1 gap-x-4 gap-y-2 md:grid-cols-2 xl:grid-cols-3">
            {list.map((t) => (
              <li key={keyOf(t)}>{render(t)}</li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
