#!/usr/bin/env python3
"""
Kobo harvest 対象リスト構築(READ-ONLY)。
Phase1 = 書影欠け作品(null cover有)。Phase2 = 説明欠けの人気作(coverはあるがcaption無・popularity順上位)。
既存112k紙captionとdedup。出力 .cache/_kobo_targets.json。
"""
import sys, os, json, glob, gzip
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P2_CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 8000  # Phase2 上限(人気作)

def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""

# 既に caption を持つ ISBN(紙112k)
cap_have = set()
gz = os.path.join(ROOT, "data", "seeds", "rakuten-captions.jsonl.gz")
if os.path.exists(gz):
    for line in gzip.open(gz, "rt", encoding="utf-8"):
        try: cap_have.add(json.loads(line)["isbn"])
        except: continue
print(f"既存caption ISBN: {len(cap_have)}", flush=True)

phase1 = []          # 書影欠け slug
phase2 = []          # (popularity, slug) 説明欠け
n = 0
for fp in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
    try: d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
    except: continue
    if not isinstance(d, dict) or not d.get("slug"): continue
    n += 1
    eds = d.get("editions") or []
    vols = [v for e in eds for v in (e.get("volumes") or [])] + \
           [v for e in eds for ver in (e.get("versions") or []) for v in (ver.get("volumes") or [])]
    has_cover_gap = any(not v.get("cover_url") and to13(v.get("isbn13")) for v in vols)
    has_cap_gap = any(v.get("cover_url") and to13(v.get("isbn13")) and to13(v.get("isbn13")) not in cap_have for v in vols)
    if has_cover_gap:
        phase1.append(d["slug"])
    elif has_cap_gap:
        pop = d.get("popularity") or 0
        phase2.append((pop if isinstance(pop, (int, float)) else 0, d["slug"]))

phase2.sort(key=lambda x: -x[0])
phase2_slugs = [s for _, s in phase2[:P2_CAP]]
targets = {"phase1": phase1, "phase2": phase2_slugs}
json.dump(targets, open(os.path.join(ROOT, ".cache", "_kobo_targets.json"), "w", encoding="utf-8"), ensure_ascii=False)
print(f"走査 {n}作")
print(f"Phase1(書影欠け): {len(phase1)}作")
print(f"Phase2(説明欠け人気作・全{len(phase2)}中上位{len(phase2_slugs)}採用): {len(phase2_slugs)}作")
print(f"→ 合計対象 {len(phase1)+len(phase2_slugs)}作 (.cache/_kobo_targets.json)")
