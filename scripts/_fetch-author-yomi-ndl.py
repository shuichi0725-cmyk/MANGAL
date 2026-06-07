"""B2: 著者ヨミを NDL典拠(ma:ndla ID直引き)で取得。 504にyomi無だがndla有の漢字著者用。
ja-Kana transcription を抽出 → 姓名連結カタカナ。 中断耐性(.cache/b2-ndl-yomi.json)。
"""
import json, sys, re, html, time, os
import urllib.request
sys.stdout.reconfigure(encoding="utf-8")
ROOT = "C:/Users/shuic/code/MANGAL"

todo = json.load(open(ROOT + "/.cache/b2-ndl-todo.json", encoding="utf-8"))  # {name: ndla_url}
CACHE = ROOT + "/.cache/b2-ndl-yomi.json"
out = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}

def clean_yomi(raw):
    # "タカハシ, ルミコ, 1957-" → "タカハシルミコ"。 日付/数字/latin部は捨て、 かな部のみ連結
    parts = [p.strip() for p in raw.split(",")]
    keep = []
    for p in parts:
        if re.search(r"\d", p):
            continue
        if re.search(r"[ァ-ヶーぁ-ん]", p):  # かな含む部のみ
            keep.append(re.sub(r"[\s　]", "", p))
    return "".join(keep)

def fetch(eid):
    url = "https://id.ndl.go.jp/auth/ndlna/%s.rdf" % eid
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MANGAL author-yomi)"})
    x = html.unescape(urllib.request.urlopen(req, timeout=25).read().decode("utf-8"))
    m = re.search(r'<ndl:transcription xml:lang="ja-Kana">(.*?)</ndl:transcription>', x, re.S)
    return clean_yomi(m.group(1)) if m else ""

names = [n for n in todo if n not in out]
print("対象 %d / 既取得 %d / 残 %d" % (len(todo), len(out), len(names)), flush=True)
ok = miss = err = 0
for i, nm in enumerate(names, 1):
    eid = todo[nm].rstrip("/").split("/")[-1]
    try:
        y = fetch(eid)
        out[nm] = y
        if y:
            ok += 1
        else:
            miss += 1
    except Exception:
        err += 1
        out[nm] = ""  # 失敗も記録(web fallbackへ回す)
    time.sleep(0.2)
    if i % 200 == 0:
        json.dump(out, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        print("  %d/%d (ok=%d miss=%d err=%d)" % (i, len(names), ok, miss, err), flush=True)
json.dump(out, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
got = sum(1 for v in out.values() if v)
print("完了: 取得%d / 空%d / 計%d" % (got, len(out) - got, len(out)), flush=True)
