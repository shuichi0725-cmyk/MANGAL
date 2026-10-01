#!/usr/bin/env python3
"""Kobo電子版の紹介文(itemCaption)を「キャッチ無し・書影あり」頁の材料として集める(2026-10-01 新設)。

★書き込みはしない(材料集めだけ)。出力 = .cache/kobo-caption/harvest.jsonl(1頁1行・追記・再開可)。
★照合は2段で、どちらで当たったかを記録する:
   strict  = 題(巻番号を除いた正規化)完全一致 + 著者一致  … 100作試験で40/100・誤りなし
   relaxed = 「N巻」表記/副題付き/冠付き(正規化題が電子題に含まれる) + 著者一致
             … 試験で+20/100。うち別作品(スピンオフ)・掲載範囲外(傑作集/セレクション/コレクション)・
               後の巻 が混ざる = 書く段階で1件ずつ判断する前提
   分冊版(「分冊」「【第N話】」)は除外。
★失敗(429/5xx/通信)は否定記録にしない = done に入れず次回再試行。成功応答で一致0件だけを no_match で記録。
使い方:
  python scripts/_kobo-caption-harvest.py            # 全対象(2〜4巻→1巻→5巻以上の順)
  python scripts/_kobo-caption-harvest.py --limit 50 # 試運転
  python scripts/_kobo-caption-harvest.py --status   # 進捗だけ
"""
import sys, os, json, re, time, glob, unicodedata, urllib.request, urllib.parse, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTD = os.path.join(ROOT, ".cache", "kobo-caption")
OUT = os.path.join(OUTD, "harvest.jsonl")
env = {}
for ln in open(os.path.join(ROOT, ".env.local"), encoding="utf-8"):
    if "=" in ln and not ln.strip().startswith("#"):
        k, v = ln.split("=", 1); env[k.strip()] = v.strip()
_o = urllib.parse.urlparse(env["RAKUTEN_REFERER"]); RORG = f"{_o.scheme}://{_o.netloc}"


def naz(s):
    return re.sub(r"[\s　・！!？\?（）\(\)【】「」〔〕〜~,，、。:：;；/／\.．’'\"＆&\-]", "",
                  unicodedata.normalize("NFKC", str(s or ""))).lower()


def nau(s):
    return re.sub(r"[\s　・（）\(\)\[\]]", "", unicodedata.normalize("NFKC", str(s or "")))


def volnum(rt):
    t = unicodedata.normalize("NFKC", rt)
    m = (re.search(r"[（(]\s*(\d+)\s*[）)]\s*$", t) or re.search(r"第\s*(\d+)\s*巻", t)
         or re.search(r"[　 ]?(\d+)\s*巻\s*$", t) or re.search(r"[　 ]*[:：]?\s*(\d+)\s*$", t))
    if m:
        return int(m.group(1)), naz(t[:m.start()])
    return None, naz(t)


class Throttled(Exception):
    pass


def kobo(title):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"], "format": "json",
         "formatVersion": "2", "title": title, "hits": 30, "page": 1}
    u = "https://openapi.rakuten.co.jp/services/api/Kobo/EbookSearch/20170426?" + urllib.parse.urlencode(p)
    for wait in (0, 2, 5, 15, 45, 120):
        if wait:
            print(f"    retry in {wait}s", flush=True); time.sleep(wait)
        time.sleep(1.0)
        try:
            req = urllib.request.Request(u, headers={"Referer": env["RAKUTEN_REFERER"], "Origin": RORG,
                                                     "User-Agent": "M/0.1", "Accept": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except urllib.error.HTTPError as e:
            if e.code == 400:      # 題が検索語として不正(記号のみ等)= 成功応答扱いの0件
                return {"Items": [], "_http400": True}
            if e.code in (429, 500, 502, 503, 504):
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            continue
    raise Throttled("retries exhausted")


def targets():
    d = json.load(open(os.path.join(ROOT, "data", "manga-list-cols.v1.json"), encoding="utf-8"))
    col = {k: d["c"][i] for i, k in enumerate(d["f"])}
    ci = json.load(open(os.path.join(ROOT, "data", "manga-catch-index.json"), encoding="utf-8"))
    hold = set(l.split("\t")[0] for l in open(os.path.join(ROOT, "docs", "production-diagnostics", "enrich-hold.tsv"),
                                              encoding="utf-8"))
    pub2src = {}
    for fp in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
        with open(fp, encoding="utf-8") as f:
            for line in f:
                if line.startswith("slug: "):
                    pub2src[line[6:].strip()] = os.path.basename(fp)[:-4]; break
    band = {"2-4": [], "1": [], "5+": []}
    for s, c, v in zip(col["slug"], col["cover"], col["total_volumes"]):
        if not c or s in ci:
            continue
        src = pub2src.get(s, s)
        if src in hold or s in hold or not os.path.exists(os.path.join(ROOT, "data", "manga.v2", src + ".yml")):
            continue
        v = v or 0
        band["1" if v <= 1 else ("2-4" if v <= 4 else "5+")].append((s, src, "1" if v <= 1 else ("2-4" if v <= 4 else "5+")))
    return band["2-4"] + band["1"] + band["5+"]


def main():
    os.makedirs(OUTD, exist_ok=True)
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10 ** 9
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT, encoding="utf-8"):
            try:
                done.add(json.loads(l)["src"])
            except Exception:
                pass
    tg = targets()
    todo = [t for t in tg if t[1] not in done]
    print(f"対象 {len(tg)} / 済 {len(done)} / 残 {len(todo)}", flush=True)
    if "--status" in sys.argv:
        return
    n = ns = nr = 0
    with open(OUT, "a", encoding="utf-8") as out:
        for pub, src, b in todo[:limit]:
            y = yaml.load(open(os.path.join(ROOT, "data", "manga.v2", src + ".yml"), encoding="utf-8"), Loader=L)
            title = y.get("title") or ""
            base = naz(title)
            pau = set(nau(a.get("name")) for a in (y.get("authors") or []) if a.get("name"))
            try:
                r = kobo(title)
            except Throttled:
                print("★楽天が応答しない(リトライ尽き)= 中断。再実行で続きから。", flush=True)
                break
            got = []
            for it in r.get("Items", []):
                tt = it.get("title", "")
                if "分冊" in tt or re.search(r"第\d+話】", tt):
                    continue
                nv, rest = volnum(tt)
                strict = rest == base
                relaxed = (not strict) and len(base) >= 3 and base in rest
                if not (strict or relaxed):
                    continue
                ra = nau(it.get("author", ""))
                if not pau or not any(pa and pa in ra for pa in pau):
                    continue
                got.append({"match": "strict" if strict else "relaxed", "vol": nv or 1, "title": tt,
                            "author": it.get("author"), "cap": (it.get("itemCaption") or "").strip(),
                            "date": it.get("salesDate"), "url": it.get("itemUrl")})
            got.sort(key=lambda g: (g["match"] != "strict", g["vol"]))
            rec = {"slug": pub, "src": src, "band": b, "title": title, "authors": sorted(pau),
                   "n_items": len(r.get("Items", [])), "matched": got,
                   "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()
            n += 1
            if any(g["match"] == "strict" and len(g["cap"]) >= 40 for g in got):
                ns += 1
            elif any(len(g["cap"]) >= 40 for g in got):
                nr += 1
            if n % 200 == 0:
                print(f"{n} 件 / strict紹介文 {ns} / relaxedのみ {nr}", flush=True)
    print(f"END 今回 {n} 件 / strict紹介文 {ns} / relaxedのみ {nr}", flush=True)


if __name__ == "__main__":
    main()
