"""テストページを2026新刊だけに入れ替え: in-scope新刊をテストページ化(.preview-data)。
書影/caption(synopsis)/著者/発売日付き。型1=新刊巻・型3=新規。kanaは題fallback(索引表示用)。
種2/本番不変。usage: python _distill_preview.py"""
import csv, json, os, re, glob, unicodedata
ROOT = "C:/Users/shuic/code/MANGAL"
PREV = f"{ROOT}/.preview-data/manga"

def clean_title(t):
    t = re.sub(r"\s*=\s*[A-Za-z].*$", "", str(t or ""))  # = 英題除去
    return t.strip()
def volnum(t):
    m = re.search(r"[\.．]\s*(\d+)\s*$", str(t or "")) or re.search(r"Vol(?:ume)?\.?\s*(\d+)", str(t or ""), re.I)
    return int(m.group(1)) if m else 1
def rough_kana(t):
    # 索引用の暫定kana(無いと索引skip)。本来はNDL読みをfetch(holes=kana[調べる])。
    return unicodedata.normalize("NFKC", str(t or ""))[:40]

enr = {json.loads(l)["isbn"]: json.loads(l) for l in open(f"{ROOT}/data/seeds/distill-enrich-2026.jsonl", encoding="utf-8")}
disc = {r["isbn13"]: r for r in csv.DictReader(open(f"{ROOT}/data/seeds/ndl-discovery-2026.tsv", encoding="utf-8"), delimiter="\t")}
ledger = {r["isbn"]: r for r in csv.DictReader(open(f"{ROOT}/data/seeds/distill-ledger-2026.tsv", encoding="utf-8"), delimiter="\t")}
manifest = [r for r in csv.DictReader(open(f"{ROOT}/.cache/madb-distill/ndl-manifest.tsv", encoding="utf-8"), delimiter="\t") if r["scope"] == "in"]

# 既存テストページを全消去(新刊だけに入れ替え)
removed = 0
for f in glob.glob(f"{PREV}/*.yml"):
    os.remove(f); removed += 1
print(f"既存テストページ消去: {removed}", flush=True)

import yaml
n = 0
for r in manifest:
    ib = r["isbn"]; e = enr.get(ib, {}); d = disc.get(ib, {}); lt = ledger.get(ib, {})
    full = d.get("title", r["title"]); title = clean_title(full); vn = volnum(full)
    cre = d.get("creators", "")
    authors = [{"name": re.sub(r"\s*(著|原作|作画|漫画|/.*)$", "", a).strip(), "role": "writer_artist"}
               for a in cre.split("/")[:3] if a.strip()]
    cover = e.get("cover") if (e.get("cover") and "noimage" not in (e.get("cover") or "")) else None
    syn = (e.get("caption") or "")[:140]
    status = lt.get("status", "")
    badge = ("型1新刊巻" if lt.get("type", "").startswith("型1") else "型3新規") + (" [要fill]" if status.startswith("要fill") else (" [hold]" if status.startswith("hold") else " [ship]"))
    # ★プレビュー表示用の暫定fill(index必須欄)。 本来は holes=作る/調べる で正式fill。
    yr = int(re.sub(r"\D", "", str(d.get("date", "2026"))[:4]) or 2026)
    blob = title + " " + syn
    GK = [("isekai", r"異世界|転生|転移"), ("romance", r"恋|愛|初恋|婚約|令嬢|溺愛|結婚"), ("romcom", r"ラブコメ"),
          ("fantasy", r"魔法|魔王|勇者|ドラゴン|精霊|ファンタジ"), ("action", r"バトル|戦|討伐|戦争|復讐"),
          ("gourmet", r"グルメ|料理|ごはん|めし|食"), ("horror", r"ホラー|怪|恐怖|呪|ゾンビ"),
          ("mystery", r"ミステリ|探偵|殺人|事件|謎"), ("school", r"学園|高校|JK|青春"),
          ("ecchi", r"えっち|エロ|お色気|発情|パコ"), ("comedy", r"ギャグ|コメディ|笑")]
    gs = [k for k, pat in GK if re.search(pat, blob)][:3] or ["drama"]
    doc = {"slug": f"z{ib}", "title": title, "title_kana": rough_kana(title),
           "title_romaji": re.sub(r"[^a-z0-9]+", "-", (e.get("rk_title") or title).lower()).strip("-")[:40] or f"shinkan-{ib}",
           "year_started": yr, "subtitle": None, "authors": authors or [{"name": "(unknown)", "role": "writer_artist"}],
           "publisher": "(unknown)", "genres": gs, "genres_provisional": True,
           "first_volume_date": d.get("date", ""), "synopsis": syn,
           "_distill": f"2026新刊 {badge} ISBN{ib}",
           "editions": [{"type": "standard", "label": "通常版",
                         "volumes": [{"number": vn, "isbn13": ib, "release_date": d.get("date", ""), "cover_url": cover}]}]}
    yaml.safe_dump(doc, open(f"{PREV}/z{ib}.yml", "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
    n += 1
print(f"2026新刊テストページ生成: {n} (書影有 {sum(1 for r in manifest if (enr.get(r['isbn'],{}).get('cover') and 'noimage' not in (enr.get(r['isbn'],{}).get('cover') or '')))})")
