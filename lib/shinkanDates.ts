/** /shinkan 系の純粋ヘルパー(fs非依存=client からも import 可)。 */
export type ShinkanItem = [string, number | null, string, string | null, string | null, string, string, string];
export type ShinkanMonth = { days: Record<string, ShinkanItem[]>; unknown: ShinkanItem[] };

/** JST の今 (UTC 値に +9h を足した Date。getUTC* で読む) */
export function jstNow(): Date {
  return new Date(Date.now() + 9 * 3600 * 1000);
}
export function jstYm(offset = 0): string {
  const t = jstNow();
  const m = t.getUTCMonth() + offset;
  const y = t.getUTCFullYear() + Math.floor(m / 12);
  return `${y}-${String((((m % 12) + 12) % 12) + 1).padStart(2, "0")}`;
}
export function ymLabel(ym: string): string {
  return `${ym.slice(0, 4)}年${Number(ym.slice(5))}月`;
}
export const WEEK_JA = ["日", "月", "火", "水", "木", "金", "土"];
export function dateLabel(iso: string, withYear = false): string {
  const [y, m, d] = iso.split("-").map(Number);
  const w = WEEK_JA[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return `${withYear ? `${y}年` : ""}${m}月${d}日(${w})`;
}

/** 今週(月曜〜日曜・JST)の範囲。 */
export function weekRange(base: Date = jstNow()): { start: string; end: string } {
  const dow = base.getUTCDay(); // 0=日
  const mon = new Date(Date.UTC(base.getUTCFullYear(), base.getUTCMonth(), base.getUTCDate() - ((dow + 6) % 7)));
  const sun = new Date(mon.getTime() + 6 * 86400 * 1000);
  const iso = (t: Date) => t.toISOString().slice(0, 10);
  return { start: iso(mon), end: iso(sun) };
}

/** 月JSON群から範囲内の (発売日, 冊) を発売日順に抜く(server/client 共通ロジック) */
export function rowsInRange(
  months: Record<string, ShinkanMonth | null | undefined>,
  start: string,
  end: string,
): Array<{ date: string; items: ShinkanItem[] }> {
  const out: Array<{ date: string; items: ShinkanItem[] }> = [];
  for (const ym of Object.keys(months).sort()) {
    const d = months[ym];
    if (!d) continue;
    for (const day of Object.keys(d.days).sort()) {
      const iso = `${ym}-${day.padStart(2, "0")}`;
      if (iso >= start && iso <= end) out.push({ date: iso, items: d.days[day] });
    }
  }
  return out;
}
export function monthsCovering(start: string, end: string): string[] {
  return [...new Set([start.slice(0, 7), end.slice(0, 7)])].sort();
}
