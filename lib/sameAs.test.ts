import { describe, expect, it } from "vitest";
import { workSameAs } from "./sameAs";

describe("workSameAs", () => {
  it("作品QIDとAniListを使い、著者QID(wikidata_qid)は使わない", () => {
    const m = { anilist_id: 105778, work_wikidata_qid: "Q65240543", wikidata_qid: "Q24864023" };
    const s = workSameAs(m);
    expect(s).toEqual(["https://www.wikidata.org/wiki/Q65240543", "https://anilist.co/manga/105778"]);
    expect(s.join(" ")).not.toContain("Q24864023");
  });
  it("著者QIDしか無い頁は作品sameAsを出さない", () => {
    expect(workSameAs({ wikidata_qid: "Q24864023" } as never)).toEqual([]);
  });
});
