"""B2残: 504/NDL典拠に無い著者の読みを NDL SRU by-creator(本の記録)から精密取得。
per-Agent抽出+検証(カタカナ・長さ・名前一致)。 非人物(組織/製作委員会等)は除外。 中断耐性。
"""
import json, sys, re, html, time, os, urllib.request, urllib.parse
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
ROOT = "C:/Users/shuic/code/MANGAL"

ranked = json.load(open(ROOT + "/.cache/b2-variant-junk.json", encoding="utf-8"))["genuine_ranked"]
CACHE = ROOT + "/.cache/b2-web-yomi.json"
out = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}

# 非人物パターン(組織/プロジェクト/合同) = 除外
ORG = re.compile(r"製作委員会|プロジェクト|グループ|出版|\(株\)|（株）|プロ$|運営|委員会|Team|ＳＮＥ|スタジオ|サンライズ|パブリッシャ|honeybee|製作|企画|編集部|鎮守府|＆|&|/")
def is_indiv(n):
    if ORG.search(n): return False
    if re.fullmatch(r"[A-Za-z0-9\.\-\s&!\?'’]+", n): return False  # latinのみ=別枠
    if re.search(r"\d", n): return False
    return True

def fetch(name):
    url = ("https://ndlsearch.ndl.go.jp/api/sru?operation=searchRetrieve&recordSchema=dcndl"
           "&maximumRecords=8&query=" + urllib.parse.quote('creator="%s"' % name))
    x = html.unescape(urllib.request.urlopen(url, timeout=25).read().decode("utf-8"))
    nn = name.replace(" ", "")
    c = Counter()
    for ag in re.findall(r"<foaf:Agent\b.*?</foaf:Agent>", x, re.S):
        nm = re.search(r"<foaf:name>(.*?)</foaf:name>", ag, re.S)
        tr = re.search(r"<dcndl:transcription>(.*?)</dcndl:transcription>", ag, re.S)
        if not nm or not tr:
            continue
        if nm.group(1).replace(" ", "") != nn:   # ★同一Agent内で名前完全一致のみ
            continue
        t = re.sub(r"[\s　,、]", "", tr.group(1))
        t = re.sub(r"\d{4}-?\d{0,4}$", "", t)     # 生没年除去
        if re.fullmatch(r"[ァ-ヶー]+", t) and 2 <= len(t) <= 14:  # カタカナ・妥当長
            c[t] += 1
    return c.most_common(1)[0][0] if c else ""

todo = [n for n in ranked if is_indiv(n) and n not in out][:400]  # 上位の個人作家400に限定
print("対象(個人・上位):", len(todo), flush=True)
ok = 0
for i, nm in enumerate(todo, 1):
    try:
        y = fetch(nm)
        out[nm] = y
        if y: ok += 1
    except Exception:
        out[nm] = ""
    time.sleep(0.25)
    if i % 50 == 0:
        json.dump(out, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        print("  %d/%d ok=%d" % (i, len(todo), ok), flush=True)
json.dump(out, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
print("完了: 取得%d / 試行%d" % (sum(1 for v in out.values() if v), len(out)), flush=True)
