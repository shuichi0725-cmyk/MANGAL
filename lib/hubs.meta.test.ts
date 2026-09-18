import { describe, expect, it } from "vitest";
import { hubDefs, hubMeta, hubRows, HUB_PAGE_SIZE, type HubKind } from "./hubs";

/** ハブ面(雑誌/出版社/年)の metadata 回帰テスト。
 *
 *  ★2026-09-18 の実害: `hubMeta` はページ番号を **title にしか** 付けておらず、
 *  description が全ページ 1ページ目と同一だった(実測 507頁 = publisher 210 / year 246 /
 *  magazine 51)。さらに代表作が「全体の人気上位3」固定だったため、5ページ目の説明文に
 *  1ページ目の作品名が並ぶという不正確さもあった。
 *  ここで「2ページ目以降は別文・そのページの作品を名乗る」を固定する。
 */
const KINDS: HubKind[] = ["magazine", "publisher", "year"];

describe("hubMeta のページ送り", () => {
  for (const kind of KINDS) {
    const def = hubDefs(kind).find((d) => d.pages >= 2);
    if (!def) continue;

    it(`${kind}: 2ページ目の description が1ページ目と違う`, () => {
      const p1 = hubMeta(def, 1).description;
      const p2 = hubMeta(def, 2).description;
      expect(p2).not.toBe(p1);
    });

    it(`${kind}: 2ページ目の description が件数の範囲を名乗る`, () => {
      const d = hubMeta(def, 2).description;
      const from = HUB_PAGE_SIZE + 1;
      expect(d).toContain(`${from.toLocaleString()}〜`);
      expect(d).toContain("2/");
    });

    it(`${kind}: 2ページ目の代表作は そのページに実在する作品`, () => {
      const rows = hubRows(kind, def.key, 2);
      if (rows.length === 0) return;
      const d = hubMeta(def, 2).description;
      // 先頭の作品名(切り詰められている場合があるので冒頭6文字で照合)
      const head = rows[0].title.slice(0, 6);
      expect(d).toContain(head);
    });

    it(`${kind}: 1ページ目には ページ表記を入れない`, () => {
      const d = hubMeta(def, 1).description;
      expect(d).not.toContain("ページ）");
    });
  }
});
