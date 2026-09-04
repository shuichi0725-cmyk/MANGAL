import { describe, expect, it } from "vitest";
import { decadeOf, parseHubParts, subLabel } from "./hubs";

describe("parseHubParts (ハブ面の catch-all URL 解釈)", () => {
  it("1要素 = 1頁目", () => {
    expect(parseHubParts(["weekly-shonen-jump"])).toEqual({ key: "weekly-shonen-jump", page: 1 });
  });
  it("2要素 = 続き頁(2以上)", () => {
    expect(parseHubParts(["kodansha", "2"])).toEqual({ key: "kodansha", page: 2 });
    expect(parseHubParts(["kodansha", "10"])).toEqual({ key: "kodansha", page: 10 });
  });
  it("1頁目の明示URL / 非数値 / 0 / 3要素 / placeholder は不正", () => {
    expect(parseHubParts(["kodansha", "1"])).toBeNull();
    expect(parseHubParts(["kodansha", "x"])).toBeNull();
    expect(parseHubParts(["kodansha", "0"])).toBeNull();
    expect(parseHubParts(["a", "2", "3"])).toBeNull();
    expect(parseHubParts(["_empty"])).toBeNull();
    expect(parseHubParts([])).toBeNull();
    expect(parseHubParts(undefined)).toBeNull();
  });
});

describe("genre sub helpers", () => {
  it("subLabel", () => {
    expect(subLabel("completed")).toBe("完結済み");
    expect(subLabel("1990s")).toBe("1990年代");
    expect(subLabel("199s")).toBeNull();
    expect(subLabel("ongoing")).toBeNull();
  });
  it("decadeOf", () => {
    expect(decadeOf(1995)).toBe(1990);
    expect(decadeOf(2000)).toBe(2000);
    expect(decadeOf(2026)).toBe(2020);
  });
});
