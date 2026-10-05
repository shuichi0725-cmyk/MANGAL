import { describe, expect, it } from "vitest";
import type { MangaListItem } from "../../lib/schema";
import {
  KINDS,
  TONES,
  allowedSpreads,
  RING_GAP,
  angleGap,
  buildGraph,
  defaultSpread,
  drawUnit,
  weightedPick,
  UNIT_MAX,
  neighborhood,
  pickTone,
  placeRing,
  resolveSpread,
  rng,
  spreadPositions,
  stageGeom,
  toneOrder,
  toneQ,
  type Kind,
  type RingEntry,
  type Spread,
  EMPTY_MIX,
  mixCands,
  mixCounts,
  mixKey,
  mixUnit,
  islandPages,
  regenreKeys,
  regenreLabel,
  regenreUnit,
  themeIslands,
} from "./compass";

function book(slug: string, o: Partial<MangaListItem> = {}): MangaListItem {
  return {
    slug,
    title: slug,
    title_kana: slug,
    cover: `https://example.test/${slug}.jpg`,
    catch: `${slug} のキャッチ`,
    year_started: 2000,
    year_ended: null,
    status: "ongoing",
    authors: [{ name: `作者-${slug}` }],
    original_authors: [],
    genres: [],
    themes: [],
    demographic: "shounen",
    publisher: "p",
    publishers: ["p"],
    total_volumes: 1,
    max_edition_volumes: 1,
    popularity: 100,
    ...o,
  } as MangaListItem;
}

const T = ["陰謀", "政治", "学園", "魔法", "料理"];

describe("逆引き表", () => {
  it("書影とキャッチの両方がある作品だけを対象にし、全作品は all で引ける", () => {
    const g = buildGraph([
      book("a"),
      book("no-cover", { cover: null }),
      book("no-catch", { catch: undefined }),
    ]);
    expect(g.items.map((m) => m.slug)).toEqual(["a"]);
    expect(g.all.has("no-cover")).toBe(true);
    expect(g.byAuthor.get("作者-no-cover")).toBeUndefined();
  });
});

describe("周りの本(つながりの計算)", () => {
  it("1冊は最初に当てはまった種類にだけ入る(作者 > 同じ雑誌 > 同じ年 > 要素)", () => {
    const c = book("c", {
      authors: [{ name: "甲" }],
      magazine: "jump",
      year_started: 2016,
      themes: T,
    });
    // 作者も雑誌も年も要素も重なる本 → 作者だけ
    const all4 = book("all4", {
      authors: [{ name: "甲" }],
      magazine: "jump",
      year_started: 2016,
      themes: T,
      popularity: 9000,
    });
    // 雑誌と年と要素が重なる本 → 同じ雑誌
    const mag = book("mag", {
      magazine: "jump",
      year_started: 2016,
      themes: T,
      popularity: 9000,
    });
    // 年と要素が重なる本 → 同じ年
    const year = book("year", {
      year_started: 2016,
      themes: T,
      popularity: 9000,
    });
    // 要素だけ
    const elem = book("elem", {
      year_started: 1990,
      themes: T,
      popularity: 9000,
    });
    const g = buildGraph([c, all4, mag, year, elem]);
    const { ring } = neighborhood(g, c, (k) =>
      k === "jump" ? "週刊少年ジャンプ" : k,
    );
    const kindOf = Object.fromEntries(ring.map((r) => [r.slug, r.kind]));
    expect(kindOf).toEqual({
      all4: "author",
      mag: "mag",
      year: "year",
      elem: "elem",
    });
    expect(ring.map((r) => r.label)).toEqual([
      "作者 甲",
      "週刊少年ジャンプ",
      "2016年に開始",
      "陰謀・政治",
    ]);
  });

  it("★周り=10枠(種類ごと2枠)。 候補の無い種類(ここではジャンル)の枠は、他の種類の3冊目で埋める", () => {
    const c = book("c", {
      authors: [{ name: "甲" }],
      magazine: "jump",
      year_started: 2016,
      themes: T,
    });
    const list = [c];
    for (let i = 0; i < 5; i++)
      list.push(book(`a${i}`, { authors: [{ name: "甲" }] }));
    for (let i = 0; i < 5; i++)
      list.push(book(`m${i}`, { magazine: "jump", themes: T.slice(0, 2) }));
    for (let i = 0; i < 5; i++)
      list.push(book(`y${i}`, { year_started: 2016, themes: T.slice(0, 2) }));
    for (let i = 0; i < 5; i++)
      list.push(book(`e${i}`, { themes: T.slice(0, 3), popularity: 5000 }));
    const { ring } = neighborhood(buildGraph(list), c);
    const count = (xs: readonly { kind: string }[], k: string) =>
      xs.filter((r) => r.kind === k).length;
    // 計算側は各種類 RING_PICK(=4)冊まで持つ
    expect(KINDS.map((k) => count(ring, k))).toEqual([4, 4, 4, 4]);
    const placed = placeRing(ring, null, null, 118, 150);
    expect(placed).toHaveLength(10);
    // ジャンルの2枠(北東)は、埋める順(ジャンル→要素→年→雑誌→作者)で 要素・年 の3冊目が使う
    expect(KINDS.map((k) => count(placed, k))).toEqual([2, 2, 3, 3]);
    expect(ring.some((r) => r.slug === "c")).toBe(false);
  });

  it("★ジャンルも周りに出る(ラベル=共通のジャンル名)", () => {
    const c = book("c", { genres: ["historical", "samurai", "action"] });
    const list = [c];
    for (let i = 0; i < 3; i++) list.push(book(`g${i}`, { genres: ["historical", "samurai", "action"] }));
    const { ring } = neighborhood(buildGraph(list), c, (k) => k, {
      genreName: (k) => ({ historical: "歴史", samurai: "時代劇", action: "アクション" })[k] ?? k,
    });
    const gs = ring.filter((r) => r.kind === "genre");
    expect(gs.length).toBe(3);
    expect(gs[0].label).toBe("歴史・時代劇");
  });

  it("条件: 雑誌・年は共通の要素2以上、要素は3以上かつ popularity > 3000", () => {
    const c = book("c", { magazine: "jump", year_started: 2016, themes: T });
    const g = buildGraph([
      c,
      book("m1", { magazine: "jump", themes: T.slice(0, 1) }), // 共通1 → 出ない
      book("y1", { year_started: 2016, themes: T.slice(0, 1) }), // 共通1 → 出ない
      book("e-low", { themes: T.slice(0, 4), popularity: 3000 }), // 人気3000ちょうど → 出ない
      book("e2", { themes: T.slice(0, 2), popularity: 9000 }), // 共通2 → 出ない
    ]);
    expect(neighborhood(g, c).ring).toEqual([]);
  });

  it("並び順 = 共通の要素の数 → popularity", () => {
    const c = book("c", { magazine: "jump", themes: T });
    const g = buildGraph([
      c,
      book("two-hi", {
        magazine: "jump",
        themes: T.slice(0, 2),
        popularity: 99999,
      }),
      book("four", { magazine: "jump", themes: T.slice(0, 4), popularity: 10 }),
      book("three", {
        magazine: "jump",
        themes: T.slice(0, 3),
        popularity: 10,
      }),
    ]);
    expect(neighborhood(g, c).ring.map((r) => r.slug)).toEqual([
      "four",
      "three",
      "two-hi",
    ]);
    expect(
      placeRing(neighborhood(g, c).ring, null, null, 118, 150).map(
        (r) => r.slug,
      ),
    ).toEqual(["four", "three", "two-hi"]); // 空き枠を3冊目で埋める
  });
});

describe("広げる単位", () => {
  it("作者は作者名ごとに全作品、雑誌・年は共通の要素1以上、要素は作品数の多い順に4つ", () => {
    const c = book("c", {
      authors: [{ name: "甲" }, { name: "乙" }],
      magazine: "jump",
      year_started: 2016,
      themes: T,
    });
    const list = [c];
    list.push(book("a-no-theme", { authors: [{ name: "甲" }] })); // 共通の要素0でも作者単位には入る
    list.push(book("b1", { authors: [{ name: "乙" }] }));
    list.push(book("m0", { magazine: "jump" })); // 共通0 → 雑誌単位に入らない
    list.push(book("m1", { magazine: "jump", themes: ["陰謀"] }));
    list.push(book("y1", { year_started: 2016, themes: ["政治"] }));
    // 作品数: 料理5 > 魔法4 > 学園3 > 政治2(+y1) > 陰謀(m1)…
    for (let i = 0; i < 5; i++)
      list.push(book(`cook${i}`, { themes: ["料理"] }));
    for (let i = 0; i < 4; i++)
      list.push(book(`magic${i}`, { themes: ["魔法"] }));
    for (let i = 0; i < 3; i++)
      list.push(book(`school${i}`, { themes: ["学園"] }));
    list.push(book("pol", { themes: ["政治"] }));
    const { units } = neighborhood(buildGraph(list), c, (k) =>
      k === "jump" ? "週刊少年ジャンプ" : k,
    );
    const byKey = Object.fromEntries(
      units.map((u) => [u.key, u.items.map((i) => i.slug)]),
    );
    expect(byKey["author:甲"]).toEqual(["a-no-theme"]);
    expect(byKey["author:乙"]).toEqual(["b1"]);
    expect(byKey["mag:jump"]).toEqual(["m1"]);
    expect(byKey["year:2016"]).toEqual(["y1"]);
    expect(units.filter((u) => u.kind === "elem").map((u) => u.label)).toEqual([
      "料理",
      "魔法",
      "学園",
      "政治",
    ]);
    expect(units.find((u) => u.key === "mag:jump")?.label).toBe(
      "週刊少年ジャンプ",
    );
  });

  it("単位は候補全体を持ち、画面に出す24冊は drawUnit で引く(中央の本自身は含まない)", () => {
    const c = book("c", { authors: [{ name: "甲" }] });
    const list = [c];
    for (let i = 0; i < 40; i++)
      list.push(book(`a${i}`, { authors: [{ name: "甲" }] }));
    const u = neighborhood(buildGraph(list), c).units.find(
      (x) => x.key === "author:甲",
    )!;
    expect(u.items.length).toBe(40);
    expect(u.items.some((i) => i.slug === "c")).toBe(false);
    expect(drawUnit(u, rng("x")).length).toBe(UNIT_MAX);
  });

  it("★ジャンル: 重なり75%以上 → 24冊に届かなければ60% → 50%(ラベルで段階が分かる)", () => {
    const c = book("c", { genres: ["action", "drama", "horror", "samurai"] });
    const list = [c];
    // 75%(3/4共通+同数=3/5=0.6…)を避けて段階を作る: 完全一致 3冊 / 3共通(0.6) 30冊
    for (let i = 0; i < 3; i++) list.push(book(`same${i}`, { genres: ["action", "drama", "horror", "samurai"] }));
    for (let i = 0; i < 30; i++) list.push(book(`near${i}`, { genres: ["action", "drama", "horror", "comedy"] }));
    list.push(book("far", { genres: ["action"] })); // 1/4 = 0.25 は出ない
    const u = neighborhood(buildGraph(list), c).units.find((x) => x.kind === "genre")!;
    expect(u.label).toBe("似たジャンル"); // 75%では3冊しか無い → 60%へ下げた
    expect(u.items.length).toBe(33);
    expect(u.items.some((i) => i.slug === "far")).toBe(false);
    // 近い(完全一致)ほど score が高い = 先頭に来る
    expect(u.items.slice(0, 3).every((i) => i.slug.startsWith("same"))).toBe(true);
  });

  it("ジャンルが75%以上で24冊そろえば下げない", () => {
    const c = book("c", { genres: ["comedy"] });
    const list = [c];
    for (let i = 0; i < 30; i++) list.push(book(`g${i}`, { genres: ["comedy"] }));
    const u = neighborhood(buildGraph(list), c).units.find((x) => x.kind === "genre")!;
    expect(u.label).toBe("よく似たジャンル");
  });

  it("★くじ: 近い本ほど当たりやすい(人気は使わない)・非復元・rand 無しは先頭から", () => {
    const xs = [...Array(10)].map((_, i) => ({ id: i, score: i === 0 ? 5 : 0 }));
    expect(weightedPick(xs, (x) => x.score, 3).map((x) => x.id)).toEqual([0, 1, 2]);
    let hit = 0;
    const r = rng("w");
    for (let t = 0; t < 400; t++) if (weightedPick(xs, (x) => x.score, 1, r)[0].id === 0) hit++;
    // 重み 216 対 1×9 = 約96% で近い本
    expect(hit).toBeGreaterThan(340);
    const all = weightedPick(xs, (x) => x.score, 10, rng("z")).map((x) => x.id);
    expect(new Set(all).size).toBe(10);
  });

  it("★drawUnit: 旅で辿った本は必ず外す・引き直しは直前の24冊を外す(足りる時だけ)", () => {
    const c = book("c", { authors: [{ name: "甲" }] });
    const list = [c];
    for (let i = 0; i < 60; i++) list.push(book(`a${i}`, { authors: [{ name: "甲" }] }));
    const u = neighborhood(buildGraph(list), c).units.find((x) => x.key === "author:甲")!;
    const first = drawUnit(u, rng("1"), new Set(["a0", "a1"]));
    expect(first.some((i) => i.slug === "a0" || i.slug === "a1")).toBe(false);
    const again = drawUnit(u, rng("2"), new Set(["a0", "a1"]), new Set(first.map((i) => i.slug)));
    expect(again.some((i) => first.some((f) => f.slug === i.slug))).toBe(false);
    // 候補が少ない時は直前の本も使う(24冊を割らない)
    const small = { ...u, items: u.items.slice(0, 30) };
    const s1 = drawUnit(small, rng("3"));
    expect(drawUnit(small, rng("4"), new Set(), new Set(s1.map((i) => i.slug))).length).toBe(24);
  });
});

describe("来た道", () => {
  const full: RingEntry[] = [];
  for (const k of KINDS)
    for (let i = 0; i < 3; i++)
      full.push({ slug: `${k}${i}`, kind: k, label: k, shared: 0 });

  it("★前の中央は来た方向の反対側に残る(周りの本の条件に当てはまっても枠は使わず、枠は控えで埋める)", () => {
    // 作者の糸で北から来た = 前の中央は新しい中央の作者でもある(ほぼ必ず起きる)
    const ring: RingEntry[] = [
      { slug: "prev", kind: "author", label: "作者 甲", shared: 0 },
      { slug: "next-author", kind: "author", label: "作者 甲", shared: 0 },
    ];
    const p = placeRing(ring, "prev", 90, 118, 150);
    expect(p.find((o) => o.slug === "next-author")).toMatchObject({
      kind: "author",
      ang: -90,
      back: false,
    });
    const back = p.find((o) => o.slug === "prev");
    expect(back).toMatchObject({ kind: "back", back: true, ang: 90 });
    expect(back?.dy).toBeCloseTo(150);
    expect(p).toHaveLength(2);
  });

  it("どの方向から来ても、来た道はすべり終えた位置のまま・周りの本と重ならない", () => {
    // ★2026-09-29 書影を大きくした(周りの本 58×81)ので、実際のスマホの舞台の楕円で確かめる
    const g = stageGeom(360, 504);
    for (let from = -180; from < 180; from += 5) {
      const p = placeRing(full, "prev", from + 180, g.rx, g.ry);
      const back = p.find((o) => o.back);
      expect(angleGap(back!.ang, from + 180)).toBe(0);
      expect(p.filter((o) => !o.back)).toHaveLength(9); // 来た道が1枠使う = 画面は10冊
      for (let i = 0; i < p.length; i++)
        for (let j = i + 1; j < p.length; j++) {
          const overlap =
            Math.abs(p[i].dx - p[j].dx) < RING_GAP.w - 0.5 &&
            Math.abs(p[i].dy - p[j].dy) < RING_GAP.h - 0.5;
          expect(overlap, `from ${from}: ${p[i].slug}/${p[j].slug}`).toBe(
            false,
          );
        }
    }
    expect(angleGap(350, 10)).toBe(20);
  });
});

describe("4つの広げ方", () => {
  const geom = stageGeom(360, 544);
  const items = Array.from({ length: 24 }, (_, i) => ({
    slug: `b${i}`,
    year: 1990 + (i % 12),
  }));
  const inside = (p: { x: number; y: number; w: number; h: number }) =>
    p.x - p.w / 2 >= 0 &&
    p.x + p.w / 2 <= geom.W &&
    p.y - p.h / 2 >= 0 &&
    p.y + p.h / 2 <= geom.H;

  it("★同じ年の糸では年表を選べない(既定は星屑・覚えた値が年表でも使わない)", () => {
    expect(allowedSpreads("year")).not.toContain("time");
    expect(resolveSpread("year", "time")).toBe("dust");
    for (const k of ["author", "mag", "elem"] as Kind[])
      expect(allowedSpreads(k)).toContain("time");
  });

  it("初期値はどの糸も星屑・選べるのは星屑と年表だけ(扇・同心円は覚えていても星屑に戻る)", () => {
    expect(KINDS.map(defaultSpread)).toEqual(["dust", "dust", "dust", "dust"]);
    expect(resolveSpread("elem", "time")).toBe("time");
    expect(resolveSpread("elem", "fan")).toBe("dust");
    expect(resolveSpread("mag", "ring")).toBe("dust");
    expect(resolveSpread("elem", "nonsense")).toBe("dust");
  });

  const noOverlap = (P: { x: number; y: number; w: number; h: number }[]) => {
    for (let i = 0; i < P.length; i++)
      for (let j = i + 1; j < P.length; j++)
        if (
          Math.abs(P[i].x - P[j].x) < (P[i].w + P[j].w) / 2 &&
          Math.abs(P[i].y - P[j].y) < (P[i].h + P[j].h) / 2
        )
          return false;
    return true;
  };

  it("方角に扇: 近い本8冊が大きく・糸の方角に寄る・重ならない(入りきらない分は方角から遠い側へ続く)", () => {
    for (const [w, h] of [
      [360, 504],
      [390, 560],
      [412, 620],
    ] as const) {
      const g = stageGeom(w, h);
      const r = spreadPositions("author", items, "fan", g, 2000, "k");
      expect(r.P).toHaveLength(24);
      expect(r.P.slice(0, 8).every((p) => p.w === 44)).toBe(true);
      expect(r.P.slice(8, 16).every((p) => p.w === 38)).toBe(true);
      expect(r.P.slice(16).every((p) => p.w === 33)).toBe(true);
      // 作者 = 北: 近い8冊は中央より上
      expect(r.P.slice(0, 8).every((p) => p.y < g.CY)).toBe(true);
      expect(noOverlap([...r.P, r.center])).toBe(true);
      expect(r.center).toMatchObject({ x: g.CX, y: g.CY, w: 72, h: 100 });
    }
  });

  it("同心円: 全周に置く・重ならない", () => {
    for (const [w, h] of [
      [360, 504],
      [390, 560],
      [412, 620],
    ] as const) {
      const g = stageGeom(w, h);
      const r = spreadPositions("mag", items, "ring", g, 2000, "k");
      expect(r.P).toHaveLength(24);
      expect(r.P.some((p) => p.y > g.CY) && r.P.some((p) => p.y < g.CY)).toBe(
        true,
      );
      expect(r.P.some((p) => p.x > g.CX) && r.P.some((p) => p.x < g.CX)).toBe(
        true,
      );
      expect(noOverlap([...r.P, r.center])).toBe(true);
    }
  });

  it("年表: 横軸が年(左が古い)・同じ列は下から積む(1列7冊まで)・中央は上へ", () => {
    const same = Array.from({ length: 12 }, (_, i) => ({
      slug: `s${i}`,
      year: 2001,
    }));
    const r = spreadPositions(
      "author",
      [...same, { slug: "old", year: 1980 }, { slug: "new", year: 2020 }],
      "time",
      geom,
      2001,
      "k",
    );
    const col = r.P.filter((p) => p.slug.startsWith("s"));
    expect(col.length).toBeLessThanOrEqual(7);
    expect(col[0].y).toBeGreaterThan(col[1].y); // 下ほど近い
    const x = (s: string) => r.P.find((p) => p.slug === s)!.x;
    expect(x("old")).toBeLessThan(x("s0"));
    expect(x("s0")).toBeLessThan(x("new"));
    expect(r.center.y).toBeLessThan(geom.CY);
    expect(r.axisY).toBeDefined();
    expect(r.ticks?.[0].year).toBe(1980);
  });

  it("星屑: 種が同じなら毎回同じ・重ならない・近い本ほど大きい", () => {
    const a = spreadPositions("elem", items, "dust", geom, 2000, "elem:魔法");
    const b = spreadPositions("elem", items, "dust", geom, 2000, "elem:魔法");
    expect(a.P).toEqual(b.P);
    expect(a.P.length).toBeGreaterThan(12);
    for (let i = 0; i < a.P.length; i++)
      for (let j = i + 1; j < a.P.length; j++) {
        const p = a.P[i];
        const q = a.P[j];
        const overlap =
          Math.abs(p.x - q.x) < (p.w + q.w) / 2 &&
          Math.abs(p.y - q.y) < (p.h + q.h) / 2;
        expect(overlap).toBe(false);
      }
    expect(a.P[0].w).toBeGreaterThanOrEqual(a.P[a.P.length - 1].w);
  });

  it("どの広げ方でも舞台からはみ出さない", () => {
    for (const s of ["fan", "ring", "time", "dust"] as Spread[])
      for (const k of KINDS) {
        const r = spreadPositions(k, items, s, geom, 1995, `${k}:${s}`);
        for (const p of r.P)
          expect(inside(p), `${k}/${s}/${p.slug}`).toBe(true);
      }
  });
});

describe("網点の出方", () => {
  it("11の出方すべてで v が 0..1 に収まる", () => {
    expect(TONES).toHaveLength(11);
    for (const t of TONES) {
      const o = toneOrder(t.key, 60, 124, 30, 57, rng(t.key));
      let lo = Infinity;
      let hi = -Infinity;
      for (const v of o) {
        lo = Math.min(lo, v);
        hi = Math.max(hi, v);
      }
      expect(lo, t.name).toBeGreaterThanOrEqual(0);
      expect(hi, t.name).toBeLessThanOrEqual(1);
    }
  });

  it("式どおり: 内周からは中央が最初、外周からは中央が最後、左上からは左上が最初", () => {
    const W = 11;
    const H = 11;
    const inner = toneOrder("inner", W, H, 5, 5);
    const outer = toneOrder("outer", W, H, 5, 5);
    const diag = toneOrder("diagonal", W, H, 5, 5);
    const radar = toneOrder("radar", W, H, 5, 5);
    const at = (o: Float32Array, i: number, j: number) => o[j * W + i];
    expect(at(inner, 5, 5)).toBe(0);
    expect(at(inner, 0, 0)).toBeCloseTo(1);
    expect(at(outer, 5, 5)).toBe(1);
    expect(at(diag, 0, 0)).toBe(0);
    // 真上が0・右(東)が 1/4・真下が 1/2(時計回り)
    expect(at(radar, 5, 0)).toBeCloseTo(0);
    expect(at(radar, 10, 5)).toBeCloseTo(0.25);
    expect(at(radar, 5, 10)).toBeCloseTo(0.5);
  });

  it("点の進み q: 始まる前は0・終わりは1・なめらか", () => {
    expect(toneQ(0, 0)).toBe(0);
    expect(toneQ(1, 1)).toBe(1);
    expect(toneQ(0.32, 0)).toBe(1);
    expect(toneQ(0.5, 1)).toBe(0);
    expect(toneQ(0.16, 0)).toBeCloseTo(0.5);
  });

  it("同じ出方を2回続けない", () => {
    const r = rng("pick");
    let last = pickTone(null, r);
    for (let i = 0; i < 200; i++) {
      const k = pickTone(last, r);
      expect(k).not.toBe(last);
      last = k;
    }
    expect(pickTone("inner", () => 0.9999)).not.toBe("inner");
  });
});

describe("掛け合わせ(案C)", () => {
  const center = book("c", { themes: ["悲劇", "剣劇", "復讐"], genres: ["action", "horror"] });
  const list = [
    center,
    book("a", { themes: ["悲劇", "剣劇", "復讐"], genres: ["action"] }),
    book("b", { themes: ["悲劇", "剣劇"], genres: ["action", "horror"] }),
    book("d", { themes: ["悲劇"], genres: ["horror"] }),
    book("e", { themes: ["剣劇"], genres: [] }),
  ];
  const g = buildGraph(list);

  it("選んだ要素・ジャンルを全部持つ本だけ(中央の本は除く)・何も選ばなければ空", () => {
    const slugs = (m: Parameters<typeof mixCands>[2]) => mixCands(g, center, m).map((i) => g.items[i].slug).sort();
    expect(slugs(EMPTY_MIX)).toEqual([]);
    expect(slugs({ themes: ["悲劇"], genres: [] })).toEqual(["a", "b", "d"]);
    expect(slugs({ themes: ["悲劇", "剣劇"], genres: [] })).toEqual(["a", "b"]);
    expect(slugs({ themes: ["悲劇"], genres: ["horror"] })).toEqual(["b", "d"]);
  });

  it("札の冊数: 何も選ばなければ札ごとの冊数・選んだら「足したら何冊か」(選んだ札は出さない・0もある)", () => {
    const base = mixCounts(g, center, EMPTY_MIX);
    expect(base.total).toBe(0);
    expect(Object.fromEntries(base.themes)).toEqual({ 悲劇: 3, 剣劇: 3, 復讐: 1 });
    expect(Object.fromEntries(base.genres)).toEqual({ action: 2, horror: 2 });
    const c = mixCounts(g, center, { themes: ["悲劇", "剣劇"], genres: [] });
    expect(c.total).toBe(2);
    expect(Object.fromEntries(c.themes)).toEqual({ 復讐: 1 });
    expect(Object.fromEntries(c.genres)).toEqual({ action: 2, horror: 1 });
    const z = mixCounts(g, center, { themes: ["復讐"], genres: ["horror"] });
    expect(z.total).toBe(0);
  });

  it("広げる単位: 色は要素を1つでも選べば要素・ジャンルだけならジャンル、近い本ほど先", () => {
    const u = mixUnit(g, center, { themes: ["悲劇"], genres: ["action"] }, (k) => (k === "action" ? "アクション" : k));
    expect(u?.kind).toBe("elem");
    expect(u?.label).toBe("悲劇×アクション");
    expect(u?.key).toBe(mixKey({ themes: ["悲劇"], genres: ["action"] }));
    // 近さ = 共通の要素 + 4×ジャンルの重なり: a = 3 + 4×0.5 = 5 / b = 2 + 4×1 = 6
    expect(u?.items.map((i) => i.slug)).toEqual(["b", "a"]);
    expect(mixUnit(g, center, { themes: [], genres: ["horror"] })?.kind).toBe("genre");
    expect(mixUnit(g, center, EMPTY_MIX)).toBeNull();
    expect(mixUnit(g, center, { themes: ["復讐"], genres: ["horror"] })).toBeNull();
  });
});

describe("案2+3: ジャンルの組み替え・要素の星雲", () => {
  const center = book("c", { themes: ["悲劇", "剣劇"], genres: ["action", "fantasy", "horror"] });
  const list = [
    center,
    book("af", { themes: ["悲劇", "剣劇"], genres: ["action", "fantasy"], popularity: 5 }),
    book("afh", { themes: ["悲劇"], genres: ["action", "fantasy", "horror"], popularity: 9 }),
    book("afx", { themes: [], genres: ["action", "fantasy", "historical"] }),
    book("h", { themes: ["剣劇"], genres: ["horror"] }),
  ];
  const g = buildGraph(list);

  it("組み替え後のジャンル = 中心 − 外した + 足した・ラベルは「〜抜き・〜入り」", () => {
    expect(regenreKeys(center, { drop: ["horror"], add: ["historical"] })).toEqual(["action", "fantasy", "historical"]);
    expect(regenreLabel({ drop: ["horror"], add: ["historical"] }, (k) => ({ horror: "ホラー", historical: "歴史" })[k] ?? k)).toBe(
      "ホラー抜き・歴史入り",
    );
  });

  it("★ホラーを外すと、ホラー抜きの組に似た本(よく似たジャンルと同じ段階)・何も変えなければ null", () => {
    const u = regenreUnit(g, center, { drop: ["horror"], add: [] });
    expect(u?.kind).toBe("genre");
    // action+fantasy に対して: af=1.0 / afh=0.67 / afx=0.67 → 24冊に届かないので50%まで下げて3冊
    expect(u?.items.map((i) => i.slug)).toEqual(["af", "afh", "afx"]);
    expect(regenreUnit(g, center, { drop: [], add: [] })).toBeNull();
    expect(regenreUnit(g, center, { drop: ["action", "fantasy", "horror"], add: [] })).toBeNull();
  });

  it("島 = 要素ごとの冊数(多い順)と代表の書影(共通の要素が多い順 → popularity)", () => {
    const isl = themeIslands(g, center);
    expect(isl.map((x) => [x.theme, x.count])).toEqual([
      ["悲劇", 2],
      ["剣劇", 2],
    ]);
    expect(isl[0].covers).toEqual(["af", "afh"]);
  });

  it("島の頁分け: 10個までは1頁・11個は6+5", () => {
    expect(islandPages([...Array(10).keys()]).map((p) => p.length)).toEqual([10]);
    expect(islandPages([...Array(11).keys()]).map((p) => p.length)).toEqual([6, 5]);
  });
});
