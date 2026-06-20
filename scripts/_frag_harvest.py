#!/usr/bin/env python3
"""
フラグメント補完: 楽天Books APIで作品の欠け巻ISBNを収穫(慎重・PROPOSE only)。
題+著者で照合しsubseries汚染を避ける。--apply で種4(volumes-supplement.yml)へ純粋追加。
使い方: python _frag_harvest.py <slug> [<title>] [--apply]
"""
import sys, os, json, re, time, unicodedata, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
import yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env = {}
for ln in open(os.path.join(ROOT, ".env.local"), encoding="utf-8"):
    if "=" in ln and not ln.strip().startswith("#"):
        k, v = ln.split("=", 1); env[k.strip()] = v.strip()
from urllib.parse import urlparse
RREF = env.get("RAKUTEN_REFERER", "https://github.com/"); _o = urlparse(RREF); RORG = f"{_o.scheme}://{_o.netloc}"

def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""
def naz(s): return re.sub(r"[\s　・！!？\?（）\(\)\[\]【】〜~,，、。:：;；/／\.’'\"]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

def rakuten(title, page=1):
    time.sleep(1.0)
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"], "format": "json",
         "formatVersion": "2", "title": title, "hits": 30, "page": page, "booksGenreId": "001001",
         "outOfStockFlag": 1, "sort": "+releaseDate"}
    u = "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p)
    d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"Referer": RREF, "Origin": RORG, "User-Agent": "M/0.1", "Accept": "application/json"}), timeout=30).read())
    return d

def volnum(title, base_naz):
    """楽天題から巻番号を抽出 (= 末尾の (N) / N / 第N巻)。base題と一致する前提。"""
    t = title
    m = re.search(r"[（(]\s*(\d+)\s*[）)]\s*$", t) or re.search(r"\b(\d+)\s*$", t) or re.search(r"第\s*(\d+)\s*巻", t)
    return int(m.group(1)) if m else None

def main():
    slug = sys.argv[1]
    apply = "--apply" in sys.argv
    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    fp = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
    d = yaml.safe_load(open(fp, encoding="utf-8"))
    title = args[0] if args else d.get("title")
    authors = [a.get("name") for a in (d.get("authors") or [])]
    base = naz(title)
    have = set()
    for e in d.get("editions", []):
        for v in e.get("volumes", []):
            if isinstance(v.get("number"), int): have.add(v["number"])
    lo, hi = min(have), max(have)
    missing = [x for x in range(lo, hi + 1) if x not in have]
    print(f"{slug} [{title}] 著{authors}")
    print(f"  現{sorted(have)} 欠け{missing}")
    # 楽天検索(複数ページ)
    found = {}  # num -> (isbn, rtitle, rauthor, date)
    for pg in (1, 2, 3):
        try: r = rakuten(title, pg)
        except Exception as ex: print("  API err", ex); break
        items = r.get("Items", [])
        if not items: break
        for it in items:
            rt = it.get("title", ""); rib = to13(it.get("isbn"))
            if not rib: continue
            # ★題照合: 楽天題が base題で始まる(subseries汚染除外)
            rn = naz(rt)
            if not rn.startswith(base[:max(4, len(base) - 2)]): continue
            n = volnum(rt, base)
            if n is None: continue
            found.setdefault(n, (rib, rt, it.get("author", ""), it.get("salesDate", "")))
        if r.get("count", 0) <= pg * 30: break
    print(f"  楽天で見つかった巻: {sorted(found)}")
    fill = [(n, *found[n]) for n in missing if n in found]
    print(f"  ★補完可能(欠け∩楽天): {len(fill)}巻")
    for n, ib, rt, ra, dt in fill:
        print(f"     #{n} {ib} [{rt}] 著[{ra}] {dt}")
    # 警告: 楽天題の著者がページ著者と食い違うものは要注意
    return slug, title, authors, fill

if __name__ == "__main__":
    main()
