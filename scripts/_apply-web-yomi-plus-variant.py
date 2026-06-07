"""NDL by-creator取得(63)を author-yomi へ適用 + 異体字(旧字)名を正規化して再照会・救済。"""
import json, sys, re, html, time, urllib.request, urllib.parse, yaml
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
ROOT = "C:/Users/shuic/code/MANGAL"

doc = yaml.safe_load(open(ROOT + "/data/seeds/author-yomi.yml", encoding="utf-8")) or {"yomi": {}}
y = doc["yomi"]; before = len(y)

def good(name, kana):
    if not kana or not re.search(r"[ァ-ヶーぁ-ん]", kana): return False
    if re.sub(r"[\s　]", "", kana) == re.sub(r"[\s　]", "", name): return False
    return True

# ① web-yomi(NDL by-creator)適用
web = json.load(open(ROOT + "/.cache/b2-web-yomi.json", encoding="utf-8"))
a1 = 0
for nm, k in web.items():
    if k and nm not in y and good(nm, k): y[nm] = k; a1 += 1

# ② 異体字(旧字)救済: 失敗した個人名を正規化 → NDL by-creator 再照会
VAR = str.maketrans({"髙":"高","﨑":"崎","德":"徳","廣":"広","濵":"浜","桒":"桑","槇":"槙","劒":"剣","曻":"昇","眞":"真","靏":"鶴","硲":"硲"})
def ndl_creator(name):
    url = ("https://ndlsearch.ndl.go.jp/api/sru?operation=searchRetrieve&recordSchema=dcndl&maximumRecords=8&query="
           + urllib.parse.quote('creator="%s"' % name))
    x = html.unescape(urllib.request.urlopen(url, timeout=25).read().decode("utf-8"))
    nn = name.replace(" ", ""); c = Counter()
    for ag in re.findall(r"<foaf:Agent\b.*?</foaf:Agent>", x, re.S):
        nm = re.search(r"<foaf:name>(.*?)</foaf:name>", ag, re.S)
        tr = re.search(r"<dcndl:transcription>(.*?)</dcndl:transcription>", ag, re.S)
        if not nm or not tr or nm.group(1).replace(" ", "") != nn: continue
        t = re.sub(r"[\s　,、]", "", tr.group(1)); t = re.sub(r"\d{4}-?\d{0,4}$", "", t)
        if re.fullmatch(r"[ァ-ヶー]+", t) and 2 <= len(t) <= 14: c[t] += 1
    return c.most_common(1)[0][0] if c else ""

ranked = json.load(open(ROOT + "/.cache/b2-variant-junk.json", encoding="utf-8"))["genuine_ranked"]
# 旧字を含み未取得の名を正規化名で照会(上位500まで)
cand = [n for n in ranked[:1500] if n not in y and any(ch in n for ch in "髙﨑德廣濵桒槇劒曻眞靏")]
print("異体字候補:", len(cand), flush=True)
a2 = 0
for nm in cand:
    norm = nm.translate(VAR)
    try:
        k = ndl_creator(norm)
        if k and good(nm, k): y[nm] = k; a2 += 1; print("  救済 %s(→%s) = %s" % (nm, norm, k), flush=True)
    except Exception:
        pass
    time.sleep(0.25)

with open(ROOT + "/data/seeds/author-yomi.yml", "w", encoding="utf-8") as f:
    f.write("# 著者ヨミ(50音索引)= MADB504公式 + NDL典拠(ma:ndla) + NDL by-creator + 101 + AniList + カナ名 + 異体字救済。\n")
    f.write("# name→カタカナ。 純粋追加。 _gen-author-yomi/_fetch-author-yomi-ndl/_fetch-author-yomi-web。\n")
    yaml.safe_dump({"yomi": y}, f, allow_unicode=True, sort_keys=True)
print("author-yomi: %d → %d (web+%d / 異体字+%d)" % (before, len(y), a1, a2), flush=True)
