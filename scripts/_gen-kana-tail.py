"""title_kana 空の残尾(327)を補完: 漢字=NDL by-title、 かな=題から抽出、 英字=題をkanaに。
fill seed (title-kana-fill.yml) へ純粋追加。 NDL照会は中断耐性(.cache/kana-tail-ndl.json)。
"""
import os, sys, re, glob, json, html, time
import urllib.request, urllib.parse
import yaml
sys.stdout.reconfigure(encoding="utf-8")
ROOT = "C:/Users/shuic/code/MANGAL"

# 1) v2 で kana空のページ → (slug, title)
empty = []
for f in glob.glob(ROOT + "/data/manga.v2/*.yml"):
    try:
        d = yaml.safe_load(open(f, encoding="utf-8"))
    except Exception:
        continue
    if d and not d.get("title_kana"):
        empty.append((d["slug"], d.get("title", "")))
print("kana空ページ:", len(empty))

# 2) slug → _skey(data/manga ソース)
def skey_of(slug):
    p = ROOT + "/data/manga/" + slug + ".yml"
    if os.path.exists(p):
        try:
            return (yaml.safe_load(open(p, encoding="utf-8")) or {}).get("_skey")
        except Exception:
            return None
    return None

def kata_extract(t):
    # かな(ひら→カタ)部分のみ抽出
    s = re.sub(r"[\s　]", "", t)
    out = []
    for c in s:
        if "ぁ" <= c <= "ん":
            out.append(chr(ord(c) + 0x60))  # ひら→カタ
        elif "ァ" <= c <= "ヶ" or c == "ー":
            out.append(c)
    return "".join(out)

# NDL by-title 読み(中断耐性)
NC = ROOT + "/.cache/kana-tail-ndl.json"
ndlc = json.load(open(NC, encoding="utf-8")) if os.path.exists(NC) else {}
def ndl_yomi(title):
    if title in ndlc:
        return ndlc[title]
    url = ("https://ndlsearch.ndl.go.jp/api/sru?operation=searchRetrieve&recordSchema=dcndl"
           "&maximumRecords=5&query=" + urllib.parse.quote('title="%s"' % title))
    try:
        x = html.unescape(urllib.request.urlopen(url, timeout=30).read().decode("utf-8"))
        # dc:title が title と一致する最初のレコードの transcription
        for m in re.finditer(r"<dc:title>.*?<rdf:value>(.*?)</rdf:value>.*?<dcndl:transcription>(.*?)</dcndl:transcription>", x, re.S):
            if m.group(1).strip() == title:
                ndlc[title] = m.group(2).strip(); return ndlc[title]
        # 一致なければ先頭
        m = re.search(r"<dc:title>.*?<dcndl:transcription>(.*?)</dcndl:transcription>", x, re.S)
        ndlc[title] = m.group(1).strip() if m else ""
    except Exception:
        ndlc[title] = ""
    return ndlc[title]

fills = []
n_ndl = n_kata = n_en = n_miss = 0
for i, (slug, title) in enumerate(empty, 1):
    sk = skey_of(slug)
    if not sk:
        continue
    has_kanji = bool(re.search(r"[一-龠]", title))
    has_kana = bool(re.search(r"[ぁ-んァ-ヶ]", title))
    kana = ""
    if has_kanji:
        kana = ndl_yomi(title)
        if kana:
            n_ndl += 1
        else:
            kana = re.sub(r"[\s　]", "", title)  # NDL無し=題名フォールバック(schema用、 後でAI読み候補)
            n_miss += 1
        if title not in ndlc:
            time.sleep(0.25)
    elif has_kana:
        kana = kata_extract(title); n_kata += 1
    else:  # 英字のみ
        kana = re.sub(r"[\s　]", "", title); n_en += 1
    if kana:
        fills.append({"key": sk, "kana_segmented": kana, "src": "tail"})
    if i % 40 == 0:
        json.dump(ndlc, open(NC, "w", encoding="utf-8"), ensure_ascii=False)
        print("  %d/%d (ndl=%d kata=%d en=%d miss=%d)" % (i, len(empty), n_ndl, n_kata, n_en, n_miss))
json.dump(ndlc, open(NC, "w", encoding="utf-8"), ensure_ascii=False)

# fill seed へ純粋追加
doc = yaml.safe_load(open(ROOT + "/data/seeds/title-kana-fill.yml", encoding="utf-8"))
have = {e["key"] for e in doc["fills"]}
add = 0
for fobj in fills:
    if fobj["key"] not in have:
        doc["fills"].append(fobj); have.add(fobj["key"]); add += 1
doc["fills"].sort(key=lambda x: x["key"])
with open(ROOT + "/data/seeds/title-kana-fill.yml", "w", encoding="utf-8") as fh:
    fh.write("# title_kana 補完(MADB + NDL by-ISBN + カタカナ題 + 残尾NDL by-title/抽出)\n")
    yaml.safe_dump({"fills": doc["fills"]}, fh, allow_unicode=True, sort_keys=False)
print("補完: NDL=%d 抽出=%d 英字=%d / fill追記=%d / 残(NDL読み無)=%d" % (n_ndl, n_kata, n_en, add, n_miss))
