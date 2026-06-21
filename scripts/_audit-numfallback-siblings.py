#!/usr/bin/env python3
"""
数字fallback衝突slug の相方調査(READ-ONLY): 各fallbackのbase衝突群を集め、
clean(別作・姓化可→自動rename) / 隠れ異常(同著者ペンネーム/副題truncate/重複) を分類。
出力 data/seeds/numfallback-siblings.tsv。
"""
import sys, os, glob, re, unicodedata
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""
def naz(s): return re.sub(r"[\s　・！!？\?（）\(\)【】「」〜~,，、。:：;／/\.．’'\"＆&\-－]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

ym = yaml.load(open(os.path.join(ROOT, "data", "seeds", "author-yomi.yml"), encoding="utf-8"), Loader=L).get("yomi", {})
KANJI = re.compile(r"[一-鿿]")
HEPBURN = {"カ":"ka","キ":"ki","ク":"ku","ケ":"ke","コ":"ko","サ":"sa","シ":"shi","ス":"su","セ":"se","ソ":"so","タ":"ta","チ":"chi","ツ":"tsu","テ":"te","ト":"to","ナ":"na","ニ":"ni","ヌ":"nu","ネ":"ne","ノ":"no","ハ":"ha","ヒ":"hi","フ":"fu","ヘ":"he","ホ":"ho","マ":"ma","ミ":"mi","ム":"mu","メ":"me","モ":"mo","ヤ":"ya","ユ":"yu","ヨ":"yo","ラ":"ra","リ":"ri","ル":"ru","レ":"re","ロ":"ro","ワ":"wa","ガ":"ga","ギ":"gi","グ":"gu","ゲ":"ge","ゴ":"go","ザ":"za","ジ":"ji","ズ":"zu","ゼ":"ze","ゾ":"zo","ダ":"da","ヂ":"ji","ヅ":"zu","デ":"de","ド":"do","バ":"ba","ビ":"bi","ブ":"bu","ベ":"be","ボ":"bo","パ":"pa","ピ":"pi","プ":"pu","ペ":"pe","ポ":"po","ア":"a","イ":"i","ウ":"u","エ":"e","オ":"o","ン":"n","ー":""}

def load(slug):
    fp = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
    if not os.path.exists(fp): return None
    try: d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
    except: return None
    au = (d.get("authors") or [{}])[0]
    isb = next((to13(v.get("isbn13")) for e in (d.get("editions") or []) for v in (e.get("volumes") or []) if to13(v.get("isbn13"))), "")
    return {"title": str(d.get("title") or ""), "author": au.get("name") or "",
            "year": d.get("year_started"), "isbn": isb,
            "vols": sum(len(e.get("volumes") or []) for e in (d.get("editions") or []))}

# 14候補(誤検出除外済)を slug-numfallback.tsv から再取得し、題に数字含むものを除外
rows = [r.split("\t") for r in open(os.path.join(ROOT, "data", "seeds", "slug-numfallback.tsv"), encoding="utf-8").read().splitlines()[1:]]
targets = []
for c in rows:
    slug, num = c[0], c[2]
    d = load(slug)
    if not d: continue
    if num in re.sub(r"[^0-9]", "", unicodedata.normalize("NFKC", d["title"])): continue  # 題に数字=誤検出
    targets.append((slug, num, d))

out = open(os.path.join(ROOT, "data", "seeds", "numfallback-siblings.tsv"), "w", encoding="utf-8")
out.write("slug\tclass\ttitle\tauthor\tnewslug_proposed\tsiblings\n")
cnt = {}
for slug, num, d in targets:
    base = slug[:-(len(num) + 1)]
    sibs = [os.path.basename(f)[:-4] for f in glob.glob(os.path.join(ROOT, "data", "manga.v2", base + "*.yml")) if "kobobak" not in f]
    sibs = [s for s in sibs if s != slug and (s == base or re.match(rf"^{re.escape(base)}-", s))]
    sibinfo = []
    dup = penname = trunc = False
    for s in sibs:
        sd = load(s)
        if not sd: continue
        sibinfo.append(f"{s}[{sd['author']}/{sd['year']}/{sd['isbn'][-4:] if sd['isbn'] else '-'}]")
        if sd["isbn"] and sd["isbn"] == d["isbn"]: dup = True
        if naz(sd["author"]) and naz(sd["author"]) == naz(d["author"]): penname = True
        # 相方の題がfallback題を内包(=fallback側がtruncate) or 逆
        if naz(d["title"]) and naz(sd["title"]) and (naz(d["title"]) in naz(sd["title"]) or naz(sd["title"]) in naz(d["title"])) and naz(d["title"]) != naz(sd["title"]):
            trunc = True
    # 姓化可否
    yomi = d["author"] and (ym.get(d["author"]) or ym.get(d["author"].split("／")[0].strip()))
    surname = ""
    if yomi:
        # 姓 = 読みの先頭(漢字姓は最初の意味塊だが簡易に読み全体の頭をヘボン)→ 実用上は姓パートが取れない事多いので読み頭3-4モーラ
        kk = "".join(HEPBURN.get(ch, ch if re.match(r"[a-z0-9]", ch) else "") for ch in unicodedata.normalize("NFKC", yomi))
        surname = re.sub(r"[^a-z0-9]", "", kk)[:10]
    if dup: cls = "DUPLICATE"
    elif penname: cls = "SAME_AUTHOR(penname?)"
    elif trunc: cls = "TITLE_TRUNCATE"
    elif not yomi: cls = "NO_KANA"
    elif not sibs: cls = "NO_SIBLING(?)"
    else: cls = "CLEAN_AUTO"
    cnt[cls] = cnt.get(cls, 0) + 1
    newslug = f"{base}-{surname}-{d['year']}" if cls == "CLEAN_AUTO" and surname and d["year"] else ""
    out.write(f"{slug}\t{cls}\t{d['title']}\t{d['author']}\t{newslug}\t{' '.join(sibinfo)}\n")
out.close()
print(f"調査 {len(targets)}件:")
for k, v in sorted(cnt.items(), key=lambda x: -x[1]): print(f"  {k}: {v}")
print()
for r in open(os.path.join(ROOT, "data", "seeds", "numfallback-siblings.tsv"), encoding="utf-8").read().splitlines()[1:]:
    c = r.split("\t")
    print(f"[{c[1]}] {c[0]} | {c[2][:16]} | {c[3]} | →{c[4] or '-'} | 相方:{c[5][:50]}")
