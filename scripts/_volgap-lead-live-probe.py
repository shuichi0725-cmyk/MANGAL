# -*- coding: utf-8 -*-
"""【1巻が無い頁】楽天live + NDL で欠けた先頭巻を探す(2026-09-07 ユーザ指示)。

ローカル楽天種(2026-06 の著者ハーベスト)は新刊・ニッチ作を持たないため、
先頭欠け(LEAD)の多くが NOHIT のまま残っていた
(実例: 無能の悪童王子は生き残りたい v1 = 9784575420906 はローカルに無く、楽天live+NDLで確定)。
→ **1巻が無い頁だけ**を対象に、2ソースを live で引き直す。

規則(skill external-data-access):
 - 照会は `_lookup` の rakuten_live_retry / ndl_live_retry(1.3s/req・429はbackoff吸収)
 - 逐次追記(1頁ずつflush)+再開可能(done-set)
 - ★NDL不在≠不存在。 楽天live(outOfStockFlag=1)が実在確認の一次手段

出力: .cache/volgap-lead-live.jsonl  {stem, title, rakuten:[...], ndl:[...]}
使用: python scripts/_volgap-lead-live-probe.py [--targets TSV] [--limit N]
"""
import os
import sys
import json
import time

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
import _lookup as LK

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
TARGETS = (sys.argv[sys.argv.index("--targets") + 1] if "--targets" in sys.argv
           else os.path.join(ROOT, "docs", "production-diagnostics", "volgap-fill-targets.tsv"))
OUT = os.path.join(ROOT, ".cache", "volgap-lead-live.jsonl")
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
PAGE = 200
MAX_TOTAL = 400

KEEP = ("title", "subTitle", "seriesName", "author", "publisherName", "salesDate",
        "isbn", "itemPrice", "largeImageUrl")


def ndl_all(query):
    out, start = [], 1
    while start <= MAX_TOTAL:
        recs = LK.ndl_live_retry(query, maximum=PAGE, start=start)
        if not recs:
            break
        out += recs
        if len(recs) < PAGE:
            break
        start += PAGE
    return out


def main():
    lines = open(TARGETS, encoding="utf-8").read().splitlines()
    cols = lines[0].split("\t")
    tg = [dict(zip(cols, l.split("\t"))) for l in lines[1:] if l.strip()]
    stems = sorted({r["stem"] for r in tg if r["kind"] in ("LEAD", "ELEAD")})
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                done.add(json.loads(line)["stem"])
            except Exception:
                pass
    todo = [s for s in stems if s not in done]
    if LIMIT:
        todo = todo[:LIMIT]
    print("1巻が無い頁 {} / 済 {} / 今回 {}".format(len(stems), len(done), len(todo)), flush=True)
    print("見込み ~{:.0f}分 (楽天1req + NDL1-2req / 頁)".format(len(todo) * 1.3 * 2.2 / 60), flush=True)

    env = LK._env()
    t0 = time.time()
    f = open(OUT, "a", encoding="utf-8")
    for i, stem in enumerate(todo, 1):
        p = os.path.join(SRC, stem + ".yml")
        if not os.path.exists(p):
            continue
        d = yaml.safe_load(open(p, encoding="utf-8")) or {}
        title = (d.get("title") or "").strip()
        authors = [a.get("name") for a in (d.get("authors") or [])
                   if a.get("name") and a.get("name") != "(unknown)"]
        if not title:
            continue
        try:
            items = LK.rakuten_live_retry(env, title=title, hits=30)
        except Exception as e:
            print("  楽天失敗 {}: {}".format(stem, e), flush=True)
            items = []
        rak = [{k: it.get(k) for k in KEEP} for it in items]
        q = ('title="{}" AND creator="{}"'.format(title, authors[0]) if authors
             else 'title="{}"'.format(title))
        nd = ndl_all(q)
        if not nd and authors:
            nd = ndl_all('title="{}"'.format(title))
        f.write(json.dumps({"stem": stem, "title": title, "authors": authors,
                            "rakuten": rak, "ndl": nd}, ensure_ascii=False) + "\n")
        f.flush()
        if i % 10 == 0 or i == len(todo):
            el = time.time() - t0
            print("  {}/{} {} 楽天{} NDL{} ({:.1f}分 / 残り~{:.0f}分)".format(
                i, len(todo), stem[:28], len(rak), len(nd), el / 60,
                (el / i) * (len(todo) - i) / 60), flush=True)
    f.close()
    print("完了 → " + OUT)


if __name__ == "__main__":
    main()
