# -*- coding: utf-8 -*-
"""offset seed(volumes-supplement-offset.yml)のラノベ/別作品混入掃引 (= 無職転生21巻型 2026-08-27)。

型: 2026-06-21の「B/C群 欠け巻補完(NDL著者strict)」はNDL著者一致だけで採用したため、
**原作小説**(著者に原作者が入る)や別作品の巻を掴み得た(無職転生21=MFブックス小説が実例)。
現行の巻抜けfillは4ゲート(題一致/版prefix/日付窓/著者)だが、6月分は再検証されていない。

検査: source=ndl の各entryを楽天liveでISBN照会し、
  ①楽天題(base正規化) vs そのISBNが載る本番頁の題 → 不一致=別作品疑い
  ②楽天seriesName にラノベ/小説レーベル語(ブックス/文庫/ノベル/novels) → 小説疑い
  ③楽天サイズ/ジャンルが取れれば補助
出力: docs/production-diagnostics/offset-ln.tsv (人が裁ける形)。自動除去はしない。

  python scripts/_audit-offset-ln.py [--limit N]
resumable: .cache/offset-ln-checked.txt に照会済みISBNを逐次記録。
"""
import argparse
import datetime
import io
import json
import os
import re
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import importlib
_LK = importlib.import_module("_lookup")

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "data", "seeds", "volumes-supplement-offset.yml")
PAGE_IDX = os.path.join(ROOT, ".cache", "isbn-page-index.json")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "offset-ln.tsv")
CHECKED = os.path.join(ROOT, ".cache", "offset-ln-checked.txt")

RE_LN = re.compile(r"(ブックス|文庫|ノベル|novels|ノベルズ|NOVELS)", re.I)
RE_STRIP = re.compile(r"[\s　・:：!！?？~〜\-‐−()（）\[\]【】「」『』<>《》.。,、&＆'’\"0-9０-９]+")


def norm(s):
    return RE_STRIP.sub("", str(s or "")).lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    seed = yaml.safe_load(io.open(SEED, encoding="utf-8"))
    page_idx = json.load(io.open(PAGE_IDX, encoding="utf-8"))
    checked = set()
    if os.path.exists(CHECKED):
        checked = {l.strip() for l in io.open(CHECKED, encoding="utf-8") if l.strip()}
    env = {}
    for name in (".env.local", ".env"):
        p = os.path.join(ROOT, name)
        if os.path.exists(p):
            for ln in io.open(p, encoding="utf-8"):
                if "=" in ln and not ln.startswith("#"):
                    k, v = ln.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")

    import glob
    title_cache = {}

    def page_title(slug):
        if slug not in title_cache:
            p = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
            t = ""
            if os.path.exists(p):
                for ln in io.open(p, encoding="utf-8"):
                    if ln.startswith("title:"):
                        t = ln[6:].strip().strip("'\"")
                        break
            title_cache[slug] = t
        return title_cache[slug]

    todo = [v for v in (seed.get("volumes") or []) if v.get("source") == "ndl"
            and str(v.get("isbn13")) not in checked]
    if a.limit:
        todo = todo[: a.limit]
    print(f"対象 {len(todo)} (照会済skip {len(checked)})", flush=True)
    rows = []
    mode = "a" if os.path.exists(OUT) and checked else "w"
    outf = io.open(OUT, mode, encoding="utf-8", newline="")
    if mode == "w":
        outf.write("isbn13\t巻\t頁\t頁題\t楽天題\tseriesName\tflag\n")
    ckf = io.open(CHECKED, "a", encoding="utf-8", newline="\n")
    n_flag = 0
    for i, v in enumerate(todo):
        ib = str(v.get("isbn13"))
        try:
            items = _LK.rakuten_live_retry(env, isbn=ib)
        except Exception:
            continue
        rt, sn = "", ""
        for it in items or []:
            dd = it.get("Item") or it
            rt = dd.get("title") or ""
            sn = dd.get("seriesName") or ""
            if rt:
                break
        slugs = page_idx.get(ib)
        slug = (slugs[0] if isinstance(slugs, list) and slugs else slugs) or ""
        pt = page_title(str(slug)) if slug else ""
        flags = []
        if rt and pt:
            n_r, n_p = norm(rt), norm(pt)
            if not (n_p and (n_p in n_r or n_r in n_p)):
                flags.append("題不一致")
        if sn and RE_LN.search(sn):
            flags.append(f"LNレーベル({sn[:20]})")
        if rt and RE_LN.search(rt):
            flags.append("題にレーベル語")
        if not rt:
            flags.append("楽天無し")
        if flags:
            n_flag += 1
            outf.write("\t".join([ib, str(v.get("number")), str(slug), pt[:30], rt[:40], sn[:20],
                                  " / ".join(flags)]) + "\n")
            outf.flush()
        ckf.write(ib + "\n")
        ckf.flush()
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(todo)} flag {n_flag}", flush=True)
        import time
        time.sleep(1.3)
    print(f"\n完了: 照会 {len(todo)} / flag {n_flag} → {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
