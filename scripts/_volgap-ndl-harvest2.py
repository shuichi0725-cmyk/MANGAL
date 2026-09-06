# -*- coding: utf-8 -*-
"""【巻抜け充填 第2段】ローカル楽天で埋まらなかった頁を NDL SRU で回収する。

前段 = _volgap-local-fill-v2.py (tier=NOHIT/DROPPED の頁がここの入力)。
★発見源で探すのが当然([[ndl_volume_completion_better_than_rakuten]])= NDLは楽天が持たない
  ニッチ作/旧作の巻を持つ。 楽天title検索の取りこぼしをここで拾う。

規則(skill external-data-access):
 - 照会は `_lookup.ndl_live_retry`(1.3s/req・429はbackoff吸収)。live実装をコピペしない
 - ページング必須(1req最大200件・実効500件上限)。1頁だけ取る実装は禁止
 - 逐次追記(1頁ずつflush)+再開可能(done-set)

出力: .cache/volgap-ndl-fill.jsonl  {stem, title, query, n, records:[...]}
使用: python scripts/_volgap-ndl-harvest2.py [--in JSON] [--limit N]
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
IN = (sys.argv[sys.argv.index("--in") + 1] if "--in" in sys.argv
      else os.path.join(ROOT, ".cache", "volgap-local-fill-v2.json"))
OUT = os.path.join(ROOT, ".cache", "volgap-ndl-fill.jsonl")
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
PAGE = 200
MAX_TOTAL = 500  # ★1クエリ実効上限(2026-07-19実測)


def fetch_all(query):
    """startRecord ページングで全件(実効500件上限まで)。"""
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
    rows = json.load(open(IN, encoding="utf-8"))
    need = sorted({r["stem"] for r in rows if r["tier"] in ("NOHIT", "DROPPED")})
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                done.add(json.loads(line)["stem"])
            except Exception:
                pass
    todo = [s for s in need if s not in done]
    if LIMIT:
        todo = todo[:LIMIT]
    print("NDL照会が要る頁 {} / 済 {} / 今回 {}".format(len(need), len(done), len(todo)), flush=True)
    print("見込み ~{:.0f}分 (1.3秒/req・頁あたり1-3req)".format(len(todo) * 1.3 * 1.6 / 60), flush=True)

    t0 = time.time()
    f = open(OUT, "a", encoding="utf-8")
    for i, stem in enumerate(todo, 1):
        p = os.path.join(SRC, stem + ".yml")
        if not os.path.exists(p):
            continue
        d = yaml.safe_load(open(p, encoding="utf-8")) or {}
        title = (d.get("title") or "").strip()
        authors = [a.get("name") for a in (d.get("authors") or []) if a.get("name")]
        if not title:
            continue
        # ★作者束縛が本命(同名作に埋もれない)。著者不明の頁だけ title 単独
        if authors:
            q = 'title="{}" AND creator="{}"'.format(title, authors[0])
        else:
            q = 'title="{}"'.format(title)
        recs = fetch_all(q)
        # 作者束縛で0件なら title 単独へ緩和(NDLの著者表記ゆれ吸収)
        q2 = ""
        if not recs and authors:
            q2 = 'title="{}"'.format(title)
            recs = fetch_all(q2)
        f.write(json.dumps({"stem": stem, "title": title, "query": q, "query2": q2,
                            "n": len(recs), "records": recs}, ensure_ascii=False) + "\n")
        f.flush()
        if i % 10 == 0 or i == len(todo):
            el = time.time() - t0
            print("  {}/{} {} n={} ({:.1f}分経過 / 残り~{:.0f}分)".format(
                i, len(todo), stem[:30], len(recs), el / 60,
                (el / i) * (len(todo) - i) / 60), flush=True)
    f.close()
    print("完了 → " + OUT)


if __name__ == "__main__":
    main()
