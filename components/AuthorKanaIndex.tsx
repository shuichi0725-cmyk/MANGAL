"use client";

import { useMemo, useState } from "react";
import { ChipButton } from "@/components/ui/Chip";

type AuthorEntry = { name: string; kana: string };

type Props = {
  authors: AuthorEntry[];
  selected: string[];
  onToggle: (name: string) => void;
};

// 五十音(行 → その行の音)。 カタカナ基準。
const GYO: { row: string; kana: string[] }[] = [
  { row: "ア", kana: ["ア", "イ", "ウ", "エ", "オ"] },
  { row: "カ", kana: ["カ", "キ", "ク", "ケ", "コ"] },
  { row: "サ", kana: ["サ", "シ", "ス", "セ", "ソ"] },
  { row: "タ", kana: ["タ", "チ", "ツ", "テ", "ト"] },
  { row: "ナ", kana: ["ナ", "ニ", "ヌ", "ネ", "ノ"] },
  { row: "ハ", kana: ["ハ", "ヒ", "フ", "ヘ", "ホ"] },
  { row: "マ", kana: ["マ", "ミ", "ム", "メ", "モ"] },
  { row: "ヤ", kana: ["ヤ", "ユ", "ヨ"] },
  { row: "ラ", kana: ["ラ", "リ", "ル", "レ", "ロ"] },
  { row: "ワ", kana: ["ワ", "ヲ", "ン"] },
];
const OTHER = "他"; // latin / 記号 / 読み無し

// 濁点・半濁点・小書き → 清音(行判定用)
const DAKU: Record<string, string> = {
  ガ: "カ", ギ: "キ", グ: "ク", ゲ: "ケ", ゴ: "コ",
  ザ: "サ", ジ: "シ", ズ: "ス", ゼ: "セ", ゾ: "ソ",
  ダ: "タ", ヂ: "チ", ヅ: "ツ", デ: "テ", ド: "ト",
  バ: "ハ", ビ: "ヒ", ブ: "フ", ベ: "ヘ", ボ: "ホ",
  パ: "ハ", ピ: "ヒ", プ: "フ", ペ: "ヘ", ポ: "ホ",
  ヴ: "ウ",
  ァ: "ア", ィ: "イ", ゥ: "ウ", ェ: "エ", ォ: "オ",
  ッ: "ツ", ャ: "ヤ", ュ: "ユ", ョ: "ヨ", ヮ: "ワ",
};
const KANA_TO_ROW: Record<string, string> = {};
for (const g of GYO) for (const k of g.kana) KANA_TO_ROW[k] = g.row;

/** 読み(or 名)の先頭 → 清音カタカナ。 カナでなければ null。 */
function baseKana(s: string): string | null {
  if (!s) return null;
  let c = s[0];
  if (c >= "ぁ" && c <= "ん") c = String.fromCharCode(c.charCodeAt(0) + 0x60); // ひら→カタ
  if (DAKU[c]) c = DAKU[c];
  return KANA_TO_ROW[c] ? c : null;
}

export default function AuthorKanaIndex({ authors, selected, onToggle }: Props) {
  const [openRow, setOpenRow] = useState<string | null>(null);
  const [openKana, setOpenKana] = useState<string | null>(null);

  // 著者を音単位でバケット化。 byRow[row] = 件数, byKana[音] = 著者[]
  const { byKana, otherList, rowCount } = useMemo(() => {
    const byKana = new Map<string, AuthorEntry[]>();
    const otherList: AuthorEntry[] = [];
    const rowCount = new Map<string, number>();
    for (const a of authors) {
      const b = baseKana(a.kana || a.name);
      if (b) {
        (byKana.get(b) ?? byKana.set(b, []).get(b)!).push(a);
        const row = KANA_TO_ROW[b];
        rowCount.set(row, (rowCount.get(row) ?? 0) + 1);
      } else {
        otherList.push(a);
      }
    }
    return { byKana, otherList, rowCount };
  }, [authors]);

  const shownAuthors: AuthorEntry[] =
    openRow === OTHER ? otherList : openKana ? byKana.get(openKana) ?? [] : [];

  const rowDef = GYO.find((g) => g.row === openRow);

  return (
    <div className="space-y-2">
      {/* 選択中の著者(削除可) */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selected.map((name) => (
            <ChipButton key={name} active onClick={() => onToggle(name)}>
              {name} ✕
            </ChipButton>
          ))}
        </div>
      )}

      {/* 第1段: 行(あかさたな…) */}
      <div className="flex flex-wrap gap-1">
        {GYO.map((g) => (
          <ChipButton
            key={g.row}
            active={openRow === g.row}
            onClick={() => {
              setOpenRow(openRow === g.row ? null : g.row);
              setOpenKana(null);
            }}
          >
            {g.row}
          </ChipButton>
        ))}
        {otherList.length > 0 && (
          <ChipButton
            active={openRow === OTHER}
            onClick={() => {
              setOpenRow(openRow === OTHER ? null : OTHER);
              setOpenKana(null);
            }}
          >
            A-Z他
          </ChipButton>
        )}
      </div>

      {/* 第2段: その行の音(あいうえお) */}
      {rowDef && (
        <div className="flex flex-wrap gap-1 pl-1">
          {rowDef.kana.map((k) => {
            const c = byKana.get(k)?.length ?? 0;
            return (
              <ChipButton
                key={k}
                active={openKana === k}
                onClick={() => setOpenKana(openKana === k ? null : k)}
              >
                {k}
                {c > 0 && <span className="text-[10px] opacity-60">{c}</span>}
              </ChipButton>
            );
          })}
        </div>
      )}

      {/* 第3段: 著者一覧 */}
      {shownAuthors.length > 0 && (
        <div className="max-h-56 overflow-y-auto rounded-card border border-[var(--color-line)] p-1.5 space-y-0.5">
          {shownAuthors.map((a) => (
            <label
              key={a.name}
              className="flex items-center gap-2 cursor-pointer px-1 py-0.5 rounded hover:bg-black/5"
            >
              <input
                type="checkbox"
                checked={selected.includes(a.name)}
                onChange={() => onToggle(a.name)}
              />
              <span>{a.name}</span>
              {a.kana && <span className="text-[11px] text-ink/40">{a.kana}</span>}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
