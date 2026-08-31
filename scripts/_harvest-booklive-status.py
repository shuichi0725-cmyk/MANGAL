# -*- coding: utf-8 -*-
"""BookLive最終巻照会 → 連載状態の外部証拠を収穫 (2026-08-18 連載中再検査)。

対象 = ongoing頁のうち試し読みアンカー(tameshiyomi-map.json)を持つもの:
  A: AniListリンク無し × 最終刊〜2022 (誤ongoing濃厚)
  B: AniListリンク無し × 2023-24 (グレー)
  C: AniList FINISHED × 最終刊〜2022 (クロスチェック)
  D: AniList RELEASING × 最終刊〜2022 (AniList鮮度疑い)

シグナル(最終巻頁1フェッチ):
  1. tag_left「完結」= tag_kanketsu (確定)
  2. あらすじ強文言(完結編/堂々の完結/全N巻…)= desc_strong (強)
  3. 弱文言(終幕/フィナーレ…)= desc_weak (保留=自動適用しない)
  4. 無し = none

出力 = data/seeds/status-booklive.jsonl へ逐次追記(再開時は照会済slugをskip)。
★レート = _booklive 共通ゲート(2026-08-31: 札・直列2.0秒・日次上限)。
  429等の異常はBlocked=台帳に書かず即中断(exit 2)。404=verdict http404 として記録(=照会済)。
"""
import io
import json
import re
import sys
import time
from pathlib import Path

import _booklive
from _booklive import Blocked, CapReached

ROOT = Path(__file__).resolve().parent.parent
TSV = ROOT / "docs" / "production-diagnostics" / "ongoing-recheck.tsv"
MAP = ROOT / "data" / "tameshiyomi-map.json"
OUT = ROOT / "data" / "seeds" / "status-booklive.jsonl"

STRONG = re.compile(
    r"堂々の?完結|遂に完結|ついに完結|完結編|最終巻|感動の完結|待望の完結|完結巻"
    r"|シリーズ完結|本編完結|全[0-9０-９一二三四五六七八九十]+巻|、完結|！完結|!!完結|完結！"
)
WEAK = re.compile(r"終幕|フィナーレ|ファイナル|最終回|最終決戦|クライマックス|大団円|完[。！!」]")
PART = re.compile(r"第[一二三四五六七八九十\d０-９]+部、?完結|[一二三四五六七八九十\d０-９]+章、?完結")


def probe(tid: str, vol: int) -> dict:
    """★Blocked/CapReachedは投げる(呼び手が中断)。404=verdict http404(定まった否定=照会済扱い)。"""
    st, html = _booklive.request(f"https://booklive.jp/product/index/title_id/{tid}/vol_no/{vol:03d}")
    if st != 200:
        return {"tag": "", "verdict": "http404", "evidence": "", "desc_tail": ""}
    m = re.search(r'product_series_tag tag_left[^"]*"><span>([^<]+)</span>', html)
    tag = m.group(1) if m else ""
    dm = re.search(r'name="description" content="【試し読み無料】([^"]*)"', html)
    desc = dm.group(1) if dm else ""
    if tag == "完結":
        verdict, ev = "tag_kanketsu", "タグ=完結"
    else:
        sm = STRONG.search(desc)
        pm = PART.search(desc)
        wm = WEAK.search(desc)
        if sm and not (pm and pm.start() <= sm.start() <= pm.end()):
            verdict, ev = "desc_strong", sm.group(0)
        elif pm:
            verdict, ev = "desc_part", pm.group(0)
        elif wm:
            verdict, ev = "desc_weak", wm.group(0)
        elif tag == "続巻入荷":
            verdict, ev = "tag_zokkan", "タグ=続巻入荷"
        else:
            verdict, ev = "none", ""
    return {"tag": tag, "verdict": verdict, "evidence": ev, "desc_tail": desc[-50:]}


def main() -> None:
    rows = {}
    for line in io.open(TSV, encoding="utf-8").readlines()[1:]:
        slug, last, st, _ = line.rstrip("\n").split("\t")
        rows[slug] = (int(last), st)
    tmap = json.load(io.open(MAP, encoding="utf-8"))

    targets = []
    for slug, (last, st) in sorted(rows.items()):
        if slug not in tmap:
            continue
        if st == "-" and last < 2025:
            grp = "A" if last < 2023 else "B"
        elif st == "FINISHED" and last < 2023:
            grp = "C"
        elif st == "RELEASING" and last < 2023:
            grp = "D"
        else:
            continue
        targets.append((slug, grp))

    done = set()
    if OUT.exists():
        for line in io.open(OUT, encoding="utf-8"):
            try:
                done.add(json.loads(line)["slug"])
            except Exception:
                pass
    todo = [(s, g) for s, g in targets if s not in done]
    print(f"対象 {len(targets)} / 照会済 {len(done)} / 残 {len(todo)}", flush=True)

    _booklive.assert_not_blocked()
    with io.open(OUT, "a", encoding="utf-8", newline="\n") as w:
        for i, (slug, grp) in enumerate(todo):
            tid, mx = tmap[slug][0], tmap[slug][1]  # 3要素形([tid, max, 欠番リスト])も先頭2つで良い
            try:
                r = probe(str(tid), int(mx))
            except CapReached as e:
                print(f"★打ち切り: {e}(逐次保存済み・続きは次回)", flush=True)
                break
            except Blocked as e:
                print(f"★中断: BookLiveから200/404以外の応答 ({e})。台帳には書かない。",
                      file=sys.stderr, flush=True)
                sys.exit(2)
            rec = {"slug": slug, "title_id": str(tid), "last_vol": int(mx), "group": grp,
                   **r, "at": time.strftime("%Y-%m-%d")}
            w.write(json.dumps(rec, ensure_ascii=False) + "\n")
            w.flush()
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(todo)}", flush=True)
    print("完了", flush=True)


if __name__ == "__main__":
    main()
