#!/usr/bin/env python3
"""
版バリアント durability stage: editions-supplement.yml を本番/テストに再適用。
seeded作品は editions を seed の権威版に置換(replace)。flat な版を置くので、後段 regroup が
同(type,巻数)を刷タブに畳む。書影は持たず(coverfill が ISBN で付与)。
intake STAGES の promote 後、regroup の前に走らせる。
使い方: python _apply-editions-supplement.py [mangaDir...]   既定= .preview-data/manga と data/manga.v2
"""
import sys, os, json, time, shutil
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L, CSafeDumper as Dp
except ImportError: from yaml import SafeLoader as L, SafeDumper as Dp
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "data", "seeds", "editions-supplement.yml")

def mk_edition(e):
    ed = {"type": e.get("type", "standard"), "label": e.get("label")}
    if e.get("publisher"): ed["publisher"] = e["publisher"]
    if e.get("imprint"): ed["imprint"] = e["imprint"]
    vols = []
    for v in (e.get("volumes") or []):
        vd = {"number": v.get("number"), "asin": None, "isbn13": v.get("isbn13"),
              "cover_url": None, "release_date": v.get("release_date")}
        if v.get("volume_label"): vd["volume_label"] = v["volume_label"]
        vols.append(vd)
    ed["volumes"] = vols
    return ed

def main():
    dirs = [a for a in sys.argv[1:] if not a.startswith("--")] or [".preview-data/manga", "data/manga.v2"]
    data = yaml.load(open(SEED, encoding="utf-8"), Loader=L) or {}
    works = {w["slug"]: w for w in (data.get("works") or [])}
    print(f"版seed: {len(works)}作", flush=True)
    bak = os.path.join(ROOT, ".cache", f"edisup-bak-{time.strftime('%Y%m%d-%H%M%S')}")
    n_app = 0
    for d in dirs:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base): continue
        applied = 0
        for slug, w in works.items():
            fp = os.path.join(base, slug + ".yml")
            if not os.path.exists(fp): continue
            doc = yaml.load(open(fp, encoding="utf-8"), Loader=L)
            if not isinstance(doc, dict): continue
            new_eds = [mk_edition(e) for e in (w.get("editions") or [])]
            if not new_eds: continue
            if w.get("replace", True):
                os.makedirs(bak, exist_ok=True)
                shutil.copy2(fp, os.path.join(bak, d.replace("/", "_").replace("\\", "_") + "__" + slug + ".yml"))
                doc["editions"] = new_eds
            else:
                exist = {e.get("label") for e in (doc.get("editions") or [])}
                doc.setdefault("editions", []).extend(e for e in new_eds if e["label"] not in exist)
            open(fp, "w", encoding="utf-8").write(yaml.dump(doc, allow_unicode=True, sort_keys=False, Dumper=Dp))
            # 同(type,巻数)を刷タブに畳む (= _regroup-versions.py をその場で実行)
            import subprocess
            subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "_regroup-versions.py"), fp],
                           capture_output=True)
            applied += 1
        print(f"  [{d}] 版適用 {applied}作", flush=True); n_app += applied
    print(f"完了: 版適用 延べ{n_app}", flush=True)

if __name__ == "__main__":
    main()
