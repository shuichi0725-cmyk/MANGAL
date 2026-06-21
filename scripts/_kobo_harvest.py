#!/usr/bin/env python3
"""
Kobo電子harvest: 対象作品を1回叩いて 書影+説明+電子リンク を一括取得。
書影=紙が無い巻に充当(純粋追加)。説明/リンク= kobo-harvest.jsonl(isbn13キー)に蓄積。
照合=題完全一致+著者+巻番号(電子はISBN無=題キー→厳格)。可逆・resume。
使い方: python _kobo_harvest.py <phase1|phase2|all> [limit] [--apply]
"""
import sys, os, json, re, time, unicodedata, urllib.request, urllib.parse, shutil
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L, CSafeDumper as Dp
except ImportError: from yaml import SafeLoader as L, SafeDumper as Dp
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env = {}
for ln in open(os.path.join(ROOT, ".env.local"), encoding="utf-8"):
    if "=" in ln and not ln.strip().startswith("#"):
        k, v = ln.split("=", 1); env[k.strip()] = v.strip()
from urllib.parse import urlparse
RREF = env["RAKUTEN_REFERER"]; _o = urlparse(RREF); RORG = f"{_o.scheme}://{_o.netloc}"

def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""
def naz(s): return re.sub(r"[\s　・！!？\?（）\(\)【】「」〔〕〜~,，、。:：;；/／\.．’'\"＆&\-]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()
def nau(s): return re.sub(r"[\s　・（）\(\)\[\]]", "", unicodedata.normalize("NFKC", str(s or "")))
def volnum(rt):
    t = unicodedata.normalize("NFKC", rt)
    m = re.search(r"[（(]\s*(\d+)\s*[）)]\s*$", t) or re.search(r"第\s*(\d+)\s*巻", t) or re.search(r"[　 ](\d+)\s*$", t)
    if m: return int(m.group(1)), naz(t[:m.start()])
    return None, naz(t)

def kobo(title, pg=1):
    time.sleep(1.0)
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"], "format": "json",
         "formatVersion": "2", "title": title, "hits": 30, "page": pg}
    u = "https://openapi.rakuten.co.jp/services/api/Kobo/EbookSearch/20170426?" + urllib.parse.urlencode(p)
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"Referer": RREF, "Origin": RORG, "User-Agent": "M/0.1", "Accept": "application/json"}), timeout=30).read())

def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "phase1"
    limit = next((int(a) for a in sys.argv[2:] if a.isdigit()), 10**9)
    apply = "--apply" in sys.argv
    tg = json.load(open(os.path.join(ROOT, ".cache", "_kobo_targets.json"), encoding="utf-8"))
    if phase == "all":
        slugs = tg["all"] if "all" in tg else (tg.get("phase1", []) + tg.get("phase2", []))
    else:
        slugs = tg[phase]
    donef = os.path.join(ROOT, ".cache", f"_kobo_done_{phase}.json")
    done = set(json.load(open(donef, encoding="utf-8"))) if os.path.exists(donef) else set()
    seedf = open(os.path.join(ROOT, "data", "seeds", "kobo-harvest.jsonl"), "a", encoding="utf-8") if apply else None
    st = time.strftime("%Y-%m-%dT%H:%M:%S")
    todo = [s for s in slugs if s not in done][:limit]
    print(f"{phase}: 対象{len(slugs)} / 済{len(done)} / 今回{len(todo)}", flush=True)
    n_cov = n_cap = n_link = n_work = 0
    for i, slug in enumerate(todo):
        fp = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
        if not os.path.exists(fp): done.add(slug); continue
        d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
        title = d.get("title"); base = naz(title)
        pau = set(nau(a.get("name")) for a in (d.get("authors") or []) if a.get("name"))
        # 巻番号 -> その巻のpaper isbn13 (代表)
        vol_isbn = {}
        for e in d.get("editions", []):
            for v in e.get("volumes", []):
                num = v.get("number")
                if isinstance(num, int) and to13(v.get("isbn13")): vol_isbn.setdefault(num, to13(v["isbn13"]))
        got = {}   # vol -> (img, caption, link, ktitle)
        try:
            for pg in (1, 2):
                r = kobo(title, pg)
                its = r.get("Items", [])
                if not its: break
                for it in its:
                    nvol, rest = volnum(it.get("title", ""))
                    if rest != base: continue
                    ra = nau(it.get("author", ""))
                    if pau and not any(pa and pa in ra for pa in pau): continue
                    if nvol is None: nvol = 1
                    img = it.get("largeImageUrl") or it.get("mediumImageUrl") or ""
                    if "noimage" in img: img = ""
                    if nvol not in got:
                        got[nvol] = (img.split("?")[0] + "?_ex=300x300" if img else "",
                                     (it.get("itemCaption") or "").strip(),
                                     it.get("affiliateUrl") or it.get("itemUrl") or "", it.get("title", ""))
                if r.get("count", 0) <= pg * 30: break
        except Exception as ex:
            print(f"  {slug} ERR {ex}", flush=True); continue
        if not got: done.add(slug); continue
        n_work += 1
        if apply:
            shutil.copy2(fp, fp + ".kobobak")
            ch = False
            for e in d.get("editions", []):
                for v in e.get("volumes", []):
                    num = v.get("number")
                    if num in got and not v.get("cover_url") and got[num][0]:
                        v["cover_url"] = got[num][0]; n_cov += 1; ch = True
            if ch:
                open(fp, "w", encoding="utf-8").write(yaml.dump(d, allow_unicode=True, sort_keys=False, Dumper=Dp))
                pv = os.path.join(ROOT, ".preview-data", "manga", slug + ".yml")
                if os.path.exists(pv):
                    dd = yaml.load(open(pv, encoding="utf-8"), Loader=L)
                    for e in dd.get("editions", []):
                        for v in e.get("volumes", []):
                            if v.get("number") in got and not v.get("cover_url") and got[v["number"]][0]:
                                v["cover_url"] = got[v["number"]][0]
                    open(pv, "w", encoding="utf-8").write(yaml.dump(dd, allow_unicode=True, sort_keys=False, Dumper=Dp))
            for num, (img, cap, link, kt) in got.items():
                ib = vol_isbn.get(num, "")
                if cap: n_cap += 1
                if link: n_link += 1
                seedf.write(json.dumps({"slug": slug, "number": num, "isbn13": ib, "kobo_img": img,
                                        "caption": cap, "kobo_link": link, "kobo_title": kt, "at": st}, ensure_ascii=False) + "\n")
            seedf.flush()
        done.add(slug)
        if (i + 1) % 25 == 0:
            json.dump(sorted(done), open(donef, "w", encoding="utf-8"))
            print(f"  ...{i+1}/{len(todo)} (作{n_work}/書影{n_cov}/説明{n_cap}/リンク{n_link})", flush=True)
    json.dump(sorted(done), open(donef, "w", encoding="utf-8"))
    if seedf: seedf.close()
    print(f"完了 {phase}: マッチ作{n_work} / 書影{n_cov} / 説明{n_cap} / 電子リンク{n_link}", flush=True)

if __name__ == "__main__":
    main()
