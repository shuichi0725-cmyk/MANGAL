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
レート = 1.3秒/req 厳守。連続エラー5でabort。
"""
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

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


def fetch(tid: str, vol: int) -> str:
    url = f"https://booklive.jp/product/index/title_id/{tid}/vol_no/{vol:03d}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")


def probe(tid: str, vol: int) -> dict:
    html = fetch(tid, vol)
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

    errs = 0
    with io.open(OUT, "a", encoding="utf-8", newline="\n") as w:
        for i, (slug, grp) in enumerate(todo):
            tid, mx = tmap[slug][0], tmap[slug][1]  # 3要素形([tid, max, 欠番リスト])も先頭2つで良い
            try:
                r = probe(str(tid), int(mx))
                errs = 0
            except Exception as e:
                errs += 1
                print(f"  ERR {slug} {type(e).__name__}: {e}", flush=True)
                if errs >= 5:
                    print("連続エラー5 → abort(再開可)", flush=True)
                    sys.exit(1)
                time.sleep(5.0)
                continue
            rec = {"slug": slug, "title_id": str(tid), "last_vol": int(mx), "group": grp,
                   **r, "at": "2026-08-18"}
            w.write(json.dumps(rec, ensure_ascii=False) + "\n")
            w.flush()
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(todo)}", flush=True)
            time.sleep(1.3)
    print("完了", flush=True)


if __name__ == "__main__":
    main()
