import type { Manga, Volume } from "./schema";

const STATUS_LABEL: Record<Manga["status"], string> = {
  ongoing: "連載中",
  completed: "完結",
  hiatus: "休載中",
};

export function yearStatusLabel(m: Manga): string {
  const start = m.year_started;
  const end = m.year_ended;
  const status = STATUS_LABEL[m.status];
  if (m.status === "ongoing") return `${start}〜 ${status}`;
  return end ? `${start}〜${end} ${status}` : `${start}〜 ${status}`;
}

/** "1997-12-24" → "1997.12.24"、"1997-12" → "1997.12"、"1997" → "1997"。 */
export function formatReleaseDate(date?: string | null): string {
  if (!date) return "";
  return date.replace(/-/g, ".");
}

export function volumeLabel(v: Volume): string {
  return `第${v.number}巻`;
}
