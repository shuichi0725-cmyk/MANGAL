#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""取りこぼし候補をNDLで検証+各巻ISBN回収(2026-07-09)。mangazenkan検出→NDL裏取り→種4補完の中間工程。
入力: .cache/volgap-candidates.json / 出力: .cache/volgap-ndl-results.jsonl(1作1行・resumable)。1.3s/req。"""
import json, os, re, sys, time, unicodedata, urllib.request, urllib.parse, html

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, ".cache", "volgap-ndl-results.jsonl")

def anorm(a):
    a = unicodedata.normalize("NFKC", str(a or ""))
    a = re.sub(r"(著|作画|原作|漫画|画|監修|編|イラスト|キャラクター原案).*$", "", a)
    return re.sub(r"[\s,、]", "", a).lower()

KAN = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
def kan2int(s):
    s = s.strip()
    if s.isdigit(): return int(s)
    if s == "十": return 10
    if "十" in s:
        a, _, b = s.partition("十"); return (KAN.get(a, 1) if a else 1) * 10 + (KAN.get(b, 0) if b else 0)
    return KAN.get(s)

def to13(i):
    i = re.sub(r"[^0-9X]", "", str(i or "").upper())
    if len(i) == 13: return i
    if len(i) == 10:
        c = "978" + i[:9]; s = sum((1 if k % 2 == 0 else 3) * int(d) for k, d in enumerate(c))
        return c + str((10 - s % 10) % 10)
    return None

def vol_of(title, volfield):
    if volfield:
        n = re.findall(r"\d+", volfield)
        if n: return int(n[0])
    t = unicodedata.normalize("NFKC", title)
    for pat in [r"第\s*(\d+)\s*巻", r"巻之([一二三四五六七八九十]+)", r"\((\d+)\)\s*$", r"\s(\d+)\s*$", r"(\d+)\s*巻"]:
        m = re.search(pat, t)
        if m:
            g = m.group(1); v = int(g) if g.isdigit() else kan2int(g)
            if v: return v
    return None

def ndl(title):
    q = urllib.parse.quote(f'title="{title}"')
    url = f"https://ndlsearch.ndl.go.jp/api/sru?operation=searchRetrieve&query={q}&recordSchema=dcndl&maximumRecords=100"
    try:
        xml = html.unescape(urllib.request.urlopen(url, timeout=40).read().decode("utf-8"))
    except Exception:
        return []
    if "Too Many Requests" in xml:
        print("★NDL429 → 中断"); sys.exit(2)
    out = []
    for r in re.findall(r"<recordData>(.*?)</recordData>", xml, re.S):
        tit = re.search(r"<dcterms:title>([^<]+)", r) or re.search(r"<dc:title>.*?<rdf:value>([^<]+)", r, re.S)
        tit = tit.group(1) if tit else ""
        vf = re.search(r"<dcndl:volume>.*?<rdf:value>([^<]+)", r, re.S)
        creators = re.findall(r"<foaf:name>([^<]+)", r) or re.findall(r"<dc:creator>([^<]+)", r)
        isb = re.search(r'ISBN">([0-9\-X]+)', r) or re.search(r"(97[89][\d\-]{10,16})", r)
        date = re.search(r"<dcterms:date>([^<]+)", r)
        out.append({"vol": vol_of(tit, vf.group(1) if vf else ""), "creators": [anorm(c) for c in creators],
                    "isbn": to13(isb.group(1)) if isb else None, "date": (date.group(1) if date else "")})
    return out

cand = json.load(open(os.path.join(ROOT, ".cache", "volgap-candidates.json"), encoding="utf-8"))
done = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        try: done.add(json.loads(l)["slug"])
        except Exception: pass
print(f"候補{len(cand)} / 済{len(done)} / 残{len(cand) - len(done)}")
with open(OUT, "a", encoding="utf-8") as fo:
    for i, c in enumerate(cand):
        if c["slug"] in done: continue
        ma = {anorm(x) for x in re.split(r"[,、/／]", c["author"]) if x.strip()}
        recs = ndl(c["title"])
        vmap = {}
        for r in recs:
            if not (r["vol"] and r["isbn"]): continue
            if ma & set(r["creators"]) or any(x and cc and (x in cc or cc in x) for x in ma for cc in r["creators"]):
                vmap.setdefault(r["vol"], {"isbn": r["isbn"], "date": r["date"]})
        ndlmax = max(vmap) if vmap else 0
        rec = {**c, "ndl_max": ndlmax, "ndl_vols": len(vmap),
               "vmap": {str(k): v for k, v in sorted(vmap.items())},
               "agree": bool(ndlmax >= c["mz"] - 1 and ndlmax > c["mangal"])}
        fo.write(json.dumps(rec, ensure_ascii=False) + "\n"); fo.flush()
        time.sleep(1.3)
        if (i + 1) % 10 == 0: print(f"  {i + 1}/{len(cand)}")
print("完了")
