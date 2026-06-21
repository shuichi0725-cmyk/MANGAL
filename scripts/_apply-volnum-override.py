#!/usr/bin/env python3
"""
巻番号override durability stage: volnum-override.yml(isbn13->正番号) を本番に再適用。
番号は種2由来なので再promoteでレーベル位置誤番号に戻る → promote後に貼り直す。
intake STAGES の promote 後(coverfill近辺)に走らせる。
"""
import sys, os, glob
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L, CSafeDumper as D
except ImportError: from yaml import SafeLoader as L, SafeDumper as D
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OV = os.path.join(ROOT, "data", "seeds", "volnum-override.yml")
def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""

def main():
    if not os.path.exists(OV):
        print("volnum-override.yml 無し"); return
    ov = (yaml.load(open(OV, encoding="utf-8"), Loader=L) or {}).get("overrides", {})
    ov = {to13(k): int(v) for k, v in ov.items() if to13(k)}
    print(f"override: {len(ov)} isbn", flush=True)
    nfix = npage = 0
    for base in (".preview-data/manga", "data/manga.v2"):
        d0 = os.path.join(ROOT, base)
        if not os.path.isdir(d0): continue
        for fp in glob.glob(os.path.join(d0, "*.yml")):
            try: doc = yaml.load(open(fp, encoding="utf-8"), Loader=L)
            except: continue
            if not isinstance(doc, dict): continue
            ch = False
            for e in (doc.get("editions") or []):
                for v in (e.get("volumes") or []):
                    ib = to13(v.get("isbn13"))
                    if ib in ov and v.get("number") != ov[ib]:
                        v["number"] = ov[ib]; ch = True; nfix += 1
                if ch: e["volumes"].sort(key=lambda v: v.get("number") or 0)
            if ch:
                open(fp, "w", encoding="utf-8").write(yaml.dump(doc, allow_unicode=True, sort_keys=False, Dumper=D))
                npage += 1
        print(f"  [{base}] 番号是正 {nfix} / ページ {npage}", flush=True)
    print(f"完了: 番号是正 {nfix} / ページ {npage}", flush=True)

if __name__ == "__main__":
    main()
