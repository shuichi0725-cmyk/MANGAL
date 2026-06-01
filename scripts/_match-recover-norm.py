"""matcher改善: 強正規化 × 著者一致ゲート で安全に未マッチを回収。

★正確性最優先の3ゲート:
  1. title 強正規化(NFKC全角統一+全記号/空白/上付き/ローマ数字除去)で native exact一致
  2. ★著者 overlap 必須(同名異作=中華一番/ガンダム型の誤マッチを防ぐ安全弁)
  3. ★1:1 衝突は保守的に skip(a_idを複数ページ/ページが複数a_id=曖昧→不採用)、 既存マッチ不可侵
出力: .cache/match-recovery.tsv(s3_key, a_id, a_native, note)。 enrich builderが追加読み。
"""
import sys, json, gzip, sqlite3, re, unicodedata
from collections import defaultdict
import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = "."
HIRA = str.maketrans({chr(c): chr(c + 0x60) for c in range(0x3041, 0x3097)})
# ローマ数字 → アラビア(title内)
ROMAN = {"Ⅰ": "1", "Ⅱ": "2", "Ⅲ": "3", "Ⅳ": "4", "Ⅴ": "5", "Ⅵ": "6", "Ⅶ": "7", "Ⅷ": "8", "Ⅸ": "9", "Ⅹ": "10"}


def tnorm(s):
    """title 強正規化: NFKC(全角半角/上付き統一)+ ローマ数字 + 英数かな漢字以外除去 + lower。"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    for k, v in ROMAN.items():
        s = s.replace(k, v)
    return re.sub(r"[^0-9a-zぁ-んァ-ヶ一-龯]", "", s.lower())


def anorm(s):
    if not s:
        return ""
    return re.sub(r"[\s　・･.,，、]+", "", unicodedata.normalize("NFKC", s).translate(HIRA)).lower()


def aforms(names):
    return {anorm(n) for n in names if n and isinstance(n, str) and len(anorm(n)) >= 2}


NONAUTH = re.compile(r"translat|letter|assist|editor|design|proofread|adapt", re.I)

# dump: tnorm(native) → [(a_id, author_forms, native)]
dump = defaultdict(list)
used_in_prod = set()
for line in gzip.open(".cache/anilist-manga-dump-v3.jsonl.gz", "rt", encoding="utf-8"):
    d = json.loads(line); t = d.get("title") or {}
    af = set()
    for e in (d.get("staff") or {}).get("edges", []):
        if NONAUTH.search(e.get("role", "")):
            continue
        nm = e["node"]["name"]; af |= aforms([nm.get("native"), nm.get("full")])
    nt = tnorm(t.get("native"))
    if nt:
        dump[nt].append((d["id"], af, t.get("native") or ""))

# 既存マッチ(production enrich の a_id)= 不可侵
en = json.load(open(".cache/anilist-enrich-map.json", encoding="utf-8"))
matched_keys = set(en.keys())
prod_aids = set(v["anilist_id"] for v in en.values() if isinstance(v, dict) and v.get("anilist_id"))

# merge → page
key2page = {}
for g in json.load(open("data/seeds/series-merge-auto.json", encoding="utf-8"))["merges"]:
    for k in (g.get("merge_keys") or []):
        key2page[k] = g["merge_keys"][0]
for e in (yaml.safe_load(open("data/seeds/series-merge.yml", encoding="utf-8")) or []):
    mk = e.get("merge_keys") or []
    if len(mk) >= 2:
        for k in mk:
            key2page[k] = mk[0]

con = sqlite3.connect(".cache/db-v2.sqlite"); con.text_factory = lambda b: b.decode("utf-8", "replace")
s2a = defaultdict(set)
for k, nm, alt in con.execute(
    "SELECT s.series_key,m.name,m.alt_names FROM series s "
    "JOIN series_authors sa ON sa.series_id=s.id JOIN mangaka m ON m.id=sa.mangaka_id"):
    s2a[k] |= aforms([nm] + (alt.split("|") if alt else []))
title_of = dict(con.execute("SELECT series_key,title FROM series"))
con.close()

pmatched = set(key2page.get(k, k) for k in matched_keys)

# ページごとに候補 a_id(title強一致 AND 著者overlap)を集める
page_cand = defaultdict(dict)   # page → {a_id: (matched_series_key, native)}
for k, t in title_of.items():
    p = key2page.get(k, k)
    if p in pmatched:
        continue
    s2 = s2a.get(k)
    if not s2:
        continue
    for aid, af, native in dump.get(tnorm(t), []):
        if aid in prod_aids:
            continue          # 既存マッチ不可侵
        if af and (s2 & af):  # ★著者ゲート
            page_cand[p].setdefault(aid, (k, native))

# 1:1 衝突解決(保守的)
aid_pages = defaultdict(set)
for p, cands in page_cand.items():
    for aid in cands:
        aid_pages[aid].add(p)

rows = []
for p, cands in page_cand.items():
    if len(cands) != 1:        # ページが複数a_id=曖昧 → skip
        continue
    aid = next(iter(cands))
    if len(aid_pages[aid]) != 1:  # a_idを複数ページが奪い合う → skip
        continue
    sk, native = cands[aid]
    rows.append((sk, aid, native))

with open(".cache/match-recovery.tsv", "w", encoding="utf-8") as f:
    f.write("s3_key\ta_id\ta_native\tnote\n")
    for sk, aid, native in rows:
        f.write(f"{sk}\t{aid}\t{native}\tnorm+author-gate\n")
print(f"★安全回収マッチ: {len(rows):,}件 → .cache/match-recovery.tsv")
print("=== サンプル12 ===")
for sk, aid, native in rows[:12]:
    print(f"  {sk.split('|')[-1][:22]:22} → {aid} 「{native[:20]}」")
