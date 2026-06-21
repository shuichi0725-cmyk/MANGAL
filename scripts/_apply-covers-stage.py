#!/usr/bin/env python3
"""
書影 durability stage: 書影を git追跡seed(covers.jsonl.gz)から本番に再適用。
promote が cover_url=null で出すため、intake STAGES の promote 後に走らせて書影を貼り直す。
  --build : 楽天cache(rakuten-isbn.jsonl) + Kobo(kobo-harvest.jsonl) から covers.jsonl.gz を(再)生成
  (既定) : covers.jsonl.gz を読み、null cover_url を埋める (manga.v2 + .preview-data、純粋追加)
"""
import sys, os, json, glob, gzip
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L, CSafeDumper as Dp
except ImportError: from yaml import SafeLoader as L, SafeDumper as Dp
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "data", "seeds", "covers.jsonl.gz")

def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""
def norm(u):
    u = str(u or "")
    if not u or "noimage" in u: return None
    return u.split("?")[0] + "?_ex=300x300"

def build():
    cov = {}
    # 楽天紙 cache
    cpath = os.path.join(ROOT, ".cache", "rakuten-isbn.jsonl")
    if os.path.exists(cpath):
        for line in open(cpath, encoding="utf-8"):
            try: o = json.loads(line)
            except: continue
            it = o.get("item") or {}
            ib = to13(o.get("isbn") or it.get("isbn"))
            img = norm(it.get("largeImageUrl") or it.get("mediumImageUrl"))
            if ib and img and ib not in cov: cov[ib] = img
    # Kobo電子
    kpath = os.path.join(ROOT, "data", "seeds", "kobo-harvest.jsonl")
    nk = 0
    if os.path.exists(kpath):
        for line in open(kpath, encoding="utf-8"):
            try: o = json.loads(line)
            except: continue
            ib = to13(o.get("isbn13")); img = norm(o.get("kobo_img"))
            if ib and img and ib not in cov: cov[ib] = img; nk += 1
    with gzip.open(SEED, "wt", encoding="utf-8") as f:
        for ib, u in cov.items():
            f.write(json.dumps({"isbn13": ib, "cover_url": u}, ensure_ascii=False) + "\n")
    print(f"covers.jsonl.gz 生成: {len(cov)}件 (うちKobo由来 {nk})", flush=True)

def apply():
    if not os.path.exists(SEED):
        print("covers.jsonl.gz 無し → --build 先行要", flush=True); return
    cov = {}
    for line in gzip.open(SEED, "rt", encoding="utf-8"):
        try: o = json.loads(line); cov[o["isbn13"]] = o["cover_url"]
        except: continue
    print(f"covers seed: {len(cov)}件 読込", flush=True)
    nfill = npage = 0
    for d in (".preview-data/manga", "data/manga.v2"):
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base): continue
        for fp in glob.glob(os.path.join(base, "*.yml")):
            try: data = yaml.load(open(fp, encoding="utf-8"), Loader=L)
            except: continue
            if not isinstance(data, dict): continue
            ch = False
            for e in (data.get("editions") or []):
                srcs = [e.get("volumes") or []] + [v.get("volumes") or [] for v in (e.get("versions") or [])]
                for vols in srcs:
                    for v in vols:
                        ib = to13(v.get("isbn13"))
                        if ib and not v.get("cover_url") and ib in cov:
                            v["cover_url"] = cov[ib]; nfill += 1; ch = True
            if ch:
                open(fp, "w", encoding="utf-8").write(yaml.dump(data, allow_unicode=True, sort_keys=False, Dumper=Dp))
                npage += 1
        print(f"  [{d}] 書影適用 {nfill} / ページ {npage}", flush=True)
    print(f"完了: 書影適用 {nfill} / ページ {npage}", flush=True)

if __name__ == "__main__":
    (build if "--build" in sys.argv else apply)()
