"""slug修正対象の権威フリガナをNDLから取得(楽天無し+楽天MADB乖離分)。1.2秒/件・resumable。"""
import json, yaml, os, re, time, unicodedata, urllib.request, sys
sys.stdout.reconfigure(encoding="utf-8")
ROOT = "C:/Users/shuic/code/MANGAL"
CACHE = ROOT + "/.cache/slugfix-ndl-yomi.json"

fix = dict(json.load(open(ROOT + "/data/seeds/slug-fix-candidates-2026.json", encoding="utf-8")))
om = json.load(open(ROOT + "/.cache/slug-fix-omissions-merged.json", encoding="utf-8")) if os.path.exists(ROOT + "/.cache/slug-fix-omissions-merged.json") else {}
fix.update(om)
rk = json.load(open(ROOT + "/.cache/rakuten-titlekana.json", encoding="utf-8"))

def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")); return re.sub(r"[ー\s・:：/／、。!！?？]", "", s)

# 各slugの先頭ISBN + MADB kana
need = []  # (slug, isbn)
for sl in fix:
    f = ROOT + "/.preview-data/manga/" + sl + ".yml"
    if not os.path.exists(f): continue
    d = yaml.safe_load(open(f, encoding="utf-8"))
    mk = norm((d.get("title_kana") or "").split(":")[0].split("/")[0])
    isbns = [v.get("isbn13") for e in d.get("editions", []) for v in e.get("volumes", []) if v.get("isbn13")]
    if not isbns: continue
    rtk = rk.get(sl)
    # 楽天有り かつ MADBと一致(>=0.75) ならNDL不要(2ソース合意済)
    if rtk:
        import difflib
        rn = norm(rtk)
        if mk and difflib.SequenceMatcher(None, mk, rn[:len(mk)+3]).ratio() >= 0.75:
            continue
    need.append((sl, isbns[:2]))  # 先頭2 ISBN試行

cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
print(f"NDL照会対象: {len(need)} slug (キャッシュ済 {len(cache)})", flush=True)

def ndl_yomi(isbn):
    url = f"https://ndlsearch.ndl.go.jp/api/opensearch?isbn={isbn}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 mangal-furigana"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = r.read().decode("utf-8", "replace")
        ms = re.findall(r"<dcndl:titleTranscription>(.*?)</dcndl:titleTranscription>", d)
        return ms[0].strip() if ms else ""
    except Exception:
        return None

done = 0
for sl, isbns in need:
    if sl in cache:
        continue
    val = ""
    for ib in isbns:
        y = ndl_yomi(ib)
        time.sleep(1.2)
        if y:
            val = y; break
    cache[sl] = val
    done += 1
    if done % 25 == 0:
        json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  {done}/{len(need)} 取得 (yomi有 {sum(1 for v in cache.values() if v)})", flush=True)
json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
print(f"完了: {len(cache)} slug / yomi取得 {sum(1 for v in cache.values() if v)}", flush=True)
