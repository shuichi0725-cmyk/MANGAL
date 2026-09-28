import { describe, expect, it } from "vitest";
import {
  type ShelfItem,
  STORAGE_KEY,
  countByShelf,
  decodeShelf,
  encodeShelf,
  importShelf,
  loadShelf,
  mergeSameSlug,
  moveItem,
  normalizeItems,
  ownedNote,
  parseMangaSlug,
  plaqueStats,
  putItem,
  removeItem,
  renameSlug,
  resolveMovedSlug,
  saveShelf,
  setOwned,
  shelfShareUrl,
  volumeTiles,
} from "./myShelf";

const T0 = 1_760_000_000_000; // 固定時刻(ms)
const item = (p: Partial<ShelfItem> & { slug: string }): ShelfItem => ({
  title: p.slug,
  cover: null,
  shelf: "wish",
  addedAt: T0,
  updatedAt: T0,
  ...p,
});

function memStore(init: Record<string, string> = {}) {
  const m = new Map(Object.entries(init));
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, v),
    raw: m,
  };
}

describe("保存・読み出し(端末)", () => {
  it("書いた棚をそのまま読める", () => {
    const st = memStore();
    const items = [item({ slug: "a", shelf: "own", owned: 10 }), item({ slug: "b", shelf: "curious" })];
    expect(saveShelf(st, items)).toBe(true);
    expect(loadShelf(st)).toEqual(items);
  });

  it("保存できない環境(例外)・壊れたJSON・未保存は黙って空の棚", () => {
    const throwing = {
      getItem: () => {
        throw new Error("SecurityError");
      },
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
    };
    expect(loadShelf(throwing)).toEqual([]);
    expect(saveShelf(throwing, [item({ slug: "a" })])).toBe(false);
    expect(loadShelf(memStore({ [STORAGE_KEY]: "{壊れた" }))).toEqual([]);
    expect(loadShelf(memStore())).toEqual([]);
    expect(loadShelf(null)).toEqual([]);
  });

  it("形の崩れた行は捨て、もってる以外の巻数・負の巻数は整える", () => {
    const out = normalizeItems(
      {
        items: [
          { slug: "ok", shelf: "own", owned: -3, title: "t", addedAt: T0, updatedAt: T0 },
          { slug: "", shelf: "own" },
          { slug: "x", shelf: "trash" },
          { slug: "w", shelf: "wish", owned: 5, addedAt: T0, updatedAt: T0 },
          "ごみ",
        ],
      },
      T0,
    );
    expect(out.map((x) => [x.slug, x.shelf, x.owned])).toEqual([
      ["ok", "own", 0],
      ["w", "wish", undefined],
    ]);
  });
});

describe("棚の操作", () => {
  it("しまう→同じ作品を別の棚へ(登録日は保つ)→巻数変更→取り出す", () => {
    let s = putItem([], { slug: "a", title: "A", cover: "c", shelf: "wish" }, T0);
    s = putItem(s, { slug: "b", title: "B", cover: null, shelf: "curious" }, T0 + 1);
    expect(s.map((x) => x.slug)).toEqual(["b", "a"]); // 新規は先頭
    s = moveItem(s, "a", "own", T0 + 2);
    expect(s.find((x) => x.slug === "a")).toMatchObject({ shelf: "own", owned: 0, addedAt: T0, updatedAt: T0 + 2 });
    s = setOwned(s, "a", 12, T0 + 3);
    expect(s.find((x) => x.slug === "a")?.owned).toBe(12);
    expect(setOwned(s, "b", 5)).toBe(s); // もってる以外は巻数を持たない
    s = moveItem(s, "a", "wish", T0 + 4);
    expect(s.find((x) => x.slug === "a")?.owned).toBeUndefined();
    expect(removeItem(s, "a").map((x) => x.slug)).toEqual(["b"]);
  });

  it("版を選んだ登録は版ラベルと登録時点の既刊を持ち、棚移動しても消えない", () => {
    let s = putItem([], { slug: "a", title: "A", cover: null, shelf: "own", owned: 3, edition: { label: "文庫版", total: 8 } }, T0);
    s = moveItem(s, "a", "wish", T0 + 1);
    expect(s[0]).toMatchObject({ edition: "文庫版", editionTotal: 8 });
    s = putItem(s, { slug: "a", title: "A", cover: null, shelf: "own", owned: 1, edition: null }, T0 + 2);
    expect(s[0].edition).toBeUndefined();
  });
});

describe("同じ slug の統合(改名・重複頁の統合)", () => {
  it("もってるが勝ち・巻数は大きい方・登録日は古い方", () => {
    const out = mergeSameSlug([
      item({ slug: "x", shelf: "own", owned: 4, addedAt: T0, updatedAt: T0 + 5 }),
      item({ slug: "y", shelf: "wish" }),
      item({ slug: "x", shelf: "own", owned: 9, addedAt: T0 - 10, updatedAt: T0 + 1 }),
      item({ slug: "x", shelf: "curious", addedAt: T0 + 2, updatedAt: T0 + 9, title: "新しい題" }),
    ]);
    expect(out).toHaveLength(2);
    expect(out[0]).toMatchObject({ slug: "x", shelf: "own", owned: 9, addedAt: T0 - 10, updatedAt: T0 + 9, title: "新しい題" });
  });

  it("もってるが無ければ後から更新した方の棚", () => {
    const out = mergeSameSlug([
      item({ slug: "x", shelf: "wish", updatedAt: T0 + 1 }),
      item({ slug: "x", shelf: "curious", updatedAt: T0 + 2 }),
    ]);
    expect(out).toEqual([expect.objectContaining({ slug: "x", shelf: "curious" })]);
  });

  it("旧 slug を新 slug へ付け替えると、既にある新 slug と1つにまとまる", () => {
    const s = [item({ slug: "old", shelf: "own", owned: 12 }), item({ slug: "new", shelf: "own", owned: 3 })];
    expect(renameSlug(s, "old", "new")).toEqual([expect.objectContaining({ slug: "new", owned: 12 })]);
  });
});

describe("slug の解決(301 転送)", () => {
  it("作品頁の URL から slug を取り出す", () => {
    expect(parseMangaSlug("https://mangal-db.com/manga/chicken-drop-zenya-no-monogatari")).toBe(
      "chicken-drop-zenya-no-monogatari",
    );
    expect(parseMangaSlug("/manga/abc.html")).toBe("abc");
    expect(parseMangaSlug("/manga/abc/")).toBe("abc");
    expect(parseMangaSlug("/manga/%E3%81%82")).toBe("あ");
    expect(parseMangaSlug("/author/abc")).toBeNull();
  });

  it("転送されて別の作品頁に着いた時だけ新 slug を返す", async () => {
    const pages: Record<string, { url: string; ok: boolean } | null> = {
      "/manga/chikin-drop-zenya-no-monogatari": { url: "https://x/manga/chicken-drop-zenya-no-monogatari", ok: true },
      "/manga/same": { url: "https://x/manga/same", ok: true },
      "/manga/gone": { url: "https://x/manga/gone", ok: false },
    };
    const fetchFinal = async (p: string) => pages[p] ?? null;
    expect(await resolveMovedSlug("chikin-drop-zenya-no-monogatari", fetchFinal)).toBe("chicken-drop-zenya-no-monogatari");
    expect(await resolveMovedSlug("same", fetchFinal)).toBeNull(); // 転送なし
    expect(await resolveMovedSlug("gone", fetchFinal)).toBeNull(); // 404
    expect(await resolveMovedSlug("unknown", fetchFinal)).toBeNull();
    expect(
      await resolveMovedSlug("err", async () => {
        throw new Error("offline");
      }),
    ).toBeNull();
  });
});

describe("もってるの札", () => {
  const ongoing = (n: number) => ({ max_edition_volumes: n, status: "ongoing" as const });
  const completed = (n: number) => ({ max_edition_volumes: n, status: "completed" as const });

  it("依頼書の表示例どおり", () => {
    expect(ownedNote({ owned: 10 }, ongoing(12)).text).toBe("10巻まで所持 → 11・12巻が出ています");
    expect(ownedNote({ owned: 10 }, ongoing(11)).text).toBe("10巻まで所持 → 11巻が出ています");
    expect(ownedNote({ owned: 3 }, ongoing(20)).text).toBe("3巻まで所持 → 4〜20巻が出ています");
    expect(ownedNote({ owned: 12 }, ongoing(12)).text).toBe("最新刊まで揃っています");
    expect(ownedNote({ owned: 12 }, completed(12)).text).toBe("全巻揃っています");
    expect(ownedNote({ owned: 10 }, completed(12)).text).toBe("完結済み・あと2冊で全巻");
    expect(ownedNote({ owned: 10 }, ongoing(12)).next).toEqual([11, 12]);
  });

  it("版を選んだ作品は登録時点の既刊で比べ、索引の巻数とは比べない", () => {
    const n = ownedNote({ owned: 8, editionTotal: 8 }, ongoing(30));
    expect(n).toMatchObject({ kind: "caught-up", total: 8, fixedEdition: true });
  });

  it("索引に無い(見つからない)作品は巻数だけ", () => {
    expect(ownedNote({ owned: 5 }, null)).toMatchObject({ kind: "unknown", text: "5巻まで所持" });
    expect(ownedNote({ owned: 0 }, ongoing(3)).text).toBe("1巻はまだ → 1〜3巻が出ています");
  });
});

describe("棚のURL(書き出し→取り込み)", () => {
  const mine = [
    item({ slug: "a", shelf: "own", owned: 10, updatedAt: T0 }),
    item({ slug: "b", shelf: "curious", updatedAt: T0 }),
    item({ slug: "c", shelf: "own", owned: 2, edition: "文庫版", editionTotal: 8, updatedAt: T0 }),
  ];

  it("書き出した文字列・URL から同じ棚に戻る(題名・書影は載せない)", () => {
    const token = encodeShelf(mine);
    const back = decodeShelf(token, T0)!;
    expect(back.map((x) => [x.slug, x.shelf, x.owned, x.edition, x.editionTotal])).toEqual([
      ["a", "own", 10, undefined, undefined],
      ["b", "curious", undefined, undefined, undefined],
      ["c", "own", 2, "文庫版", 8],
    ]);
    expect(back.every((x) => x.title === "" && x.cover === null)).toBe(true);
    const url = shelfShareUrl("https://mangal-preview.pages.dev", mine);
    expect(url).toMatch(/^https:\/\/mangal-preview\.pages\.dev\/shelf#s=v1\./);
    expect(decodeShelf(url, T0)).toEqual(back);
    expect(decodeShelf(`  ${token}\n`, T0)).toEqual(back); // 貼り付けの前後空白
  });

  it("読めない文字列は null", () => {
    expect(decodeShelf("こんにちは")).toBeNull();
    expect(decodeShelf("v1.@@@")).toBeNull();
    expect(decodeShelf("https://x/shelf#s=v2.abc")).toBeNull();
  });

  it("合流 = 両方を合わせ、同じ作品は統合規則(もってる優先・巻は大きい方)", () => {
    const incoming = [item({ slug: "a", shelf: "own", owned: 12, title: "" }), item({ slug: "z", shelf: "wish", title: "" })];
    const out = importShelf(mine, incoming, "merge");
    expect(out.map((x) => x.slug)).toEqual(["a", "b", "c", "z"]);
    expect(out[0]).toMatchObject({ owned: 12, title: "a" }); // 手元の題名の控えは残る
    expect(countByShelf(out)).toEqual({ own: 2, curious: 1, wish: 1 });
  });

  it("上書き = 持ってきた棚だけ(手元にあった題名の控えは引き継ぐ)", () => {
    const incoming = decodeShelf(encodeShelf([item({ slug: "b", shelf: "own", owned: 1 })]), T0)!;
    const out = importShelf(mine, incoming, "overwrite");
    expect(out).toEqual([expect.objectContaining({ slug: "b", shelf: "own", owned: 1, title: "b" })]);
  });
});

describe("番号タイル(もってるの段・10巻で1行)", () => {
  const nums = (t: ReturnType<typeof volumeTiles>) => t!.tiles.map((x) => x.n);
  const states = (t: ReturnType<typeof volumeTiles>) => t!.tiles.map((x) => x.state[0]).join("");

  it("40巻以下: 1巻(細枠)から既刊まで全部。所持=塗り・未所持=枠", () => {
    const t = volumeTiles(10, 12);
    expect(t!.band).toBeNull();
    expect(nums(t)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
    expect(states(t)).toBe("fooooooooomm"); // f=first o=owned m=missing
    expect(nums(volumeTiles(40, 40))).toHaveLength(40); // 40巻ちょうどは畳まない
  });

  it("41巻以上: 最後に持っている巻を含む10巻区切りの頭より前を帯に畳む(依頼書の例 160巻中140巻)", () => {
    const t = volumeTiles(140, 160);
    expect(t!.band).toEqual({ from: 2, to: 130, count: 129 });
    expect(nums(t)[0]).toBe(131); // 131 が格子の左端
    expect(nums(t)).toHaveLength(30);
    expect(states(t)).toBe("o".repeat(10) + "m".repeat(20));
    // こち亀型 = 全巻所持
    const k = volumeTiles(203, 203);
    expect(k!.band).toEqual({ from: 2, to: 200, count: 199 });
    expect(nums(k)).toEqual([201, 202, 203]);
    // 11巻ちょうど所持 = 2〜10巻を畳み、11 から
    expect(volumeTiles(11, 50)!.band).toEqual({ from: 2, to: 10, count: 9 });
  });

  it("owned=0: 畳まない・1巻は細枠のまま・残りは全部未所持", () => {
    expect(states(volumeTiles(0, 5))).toBe("fmmmm");
    const big = volumeTiles(0, 60);
    expect(big!.band).toBeNull();
    expect(nums(big)).toHaveLength(60);
  });

  it("owned=既刊: 全部所持(未所持タイル無し)。索引より多く持っていても持っている分は出す", () => {
    expect(states(volumeTiles(12, 12))).toBe("f" + "o".repeat(11));
    expect(nums(volumeTiles(14, 12))).toHaveLength(14);
  });

  it("既刊不明: タイルを出さない(null)", () => {
    expect(volumeTiles(5, null)).toBeNull();
    expect(volumeTiles(5, 0)).toBeNull();
  });
});

describe("銘板の数字", () => {
  it("もってる冊数 / 出ている続きの巻 / 全巻そろった作品(札と同じ既刊の規則)", () => {
    const facts: Record<string, { max_edition_volumes: number; status: "ongoing" | "completed" | "hiatus" }> = {
      a: { max_edition_volumes: 12, status: "ongoing" }, // 10/12 → 続き2
      b: { max_edition_volumes: 13, status: "completed" }, // 13/13 → 全巻
      c: { max_edition_volumes: 30, status: "completed" }, // 版で登録 8/8 → 全巻(索引の30とは比べない)
      d: { max_edition_volumes: 20, status: "completed" }, // 18/20 → 続き2・全巻ではない
    };
    const s = plaqueStats(
      [
        item({ slug: "a", shelf: "own", owned: 10 }),
        item({ slug: "b", shelf: "own", owned: 13 }),
        item({ slug: "c", shelf: "own", owned: 8, edition: "文庫版", editionTotal: 8 }),
        item({ slug: "d", shelf: "own", owned: 18 }),
        item({ slug: "lost", shelf: "own", owned: 5 }), // 索引に無い = 冊数だけ数える
        item({ slug: "w", shelf: "wish" }),
      ],
      (slug) => facts[slug] ?? null,
    );
    expect(s).toEqual({ ownedVolumes: 10 + 13 + 8 + 18 + 5, nextVolumes: 4, completeWorks: 2 });
  });
});
