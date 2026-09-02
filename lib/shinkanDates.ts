/** /shinkan 系の純粋ヘルパー(fs非依存=client からも import 可)。 */
export type ShinkanItem = [string, number | null, string, string | null, string | null, string, string, string];
export type ShinkanMonth = { days: Record<string, ShinkanItem[]>; unknown: ShinkanItem[] };
/** 「詳細」リンク可否の判定器(Set でも {has} でも可) */
export type KnownSet = { has(slug: string): boolean };
export const KNOWN_ALL: KnownSet = { has: () => true };

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
export function jstDay(): number {
  return jstNow().getUTCDate();
}
export function ymLabel(ym: string): string {
  return `${ym.slice(0, 4)}年${Number(ym.slice(5))}月`;
}
export const WEEK_JA = ["日", "月", "火", "水", "木", "金", "土"];
export function weekdayOf(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return WEEK_JA[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
}
export function dateLabel(iso: string, withYear = false): string {
  const [y, m, d] = iso.split("-").map(Number);
  return `${withYear ? `${y}年` : ""}${m}月${d}日(${weekdayOf(iso)})`;
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
    for (const day of sortedDays(d)) {
      const iso = `${ym}-${day.padStart(2, "0")}`;
      if (iso >= start && iso <= end) out.push({ date: iso, items: d.days[day] });
    }
  }
  return out;
}
export function monthsCovering(start: string, end: string): string[] {
  return [...new Set([start.slice(0, 7), end.slice(0, 7)])].sort();
}

/** 日キー("01"/"1" 混在耐性)を数値順に */
export function sortedDays(d: ShinkanMonth): string[] {
  return Object.keys(d.days).sort((a, b) => Number(a) - Number(b));
}
export function monthCount(d: ShinkanMonth): number {
  return Object.values(d.days).reduce((s, v) => s + v.length, 0) + (d.unknown?.length ?? 0);
}

/** 月データの署名(冊数+日/slug/巻/題/書影/ISBN/著者のハッシュ)。build 時のHTMLと閲覧時のJSONの差分検知に使う。 */
export function monthSignature(d: ShinkanMonth): string {
  let h = 5381;
  let n = 0;
  const feed = (s: string) => {
    for (let i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0;
  };
  for (const day of sortedDays(d)) {
    for (const it of d.days[day]) {
      n++;
      feed(`${Number(day)}|${it[0]}|${it[1] ?? ""}|${it[2]}|${it[3] ?? ""}|${it[4] ?? ""}|${it[5]}`);
    }
  }
  for (const it of d.unknown ?? []) {
    n++;
    feed(`u|${it[0]}|${it[1] ?? ""}|${it[2]}|${it[3] ?? ""}|${it[4] ?? ""}|${it[5]}`);
  }
  return `${n}:${h.toString(16)}`;
}
