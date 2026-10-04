import { describe, expect, it } from "vitest";
import { bigCover, vcShard } from "./volCovers";

// ★分け方(公開slugのハッシュ)は生成側 scripts/_build-vol-covers.py の fnv1a(slug) % 64 と一致しなければならない
//   (ずれると本棚が別の1本を読み「書影がまだありません」になる)。 期待値は Python 側で計算した値。
describe("vcShard = Python の fnv1a % 64 と同じ", () => {
  it.each([
    ["tensei-shitara-slime-datta-ken", 23],
    ["goblin-slayer", 35],
    ["a", 44],
    ["urusei-yatsura", 14],
    ["0-shinohara", 5],
    ["mujintou-de-elf-to-kyoudou-seikatsu-attomaaku-comic", 31],
  ])("%s → %i", (slug, want) => {
    expect(vcShard(slug)).toBe(want);
  });
});

describe("bigCover", () => {
  it("楽天は _ex=600x600 にする", () => {
    expect(bigCover("https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/1/x.jpg?_ex=300x300")).toBe(
      "https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/1/x.jpg?_ex=600x600",
    );
  });
  it("楽天以外・null はそのまま", () => {
    expect(bigCover("https://example.com/a.jpg")).toBe("https://example.com/a.jpg");
    expect(bigCover(null)).toBeNull();
  });
});
