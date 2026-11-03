import type { Manga, Volume } from "./schema";

const STATUS_LABEL: Record<Manga["status"], string> = {
  ongoing: "連載中",
  completed: "完結",
  hiatus: "休載中",
};

export function yearStatusLabel(m: {
  year_started: number;
  year_ended: number | null;
  status: Manga["status"];
}): string {
  const start = m.year_started;
  const end = m.year_ended;
  const status = STATUS_LABEL[m.status];
  if (m.status === "ongoing") return `${start}〜 ${status}`;
  // ★始めと終わりが同じ年は1つだけ(2026-11-04): 「1989〜1989 完結」→「1989 完結」。全作品の46%(1巻もの等)が該当。
  if (end && end === start) return `${start} ${status}`;
  return end ? `${start}〜${end} ${status}` : `${start}〜 ${status}`;
}

// 読みの比較で無視する記号・空白(長音「ー」は読みの一部なので含めない)
const KANA_CMP_IGNORE = /[\s・･!！?？。、,，.．:：;；"'“”‘’「」『』()（）[\]［］〜~\-‐－—―=＝/／★☆♪♡♥]/g;
const kanaCmpForm = (s: string) =>
  s
    .normalize("NFKC")
    .replace(KANA_CMP_IGNORE, "")
    .replace(/[ぁ-ゖ]/g, (c) => String.fromCharCode(c.charCodeAt(0) + 0x60));

/** ヨミが題名をカタカナに直しただけ(記号・空白の差だけ)なら true = 題名の下に2回出さない
 *  (2026-11-04:「ベルセルク」の下に「ベルセルク」、「あしたのジョー」の下に「アシタノジョー」。全作品の21%)。
 *  「こんにちは / コンニチワ」のように読みが字面と違う時は false(=ヨミを出す意味がある)。 */
export function kanaSameAsTitle(title?: string | null, kana?: string | null): boolean {
  if (!title || !kana) return false;
  return kanaCmpForm(title) === kanaCmpForm(kana);
}

/** 一覧・グリッドの著者表記 = 原作者 → 作画 の順(書店・奥付と同じ並び)。同じ名前は1回だけ。
 *  ★2026-11-04: ジャンル面・ハブ・一覧表が authors(作画)だけを出していて、原作者のいる1万作で
 *    原作者が消えていた(ワンパンマン=村田雄介のみでONEなし)。作品頁(MangaFacts)は元から両方出す。 */
export function creditNames(m: {
  authors?: ReadonlyArray<{ name: string }> | null;
  original_authors?: ReadonlyArray<{ name: string }> | null;
}): string[] {
  const out: string[] = [];
  for (const a of [...(m.original_authors ?? []), ...(m.authors ?? [])]) {
    if (a?.name && !out.includes(a.name)) out.push(a.name);
  }
  return out;
}

/** "1997-12-24" → "1997.12.24"、"1997-12" → "1997.12"、"1997" → "1997"。 */
export function formatReleaseDate(date?: string | null): string {
  if (!date) return "";
  return date.replace(/-/g, ".");
}

export function volumeLabel(v: Volume): string {
  return v.volume_label ?? `第${v.number}巻`;
}
