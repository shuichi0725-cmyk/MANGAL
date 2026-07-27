import { describe, expect, it } from "vitest";
import { visibleSectionCount } from "./aiLeagueSchedule";

/** JSTの日付 → UTC ms */
function jst(y: number, m: number, d: number, h = 0): number {
  return Date.UTC(y, m - 1, d, h) - 9 * 3600_000;
}

describe("AI書評リーグ 週次公開式(単一の正・2026-07-27固定化)", () => {
  it("EPOCH当日(2026-07-05 日曜)=第1節のみ", () => {
    expect(visibleSectionCount(jst(2026, 7, 5))).toBe(1);
  });
  it("開始前でも最低1節(clamp)", () => {
    expect(visibleSectionCount(jst(2026, 7, 1))).toBe(1);
  });
  it("2026-07-27(第4週目)=第4節まで ★teaserズレ事件の再現ケース", () => {
    expect(visibleSectionCount(jst(2026, 7, 27))).toBe(4);
  });
  it("2026-08-01(土)=まだ第4節", () => {
    expect(visibleSectionCount(jst(2026, 8, 1, 23))).toBe(4);
  });
  it("2026-08-02(日曜0時)=第5節(約束のネバーランド)公開", () => {
    expect(visibleSectionCount(jst(2026, 8, 2))).toBe(5);
  });
  it("2026-08-23=第8節(seed最終節)", () => {
    expect(visibleSectionCount(jst(2026, 8, 23))).toBe(8);
  });
});
