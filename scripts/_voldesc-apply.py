#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""巻説明(volume-desc)のseed適用 (= skill volume-desc の Step3)

AI生成バッチ(.cache/voldesc/out/batch-*.jsonl 等)を検証して
data/seeds/volume-desc-ja.jsonl へ★純粋追加(既存ISBNはskip・上書き0)。

入力行: {"isbn13": "9784...", "slug": "...", "vol": 3, "desc": "..."}
検証ゲート:
  - isbn13 = 13桁数字
  - desc >= 60字 (短すぎ=生成不良)
  - 丸写しguard: materials.jsonl があれば、caption の50字連続一致を含むdescをreject
使い方:
  python scripts/_voldesc-apply.py ".cache/voldesc/out/batch-*.jsonl"
"""
import glob, io, json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "data", "seeds", "volume-desc-ja.jsonl")
MAT = os.path.join(ROOT, ".cache", "voldesc", "materials.jsonl")

if len(sys.argv) < 2:
    print("usage: _voldesc-apply.py <batch glob...>"); sys.exit(1)

exist = set()
if os.path.exists(SEED):
    for ln in io.open(SEED, encoding="utf-8"):
        try:
            exist.add(json.loads(ln)["isbn13"])
        except Exception:
            pass

capmap = {}
# ★照合元は永続キャッシュ(captions-cache.jsonl)が正: materials.jsonlはスライス毎に上書きされ
#   並列運転でゲートが素通りする(2026-07-20 実測48件すり抜けの根因)。materialsは補助で重畳。
CAPC = os.path.join(ROOT, ".cache", "voldesc", "captions-cache.jsonl")
if os.path.exists(CAPC):
    for ln in io.open(CAPC, encoding="utf-8"):
        try:
            r = json.loads(ln)
            capmap[r["isbn"]] = r.get("caption") or ""
        except Exception:
            pass
if os.path.exists(MAT):
    for ln in io.open(MAT, encoding="utf-8"):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        for v in r.get("vols") or []:
            capmap.setdefault(v["isbn"], v.get("caption") or "")


def verbatim(desc, cap, win=50):
    if not cap or len(cap) < win:
        return False
    for i in range(0, len(cap) - win + 1, 10):
        if cap[i:i + win] in desc:
            return True
    return False


rows, rejects, dups = [], [], 0
for pat in sys.argv[1:]:
    for fp in sorted(glob.glob(pat)):
        for n, ln in enumerate(io.open(fp, encoding="utf-8"), 1):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                rejects.append((fp, n, "json parse")); continue
            ib = str(r.get("isbn13") or "")
            desc = (r.get("desc") or "").strip()
            if len(ib) != 13 or not ib.isdigit():
                rejects.append((fp, n, f"isbn不正 {ib}")); continue
            if len(desc) < 60:
                rejects.append((fp, n, f"{ib} desc短すぎ({len(desc)}字)")); continue
            if verbatim(desc, capmap.get(ib, "")):
                rejects.append((fp, n, f"{ib} 丸写し疑い(50字連続一致)")); continue
            if ib in exist:
                dups += 1; continue
            exist.add(ib)
            rows.append({"isbn13": ib, "slug": r.get("slug"), "vol": r.get("vol"),
                         "desc": desc, "at": time.strftime("%Y-%m-%d")})

with io.open(SEED, "a", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"applied={len(rows)}, dup_skip={dups}, rejected={len(rejects)}, overwrites=0 → {os.path.relpath(SEED, ROOT)}")
for fp, n, why in rejects[:20]:
    print(f"  REJECT {os.path.basename(fp)}:{n} {why}")
if len(rejects) > 20:
    print(f"  ... 他{len(rejects)-20}件")
