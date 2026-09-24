import { afterEach, describe, expect, it, vi } from "vitest";
import { animeNavSeasons, currentSeasonKey, seasonReached } from "./animeSeason";

/** JSTの日時 → Date(UTC) */
function jst(y: number, m: number, d: number, h = 0): Date {
  return new Date(Date.UTC(y, m - 1, d, h) - 9 * 3600_000);
}

const ORDER = ["2026-spring", "2026-summer", "2026-fall", "2027-winter"];

afterEach(() => {
  vi.useRealTimers();
});

describe("アニメ季節の切り替え(ホームのコーナー/ナビ共通・2026-09-24)", () => {
  it("9/30 23時(JST)はまだ夏=次の季(秋)に達していない", () => {
    vi.useFakeTimers();
    vi.setSystemTime(jst(2026, 9, 30, 23));
    expect(currentSeasonKey(ORDER)).toBe("2026-summer");
    expect(seasonReached("2026-fall")).toBe(false);
  });

  it("10/1 0時(JST)で秋に達する=夏にビルドした頁もクライアントで秋へ切り替わる", () => {
    vi.useFakeTimers();
    vi.setSystemTime(jst(2026, 10, 1, 0));
    expect(seasonReached("2026-fall")).toBe(true);
    expect(seasonReached("2027-winter")).toBe(false);
  });

  it("夏のビルドでは 今季=夏・次の季=秋 を渡す", () => {
    vi.useFakeTimers();
    vi.setSystemTime(jst(2026, 9, 28));
    expect(animeNavSeasons(ORDER)).toEqual({ now: "2026-summer", next: "2026-fall" });
  });

  it("次の季がviewに無い時は next を返さない(存在しない頁へ飛ばさない)", () => {
    vi.useFakeTimers();
    vi.setSystemTime(jst(2027, 2, 1));
    expect(animeNavSeasons(ORDER)).toEqual({ now: "2027-winter", next: undefined });
  });
});
