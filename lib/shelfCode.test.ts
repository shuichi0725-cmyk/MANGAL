import { describe, expect, it } from "vitest";
import { type ShelfItem, encodeShelf, itemKey, mergeSameKey } from "./myShelf";
import { backupHeader, checkChars, codeSig, encodeShelfCode, mergeWithMark, readShelfCode, shelfCodeUrl } from "./shelfCode";
import { divide, kanaRow, type DivideEntry } from "./shelfDivide";

const T = 1_800_000_000_000;
const it_ = (o: Partial<ShelfItem> & { slug: string; shelf: ShelfItem["shelf"] }): ShelfItem => ({
  title: "",
  cover: null,
  addedAt: T - 9_000_000,
  updatedAt: T - 9_000_000,
  ...o,
});
const SHELF: ShelfItem[] = [
  it_({ slug: "kingdom", shelf: "own", owned: 79 }),
  it_({ slug: "berserk", shelf: "own", owned: 43, edition: "完全版", editionTotal: 12 }),
  it_({ slug: "dungeon-meshi", shelf: "wish" }),
  it_({ slug: "golden-kamuy", shelf: "curious" }),
];
const strip = (xs: ShelfItem[]) => xs.map(({ slug, shelf, owned, edition, editionTotal }) => ({ slug, shelf, owned, edition, editionTotal }));

describe("バックアップ文字列(M2)", () => {
  it("英数字と - _ . だけ(4つの OS で化けない)・書き出し→読み込みで同じ棚", async () => {
    const code = await encodeShelfCode(SHELF, "backup");
    expect(code).toMatch(/^M2[zp]\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]{4}$/);
    const r = await readShelfCode(code, T);
    expect(r.ok && r.kind).toBe("backup");
    expect(r.ok && strip(r.items)).toEqual(strip(SHELF));
  });

  it("時刻は入れない = 読み込んだ側の時刻になる", async () => {
    const r = await readShelfCode(await encodeShelfCode(SHELF, "backup"), T);
    expect(r.ok && r.items.every((x) => x.addedAt === T)).toBe(true);
  });

  it("旧 v1. より短い(圧縮+時刻なし)", async () => {
    const many = Array.from({ length: 30 }, (_, i) => it_({ slug: `some-long-manga-title-${i}`, shelf: "own", owned: i }));
    expect((await encodeShelfCode(many, "backup")).length).toBeLessThan(encodeShelf(many).length / 2);
  });

  it("コピペの崩れを吸う: 先頭行・改行の折り返し・空白・全角・前後の文・URL", async () => {
    const code = await encodeShelfCode(SHELF, "backup");
    const half = Math.floor(code.length / 2);
    const fw = code.replace(/[A-Za-z0-9]/g, (c) => String.fromCharCode(c.charCodeAt(0) + 0xfee0)); // 全角化
    for (const input of [
      `${backupHeader(SHELF, new Date(T))}\n${code}`,
      `${code.slice(0, half)}\n  ${code.slice(half)}`,
      fw,
      `これ私の棚です → ${code} よろしく`,
      shelfCodeUrl("https://mangal-db.com", code),
    ]) {
      const r = await readShelfCode(input, T);
      expect(r.ok, input.slice(0, 40)).toBe(true);
      expect(r.ok && strip(r.items)).toEqual(strip(SHELF));
    }
  });

  it("欠け・書き換え = broken(黙って違う棚を読まない)/ 何も無い = none", async () => {
    const code = await encodeShelfCode(SHELF, "backup");
    const body = code.split(".")[1];
    const flipped = code.replace(body, body.slice(0, 5) + (body[5] === "A" ? "B" : "A") + body.slice(6));
    expect(await readShelfCode(flipped, T)).toEqual({ ok: false, reason: "broken" });
    expect(await readShelfCode(code.slice(0, code.length - 10), T)).toEqual({ ok: false, reason: "broken" });
    expect(await readShelfCode("こんにちは", T)).toEqual({ ok: false, reason: "none" });
  });

  it("旧 v1.(棚のURL)も読める = 前のバックアップを捨てさせない", async () => {
    const v1 = encodeShelf(SHELF);
    for (const input of [v1, `https://mangal-db.com/shelf#s=${v1}`]) {
      const r = await readShelfCode(input, T);
      expect(r.ok && r.kind).toBe("v1");
      expect(r.ok && strip(r.items)).toEqual(strip(SHELF));
    }
  });

  it("先頭行 = いつの・何作の棚か", () => {
    expect(backupHeader(SHELF, new Date(2026, 10, 17))).toBe("MANGAL本棚 2026-11-17 4作");
  });

  it("検査文字は4文字・同じ中身なら同じ印", () => {
    expect(checkChars("abc")).toHaveLength(4);
    expect(codeSig("M2z.abc.defg")).toBe(codeSig("M2z.abc.defg"));
    expect(codeSig("M2z.abc.defg")).not.toBe(codeSig("M2z.abd.defg"));
  });
});

describe("おすすめ文字列(R2)", () => {
  it("作品と版だけ = 持っている巻数・棚は渡さない。 受け取ると「気になる」", async () => {
    const code = await encodeShelfCode(SHELF.slice(0, 2), "recommend");
    expect(code.startsWith("R2")).toBe(true);
    const r = await readShelfCode(code, T);
    expect(r.ok && r.kind).toBe("recommend");
    expect(r.ok && strip(r.items)).toEqual([
      { slug: "kingdom", shelf: "curious", owned: undefined, edition: undefined, editionTotal: undefined },
      { slug: "berserk", shelf: "curious", owned: undefined, edition: "完全版", editionTotal: undefined },
    ]);
  });
});

describe("取り込みで増えた本の印(②-5a)", () => {
  it("手元に無かった作品×版だけ addedAt = 取り込んだ時刻・数を返す", () => {
    const current = SHELF.slice(0, 2);
    const incoming = [it_({ slug: "kingdom", shelf: "own", owned: 80 }), it_({ slug: "vinland-saga", shelf: "curious" }), it_({ slug: "berserk", shelf: "curious" })];
    const { items, added } = mergeWithMark(current, incoming, (a, b) => mergeSameKey([...a, ...b]), itemKey, T);
    expect(added).toBe(2); // vinland-saga と berserk(版なし = 完全版とは別の1冊)
    const by = new Map(items.map((x) => [itemKey(x), x]));
    expect(by.get("vinland-saga")!.addedAt).toBe(T);
    expect(by.get("berserk")!.addedAt).toBe(T);
    expect(by.get("kingdom")!.addedAt).toBe(T - 9_000_000); // 前からある本は増えた本にしない
    expect(by.get("kingdom")!.owned).toBe(80);
  });
});

describe("自動の仕切り", () => {
  const e = (slug: string, facts: DivideEntry<string>["facts"], noteKind: string | null = null): DivideEntry<string> => ({ value: slug, facts, noteKind });
  const es = [
    e("kingdom", { status: "ongoing", genres: ["action", "historical"], author: { name: "原泰久", kana: "ハラヤスヒサ" }, publisher: "shueisha", titleKana: "キングダム" }, "behind"),
    e("berserk", { status: "ongoing", genres: ["action", "fantasy"], author: { name: "三浦建太郎", kana: "ミウラケンタロウ" }, publisher: "hakusensha", titleKana: "ベルセルク" }, "caught-up"),
    e("dungeon-meshi", { status: "completed", genres: ["fantasy", "gourmet"], author: { name: "九井諒子", kana: "クイリョウコ" }, publisher: "kadokawa", titleKana: "ダンジョンメシ" }, "complete"),
    e("csm", { status: "completed", genres: ["action"], author: { name: "藤本タツキ", kana: "フジモトタツキ" }, publisher: "shueisha", titleKana: "チェンソーマン" }, "complete-behind"),
    e("gone", null, "unknown"),
  ];
  const ids = (s: { label: string; entries: DivideEntry<string>[] }[]) => s.map((x) => [x.label, x.entries.map((y) => y.value)]);

  it("なし = 1つのまま", () => {
    expect(divide(es, "none")).toHaveLength(1);
  });
  it("続き・状態(もってる)= 続きあり → 最新まで → 完結全巻 → 不明", () => {
    expect(ids(divide(es, "state"))).toEqual([
      ["続きの巻あり", ["kingdom", "csm"]],
      ["連載中・最新巻まで所持", ["berserk"]],
      ["完結・全巻所持", ["dungeon-meshi"]],
      ["巻数の記録なし", ["gone"]],
    ]);
  });
  it("ジャンル = 1作品1か所・この棚で多いジャンルへ寄せる・未設定は最後", () => {
    const s = divide(es, "genre", { genre: (k) => ({ action: "アクション", fantasy: "ファンタジー" })[k] });
    expect(ids(s)).toEqual([
      ["アクション", ["kingdom", "berserk", "csm"]],
      ["ファンタジー", ["dungeon-meshi"]],
      ["ジャンル未設定", ["gone"]],
    ]);
  });
  it("著者 = ヨミ順 / 出版社 = 多い順 / 50音 = 行ごと", () => {
    expect(divide(es, "author").map((x) => x.label)).toEqual(["九井諒子", "原泰久", "藤本タツキ", "三浦建太郎", "著者不明"]);
    expect(divide(es, "publisher", { publisher: (k) => ({ shueisha: "集英社" })[k] }).map((x) => x.label)).toEqual(["集英社", "hakusensha", "kadokawa", "出版社不明"]);
    expect(ids(divide(es, "kana"))).toEqual([
      ["カ行", ["kingdom"]],
      ["タ行", ["dungeon-meshi", "csm"]],
      ["ハ行", ["berserk"]],
      ["英数・記号", ["gone"]],
    ]);
  });
  it("50音の行 = ひらがな・濁点・半角も同じ行", () => {
    expect(kanaRow("がっこう")).toBe("カ行");
    expect(kanaRow("ﾊﾟﾗﾚﾙ")).toBe("ハ行");
    expect(kanaRow("ヴァンパイア")).toBe("ア行");
    expect(kanaRow("ONE")).toBe("英数・記号");
    expect(kanaRow(undefined)).toBe("英数・記号");
  });
});
