import { describe, it, expect } from "vitest";
import { VolumeSchema } from "./schema";

// ★番外編の「.5 巻」を通す規則の番人(2026-09-06)。
//   実例 = トリニティセブン『七人の魔道士と日常風景 15.5』(9784040721446)。
//   NDL の dcndl:volume も "15.5" で、本編15巻と16巻の間に入る番外編。
//   VolumeSchema が int() のままだと **その頁が丸ごとビルドskip=404** になる
//   ([[search_404_build_skip_validation]] の型)。逆に小数を無制限に許すと誤記が通るので
//   「整数 か .5」だけに絞る。同じ規則が種4 seed lint(_check-seeds.py)と
//   反映ゲート(_reflect-targeted.py)にも入っている = 3か所を揃えて動かすこと。
describe("巻番号: 整数 か .5 の半端巻だけ許す", () => {
  it.each([0, 1, 15, 34])("整数 %s は通る", (n) => {
    expect(VolumeSchema.safeParse({ number: n }).success).toBe(true);
  });

  it.each([0.5, 2.5, 15.5])(".5 の半端巻 %s は通る", (n) => {
    expect(VolumeSchema.safeParse({ number: n }).success).toBe(true);
  });

  it.each([15.3, 0.25, -1, -0.5])("誤記 %s は弾く", (n) => {
    expect(VolumeSchema.safeParse({ number: n }).success).toBe(false);
  });

  it("15 と 15.5 と 16 が同じ版に並存できる", () => {
    const vols = [{ number: 15 }, { number: 15.5 }, { number: 16 }];
    expect(vols.every((v) => VolumeSchema.safeParse(v).success)).toBe(true);
  });
});
