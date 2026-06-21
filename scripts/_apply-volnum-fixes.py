#!/usr/bin/env python3
"""
A群 巻番号是正+補完の適用。
是正(CLEAN_SINGLE 61): 各版が単巻(1冊)で番号≥2 → 番号を1へ。isbn13→1 を volnum-override.yml に記録(durable)。
補完(MISSING 90): NDL著者一致のISBNで欠け巻を追加。volumes-supplement-offset.yml(種4・promote loaded)に追記(durable)。
全て可逆(.cache backup) + changelog。使い方: python _apply-volnum-fixes.py [--apply]
"""
import sys, os, re, json, time, shutil, ast
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L, CSafeDumper as D
except ImportError: from yaml import SafeLoader as L, SafeDumper as D
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPLY = "--apply" in sys.argv
def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""

bak = os.path.join(ROOT, ".cache", f"volnum-fix-bak-{time.strftime('%Y%m%d-%H%M%S')}")
clog = open(os.path.join(ROOT, "data", "seeds", "volnum-fix-changelog.jsonl"), "a", encoding="utf-8") if APPLY else None
st = time.strftime("%Y-%m-%dT%H:%M:%S")

def backup(fp):
    if APPLY:
        os.makedirs(bak, exist_ok=True)
        shutil.copy2(fp, os.path.join(bak, os.path.basename(fp)))

# ---- 是正 (CLEAN_SINGLE) ----
clean = [r.split("\t") for r in open(os.path.join(ROOT, "data", "seeds", "true-single-final.tsv"), encoding="utf-8").read().splitlines()[1:] if len(r.split("\t")) >= 4 and r.split("\t")[3] == "CLEAN_SINGLE"]
override = {}   # isbn13 -> 1
n_renum = 0
for r in clean:
    slug = r[0]
    for base in ("data/manga.v2", ".preview-data/manga"):
        fp = os.path.join(ROOT, base, slug + ".yml")
        if not os.path.exists(fp): continue
        d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
        if not isinstance(d, dict): continue
        changed = []
        for e in (d.get("editions") or []):
            vs = e.get("volumes") or []
            if len(vs) == 1 and isinstance(vs[0].get("number"), int) and vs[0]["number"] >= 2:
                old = vs[0]["number"]; vs[0]["number"] = 1
                ib = to13(vs[0].get("isbn13"))
                if ib: override[ib] = 1
                changed.append((e.get("label"), old, ib))
        if changed:
            if APPLY:
                backup(fp)
                open(fp, "w", encoding="utf-8").write(yaml.dump(d, allow_unicode=True, sort_keys=False, Dumper=D))
            if base == "data/manga.v2":
                n_renum += len(changed)
                if clog: clog.write(json.dumps({"slug": slug, "op": "renumber_to_1", "changed": changed, "at": st}, ensure_ascii=False) + "\n")

# ---- 補完 (MISSING with fill_isbns) ----
miss = [r.split("\t") for r in open(os.path.join(ROOT, "data", "seeds", "ndl-volnum-classify-A.tsv"), encoding="utf-8").read().splitlines()[1:] if len(r.split("\t")) >= 6 and r.split("\t")[4] == "MISSING" and r.split("\t")[5].strip()]
supp_entries = []
n_fill = 0
for r in miss:
    slug = r[0]
    fills = {}
    for tok in r[5].split(";"):
        if ":" in tok:
            num, ib = tok.split(":", 1); ib = to13(ib)
            if num.isdigit() and ib: fills[int(num)] = ib
    if not fills: continue
    stub = os.path.join(ROOT, "data", "manga", slug + ".yml")
    sk = None
    if os.path.exists(stub):
        m = re.search(r"_skey:\s*(.+)", open(stub, encoding="utf-8").read())
        if m: sk = m.group(1).strip()
    for base in ("data/manga.v2", ".preview-data/manga"):
        fp = os.path.join(ROOT, base, slug + ".yml")
        if not os.path.exists(fp): continue
        d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
        if not isinstance(d, dict): continue
        tgt = max(d["editions"], key=lambda e: len(e.get("volumes") or []))
        exist_n = {v.get("number") for v in tgt["volumes"]}
        exist_i = {to13(v.get("isbn13")) for v in tgt["volumes"]}
        added = False
        for num, ib in sorted(fills.items()):
            if num not in exist_n and ib not in exist_i:
                tgt["volumes"].append({"number": num, "asin": None, "isbn13": ib, "cover_url": None, "release_date": None})
                added = True
        if added:
            tgt["volumes"].sort(key=lambda v: v.get("number") or 0)
            if APPLY:
                backup(fp)
                open(fp, "w", encoding="utf-8").write(yaml.dump(d, allow_unicode=True, sort_keys=False, Dumper=D))
            if base == "data/manga.v2":
                n_fill += len(fills)
                if sk:
                    for num, ib in sorted(fills.items()):
                        supp_entries.append({"series_keys": [sk], "number": num, "isbn13": ib, "release_date": None,
                                             "edition_type": "standard", "source": "ndl", "added_at": "2026-06-21",
                                             "note": f"A群MISSING補完(NDL著者一致)。{slug}"})
                if clog: clog.write(json.dumps({"slug": slug, "op": "ndl_fill", "vols": sorted(fills), "at": st}, ensure_ascii=False) + "\n")

# ---- durable seeds 書込 ----
if APPLY:
    # volnum-override.yml (新規・isbn13->number)
    ovf = os.path.join(ROOT, "data", "seeds", "volnum-override.yml")
    cur = {}
    if os.path.exists(ovf):
        cur = (yaml.load(open(ovf, encoding="utf-8"), Loader=L) or {}).get("overrides", {})
    cur.update({k: v for k, v in override.items()})
    open(ovf, "w", encoding="utf-8").write("# 巻番号override (isbn13->正番号)。A群単巻のレーベル位置誤番号是正。promote後stageが適用。\n" +
                                           yaml.dump({"overrides": cur}, allow_unicode=True, sort_keys=False, Dumper=D))
    # 種4 (offset seed に追記 = promote loaded)
    if supp_entries:
        sf = os.path.join(ROOT, "data", "seeds", "volumes-supplement-offset.yml")
        data = yaml.load(open(sf, encoding="utf-8"), Loader=L) or {"volumes": []}
        data.setdefault("volumes", []).extend(supp_entries)
        open(sf, "w", encoding="utf-8").write("# OFFSET/GAP/A群-NDL 低巻・欠け補完(種4)。promoteのload_volumes_supplementが読む。\n" +
                                              yaml.dump({"schema_version": 1, "volumes": data["volumes"]}, allow_unicode=True, sort_keys=False, Dumper=D))
    clog.close()
print(f"{'適用' if APPLY else 'DRY'}: 番号是正 {n_renum}巻 / 補完 {n_fill}巻 / override {len(override)} / 種4追記 {len(supp_entries)}")
