"use client";

import { useMemo, useState } from "react";
import { ChipButton } from "@/components/ui/Chip";

type AuthorEntry = { name: string; kana: string; count?: number };

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

/** 読みの2文字目 → 清音カタカナ(2音目チップ用)。 無し/カナ以外は "他"。 */
function secondKana(s: string): string {
  if (!s || s.length < 2) return "他";
  let c = s[1];
  if (c >= "ぁ" && c <= "ん") c = String.fromCharCode(c.charCodeAt(0) + 0x60);
  if (DAKU[c]) c = DAKU[c];
  return KANA_TO_ROW[c] ? c : "他";
}

// 2音目チップを出す規模の閾値(小さいバケツは従来どおり直接リスト)
const KANA2_THRESHOLD = 40;

export default function AuthorKanaIndex({ authors, selected, onToggle }: Props) {
  const [openRow, setOpenRow] = useState<string | null>(null);
  const [openKana, setOpenKana] = useState<string | null>(null);
  const [openKana2, setOpenKana2] = useState<string | null>(null);

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

  // ★2音目バケツ(2026-07-06): タ1164人→タカ312人のもう一段。清音化キー。
  const kana2Buckets = useMemo(() => {
    if (!openKana) return null;
    const bucket = byKana.get(openKana) ?? [];
    if (bucket.length < KANA2_THRESHOLD) return null;
    const m = new Map<string, AuthorEntry[]>();
    for (const a of bucket) {
      const k2 = secondKana(a.kana || a.name);
      (m.get(k2) ?? m.set(k2, []).get(k2)!).push(a);
    }
    return m;
  }, [openKana, byKana]);

  const baseList: AuthorEntry[] =
    openRow === OTHER
      ? otherList
      : openKana
        ? kana2Buckets
          ? openKana2
            ? kana2Buckets.get(openKana2) ?? []
            : []
          : byKana.get(openKana) ?? []
        : [];
  // ★作品数の多い順(高橋留美子が最上位に来る)。同数はヨミ順
  const shownAuthors = useMemo(
    () =>
      [...baseList].sort(
        (a, b) =>
          (b.count ?? 0) - (a.count ?? 0) ||
          (a.kana || a.name).localeCompare(b.kana || b.name, "ja"),
      ),
    [baseList],
  );

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
              setOpenKana2(null);
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
              setOpenKana2(null);
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
                onClick={() => { setOpenKana(openKana === k ? null : k); setOpenKana2(null); }}
              >
                {k}
                {c > 0 && <span className="text-[10px] opacity-60">{c}</span>}
              </ChipButton>
            );
          })}
        </div>
      )}

      {/* 第2.5段: 2音目チップ(大バケツのみ。タ→タカ) */}
      {kana2Buckets && (
        <div className="flex flex-wrap gap-1 pl-2">
          {Array.from(kana2Buckets.entries())
            .sort(([a], [b]) => (a === "他" ? 1 : b === "他" ? -1 : a.localeCompare(b, "ja")))
            .map(([k2, list]) => (
              <ChipButton
                key={k2}
                active={openKana2 === k2}
                onClick={() => setOpenKana2(openKana2 === k2 ? null : k2)}
              >
                {openKana}{k2 === "他" ? "-他" : k2}
                <span className="text-[10px] opacity-60">{list.length}</span>
              </ChipButton>
            ))}
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
              {(a.count ?? 0) > 1 && <span className="ml-auto text-[10px] tabular-nums text-ink/35">{a.count}</span>}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
