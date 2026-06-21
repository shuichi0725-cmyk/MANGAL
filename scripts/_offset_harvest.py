#!/usr/bin/env python3
"""
OFFSET補完バッチ: ページが vol1/低巻を取りこぼし([2,3]始まり等)を楽天で収穫して補完。
★vol1は題に「(1)」が付かない事が多い→無印題=vol1として扱う(著者一致+題完全一致時のみ)。
安全: 題完全一致+著者一致のみ / dedup(既存ISBN除外) / 種4記録(yaml.dump安全) / changelog / resume。
使い方: python _offset_harvest.py <listkey=E> [limit] [--apply]
"""
import sys, os, json, re, time, unicodedata, urllib.request, urllib.parse, shutil
sys.stdout.reconfigure(encoding="utf-8")
import yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env = {}
for ln in open(os.path.join(ROOT, ".env.local"), encoding="utf-8"):
    if "=" in ln and not ln.strip().startswith("#"):
        k, v = ln.split("=", 1); env[k.strip()] = v.strip()
from urllib.parse import urlparse
RREF = env["RAKUTEN_REFERER"]; _o = urlparse(RREF); RORG = f"{_o.scheme}://{_o.netloc}"

def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""
def naz(s): return re.sub(r"[\s　・！!？\?（）\(\)【】「」〜~,，、。:：;；/／\.．’'\"＆&\-]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()
def nau(s): return re.sub(r"[\s　・（）\(\)\[\]]", "", unicodedata.normalize("NFKC", str(s or "")))
def pdate(s):
    m = re.match(r"(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?", str(s))
    if m: y, mo, da = m.group(1), m.group(2).zfill(2), m.group(3); return f"{y}-{mo}-{da.zfill(2)}" if da else f"{y}-{mo}"
    return str(s) if s else None

def rakuten(title, author="", page=1):
    time.sleep(1.0)
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"], "format": "json",
         "formatVersion": "2", "title": title, "hits": 30, "page": page, "booksGenreId": "001001", "outOfStockFlag": 1}
    if author: p["author"] = author
    u = "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p)
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"Referer": RREF, "Origin": RORG, "User-Agent": "M/0.1", "Accept": "application/json"}), timeout=30).read())

def volnum(rt):
    m = re.search(r"[（(]\s*(\d+)\s*[）)]\s*$", rt) or re.search(r"第\s*(\d+)\s*巻", rt) or re.search(r"[　 ](\d+)\s*$", rt)
    if m: return int(m.group(1)), naz(rt[:m.start()])
    return None, naz(rt)  # 番号なし

def main():
    listkey = sys.argv[1] if len(sys.argv) > 1 else "E"
    limit = next((int(a) for a in sys.argv[2:] if a.isdigit()), 999999)
    apply = "--apply" in sys.argv
    slugs = json.load(open(os.path.join(ROOT, ".cache", "_offset_lists.json"), encoding="utf-8"))[listkey]
    donef = os.path.join(ROOT, ".cache", f"_offset_done_{listkey}.json")
    done = set(json.load(open(donef, encoding="utf-8"))) if os.path.exists(donef) else set()
    s4f = open(os.path.join(ROOT, "data", "seeds", "volumes-supplement-offset.yml"), "a", encoding="utf-8")
    lf = open(os.path.join(ROOT, "data", "seeds", "sharedisbn-step1-changelog.jsonl"), "a", encoding="utf-8")
    st = time.strftime("%Y-%m-%dT%H:%M:%S")
    todo = [s for s in slugs if s not in done][:limit]
    print(f"{listkey}: 対象{len(slugs)} / 済{len(done)} / 今回{len(todo)}", flush=True)
    nfill = nworks = nskip = 0
    for i, slug in enumerate(todo):
        fp = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
        if not os.path.exists(fp): done.add(slug); continue
        d = yaml.safe_load(open(fp, encoding="utf-8"))
        title = d.get("title"); base = naz(title)
        pau = set(nau(a.get("name")) for a in (d.get("authors") or []) if a.get("name"))
        existing_isbn = set(to13(v.get("isbn13")) for e in d.get("editions", []) for v in e.get("volumes", []) if to13(v.get("isbn13")))
        nums = sorted(set(v.get("number") for e in d.get("editions", []) for v in e.get("volumes", []) if isinstance(v.get("number"), int)))
        if not nums: done.add(slug); continue
        miss_low = [x for x in range(1, nums[0])]  # vol1..min-1
        found = {}
        try:
            for pg in (1, 2):
                r = rakuten(title, next(iter(pau), "") and "", pg)  # 著者は付けない(別名揺れ回避)→題+著者照合は後段
                items = r.get("Items", [])
                if not items: break
                for it in items:
                    rt = it.get("title", ""); ib = to13(it.get("isbn"))
                    if not ib or ib in existing_isbn: continue
                    n, rest = volnum(rt)
                    if rest != base: continue          # ★番号除去後が題と完全一致
                    ra = nau(it.get("author", ""))
                    if pau and not any(pa and pa in ra for pa in pau): continue  # 著者一致
                    if n is None: n = 1                 # 無印題=vol1
                    if n in miss_low:
                        found.setdefault(n, (ib, pdate(it.get("salesDate", "")), rt))
                if r.get("count", 0) <= pg * 30: break
        except Exception as ex:
            print(f"  {slug} ERR {ex}", flush=True); continue
        fill = sorted(found.items())
        if fill:
            nworks += 1; nfill += len(fill)
            if apply:
                shutil.copy2(fp, fp + ".offbak")
                tgt = max(d["editions"], key=lambda e: len(e.get("volumes", [])))
                ex = {v.get("number") for v in tgt["volumes"]}
                for n, (ib, dt, rt) in fill:
                    if n not in ex:
                        tgt["volumes"].append({"number": n, "asin": None, "isbn13": ib, "cover_url": None, "release_date": dt})
                tgt["volumes"].sort(key=lambda v: v.get("number") or 0)
                open(fp, "w", encoding="utf-8").write(yaml.dump(d, allow_unicode=True, sort_keys=False))
                # .preview-data 側
                pv = os.path.join(ROOT, ".preview-data", "manga", slug + ".yml")
                if os.path.exists(pv):
                    dd = yaml.safe_load(open(pv, encoding="utf-8"))
                    t2 = max(dd["editions"], key=lambda e: len(e.get("volumes", [])))
                    e2 = {v.get("number") for v in t2["volumes"]}
                    for n, (ib, dt, rt) in fill:
                        if n not in e2: t2["volumes"].append({"number": n, "asin": None, "isbn13": ib, "cover_url": None, "release_date": dt})
                    t2["volumes"].sort(key=lambda v: v.get("number") or 0)
                    open(pv, "w", encoding="utf-8").write(yaml.dump(dd, allow_unicode=True, sort_keys=False))
                # 種4 series_key は stub の _skey から(promote durability)。無ければ slug
                sk = f"slug:{slug}"
                stub = os.path.join(ROOT, "data", "manga", slug + ".yml")
                if os.path.exists(stub):
                    mm = re.search(r"_skey:\s*(.+)", open(stub, encoding="utf-8").read())
                    if mm: sk = mm.group(1).strip()
                ents = [{"series_keys": [sk], "number": n, "isbn13": ib, "release_date": dt,
                         "edition_type": "standard", "title_display": rt[:42], "source": "rakuten",
                         "added_at": "2026-06-21", "note": f"OFFSET低巻補完(vol1無印題対応・題完全一致+著者)。{slug}"} for n, (ib, dt, rt) in fill]
                txt = yaml.dump(ents, allow_unicode=True, sort_keys=False, default_flow_style=False)
                s4f.write("\n" + "\n".join("  " + l if l.strip() else l for l in txt.split("\n"))); s4f.flush()
                lf.write(json.dumps({"slug": slug, "op": "offset_fill", "vols": [n for n, _ in fill], "at": st}, ensure_ascii=False) + "\n"); lf.flush()
            print(f"  [{i+1}/{len(todo)}] {slug} +{[n for n,_ in fill]}", flush=True)
        else:
            nskip += 1
        done.add(slug)
        if (i + 1) % 25 == 0:
            json.dump(sorted(done), open(donef, "w", encoding="utf-8"))
            print(f"  ...{i+1} processed (works補完{nworks}/巻{nfill}/skip{nskip})", flush=True)
    json.dump(sorted(done), open(donef, "w", encoding="utf-8"))
    s4f.close(); lf.close()
    print(f"完了: works補完{nworks} / 巻{nfill} / skip{nskip}", flush=True)

if __name__ == "__main__":
    main()
