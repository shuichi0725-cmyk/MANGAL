#!/usr/bin/env python3
"""
B/C群 FILL補完の適用: NDL著者一致ISBNで欠け巻(低巻/内部欠け)を追加。
種4(volumes-supplement-offset.yml・promote loaded)に追記=durable。可逆(.cache backup)+changelog。
安全: 番号未存在∧ISBN未存在のみ追加(dedup)。使い方: python _apply-bc-fills.py [--apply]
"""
import sys, os, re, json, time, shutil
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L, CSafeDumper as D
except ImportError: from yaml import SafeLoader as L, SafeDumper as D
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPLY = "--apply" in sys.argv
def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""

bak = os.path.join(ROOT, ".cache", f"bc-fill-bak-{time.strftime('%Y%m%d-%H%M%S')}")
clog = open(os.path.join(ROOT, "data", "seeds", "volnum-fix-changelog.jsonl"), "a", encoding="utf-8") if APPLY else None
st = time.strftime("%Y-%m-%dT%H:%M:%S")

# B + C の FILL 行を集約
fills_by_slug = {}
for g in ("B", "C"):
    fp = os.path.join(ROOT, "data", "seeds", f"ndl-classify-{g}.tsv")
    if not os.path.exists(fp): continue
    for r in open(fp, encoding="utf-8").read().splitlines()[1:]:
        c = r.split("\t")
        if len(c) >= 7 and c[6] == "FILL" and c[5].strip():
            fills = {}
            for tok in c[5].split(";"):
                if ":" in tok:
                    num, ib = tok.split(":", 1); ib = to13(ib)
                    if num.isdigit() and ib: fills[int(num)] = ib
            if fills: fills_by_slug[c[0]] = fills

supp = []; n_fill = n_work = 0
for slug, fills in fills_by_slug.items():
    stub = os.path.join(ROOT, "data", "manga", slug + ".yml"); sk = None
    if os.path.exists(stub):
        m = re.search(r"_skey:\s*(.+)", open(stub, encoding="utf-8").read())
        if m: sk = m.group(1).strip()
    applied_here = False
    for base in ("data/manga.v2", ".preview-data/manga"):
        fp = os.path.join(ROOT, base, slug + ".yml")
        if not os.path.exists(fp): continue
        try: d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
        except: continue
        if not isinstance(d, dict) or not d.get("editions"): continue
        tgt = max(d["editions"], key=lambda e: len(e.get("volumes") or []))
        exn = {v.get("number") for v in tgt["volumes"]}
        exi = {to13(v.get("isbn13")) for v in tgt["volumes"]}
        add = [(n, ib) for n, ib in sorted(fills.items()) if n not in exn and ib not in exi]
        if not add: continue
        for n, ib in add:
            tgt["volumes"].append({"number": n, "asin": None, "isbn13": ib, "cover_url": None, "release_date": None})
        tgt["volumes"].sort(key=lambda v: v.get("number") or 0)
        if APPLY:
            os.makedirs(bak, exist_ok=True)
            shutil.copy2(fp, os.path.join(bak, base.replace("/", "_") + "__" + slug + ".yml"))
            open(fp, "w", encoding="utf-8").write(yaml.dump(d, allow_unicode=True, sort_keys=False, Dumper=D))
        if base == "data/manga.v2":
            applied_here = True; n_fill += len(add)
            if sk:
                for n, ib in add:
                    supp.append({"series_keys": [sk], "number": n, "isbn13": ib, "release_date": None,
                                 "edition_type": "standard", "source": "ndl", "added_at": "2026-06-21",
                                 "note": f"B/C群 欠け巻補完(NDL著者strict)。{slug}"})
            if clog: clog.write(json.dumps({"slug": slug, "op": "bc_fill", "vols": [n for n, _ in add], "at": st}, ensure_ascii=False) + "\n")
    if applied_here: n_work += 1

if APPLY and supp:
    sf = os.path.join(ROOT, "data", "seeds", "volumes-supplement-offset.yml")
    data = yaml.load(open(sf, encoding="utf-8"), Loader=L) or {"volumes": []}
    data.setdefault("volumes", []).extend(supp)
    open(sf, "w", encoding="utf-8").write("# OFFSET/GAP/A/B/C-NDL 補完(種4)。promoteのload_volumes_supplementが読む。\n" +
                                          yaml.dump({"schema_version": 1, "volumes": data["volumes"]}, allow_unicode=True, sort_keys=False, Dumper=D))
if clog: clog.close()
print(f"{'適用' if APPLY else 'DRY'}: 補完 {n_work}作 / {n_fill}巻 / 種4追記 {len(supp)}")
