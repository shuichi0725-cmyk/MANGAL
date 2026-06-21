#!/usr/bin/env python3
"""
楽天キャッシュ(rakuten-isbn.jsonl 246k)から書影を全DBに純粋追加(API不要)。
cover_url が null の巻だけ、ISBNでキャッシュの largeImageUrl を埋める。
descriptionも同時に ISBN→caption seed に退避(後のAI要約用・gitignoreでない場所)。
使い方: python _rakuten-cache-coverfill.py [--apply] [dir1 dir2...]
"""
import sys, os, json, glob, re, time
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L, CSafeDumper as D
except ImportError: from yaml import SafeLoader as L, SafeDumper as D
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""
def norm_img(u):
    u = str(u or "")
    if not u or "noimage" in u: return None
    return u.split("?")[0] + "?_ex=300x300"

apply = "--apply" in sys.argv
dirs = [a for a in sys.argv[1:] if not a.startswith("--")] or [".preview-data/manga", "data/manga.v2"]

print("キャッシュ読込中...", flush=True)
COV = {}; CAP = {}
t0 = time.time()
for line in open(os.path.join(ROOT, ".cache", "rakuten-isbn.jsonl"), encoding="utf-8"):
    try: o = json.loads(line)
    except: continue
    it = o.get("item") or {}
    ib = to13(o.get("isbn") or it.get("isbn"))
    if not ib: continue
    img = norm_img(it.get("largeImageUrl") or it.get("mediumImageUrl"))
    if img and ib not in COV: COV[ib] = img
    cap = (it.get("itemCaption") or "").strip()
    if cap and ib not in CAP: CAP[ib] = cap
print(f"キャッシュ: 書影{len(COV)} / 説明{len(CAP)} ({time.time()-t0:.0f}s)", flush=True)

clog = open(os.path.join(ROOT, "data", "seeds", "cover-cachefill-changelog.jsonl"), "a", encoding="utf-8") if apply else None
capf = os.path.join(ROOT, "data", "seeds", "rakuten-captions.jsonl")
cap_seen = set()
if os.path.exists(capf):
    for line in open(capf, encoding="utf-8"):
        try: cap_seen.add(json.loads(line)["isbn"])
        except: continue
capout = open(capf, "a", encoding="utf-8") if apply else None

for d in dirs:
    base = os.path.join(ROOT, d)
    if not os.path.isdir(base): continue
    files = glob.glob(os.path.join(base, "*.yml"))
    nfill = npage = ncap = 0
    t1 = time.time()
    for i, fp in enumerate(files):
        try: data = yaml.load(open(fp, encoding="utf-8"), Loader=L)
        except: continue
        if not isinstance(data, dict): continue
        ch = False
        def fill_vols(vols):
            global nfill, ncap
            c = False
            for v in vols:
                ib = to13(v.get("isbn13"))
                if not ib: continue
                if not v.get("cover_url") and ib in COV:
                    v["cover_url"] = COV[ib]; nfill += 1; c = True
                if apply and ib in CAP and ib not in cap_seen and ib not in fill_vols.local:
                    fill_vols.local.add(ib); ncap += 1
                    capout.write(json.dumps({"isbn": ib, "caption": CAP[ib]}, ensure_ascii=False) + "\n")
            return c
        fill_vols.local = set()
        for e in (data.get("editions") or []):
            if fill_vols(e.get("volumes") or []): ch = True
            for ver in (e.get("versions") or []):
                if fill_vols(ver.get("volumes") or []): ch = True
        if ch:
            npage += 1
            if apply:
                open(fp, "w", encoding="utf-8").write(yaml.dump(data, allow_unicode=True, sort_keys=False, Dumper=D))
                clog.write(json.dumps({"slug": data.get("slug"), "filled": True}, ensure_ascii=False) + "\n")
        if (i + 1) % 10000 == 0:
            print(f"  {d}: {i+1}/{len(files)} (書影{nfill}/page{npage}) {time.time()-t1:.0f}s", flush=True)
    print(f"[{d}] 書影補完 {nfill} / ページ {npage} / 説明退避 {ncap} ({time.time()-t1:.0f}s)", flush=True)
if apply: clog.close(); capout.close()
print("DRY (未適用)" if not apply else "適用完了", flush=True)
