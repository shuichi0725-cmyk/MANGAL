#!/usr/bin/env python3
"""本番存在チェック(高速): 索引→ISBN索引 の順で引く。★生ファイル66k走査は禁止(遅い)。

usage:
  python scripts/_exists.py --title <部分一致>      # 一覧索引でtitle検索(即)
  python scripts/_exists.py --slug <slug>           # 索引slug照合(即)
  python scripts/_exists.py --isbn <isbn13,...>     # ISBN→頁 (ISBN索引。無ければ--buildを先に)
  python scripts/_exists.py --build                 # ISBN索引を再生成(manga.v2 1回走査・以後は即)
ISBN索引 = .cache/isbn-page-index.json (isbn13→[slug])。reflect後に古くなるので大量照合前に--build推奨。
"""
import json, sys, os, re, glob
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "data", "manga-list-index.json")
IIDX = os.path.join(ROOT, ".cache", "isbn-page-index.json")

def build():
    import yaml
    m = {}
    n = 0
    for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
        n += 1
        try:
            raw = open(p, encoding="utf-8").read()
        except Exception:
            continue
        slug = None
        mm = re.search(r"^slug: (.+)$", raw, re.M)
        slug = mm.group(1).strip().strip("'\"") if mm else os.path.basename(p)[:-4]
        for ib in set(re.findall(r"97[89]\d{10}", raw)):
            m.setdefault(ib, []).append(slug)
    json.dump(m, open(IIDX, "w", encoding="utf-8"))
    print(f"ISBN索引: {n}頁 / {len(m)} ISBN → {IIDX}")

def main():
    args = sys.argv[1:]
    if "--build" in args:
        build(); return
    d = json.load(open(IDX, encoding="utf-8"))
    f = d["f"]; si = f.index("slug"); ti = f.index("title"); ai = f.index("authors")
    if "--title" in args:
        q = args[args.index("--title") + 1]
        hits = [(r[si], r[ti], (r[ai] or [{}])[0].get("name", "") if r[ai] else "") for r in d["d"] if q in str(r[ti])]
        for h in hits[:20]:
            print(f"  {h[0]:40} {h[1][:24]} {h[2]}")
        print(f"title『{q}』: {len(hits)}件")
    elif "--slug" in args:
        q = args[args.index("--slug") + 1]
        print("有" if any(r[si] == q for r in d["d"]) else "無")
    elif "--isbn" in args:
        qs = args[args.index("--isbn") + 1].split(",")
        if not os.path.exists(IIDX):
            print("ISBN索引無し → --build を先に"); return
        m = json.load(open(IIDX, encoding="utf-8"))
        for q in qs:
            q = re.sub(r"\D", "", q)
            print(f"  {q}: {m.get(q, '無')}")
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
