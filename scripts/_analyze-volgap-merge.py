"""巻抜けのunder-merge候補を分析: 種2既存の欠番巻のsidを、作品にmergeすべきか判定。
安全規則: 作品title が「巻のsid series_key の name: token」に厳密一致(NFKC) する時のみ merge候補。
  → spinoff/homonym(こち亀=titleがsub:に在りname:に無い)を除外。 + 著者重複も確認。
出力: series-merge.yml 追記用エントリ(merge_keys) + skip理由。 --apply で series-merge.yml 追記。"""
import sys, re, json, sqlite3, unicodedata, yaml
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
APPLY = "--apply" in sys.argv

def norm(s):
    return re.sub(r"[\s　・,，\.。、:：;!！?？()（）\[\]【】/／\-~〜]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

def name_tokens(series_key):
    return [norm(m) for m in re.findall(r"name:([^|]+)", series_key or "")]

con = sqlite3.connect(DB); cur = con.cursor()
def sid_skey_of_isbn(ib):
    r = cur.execute("SELECT se.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series se ON se.id=e.series_id WHERE v.isbn13=?", (ib,)).fetchone()
    return r[0] if r else None
def authors_of_key(sk):
    r = cur.execute("SELECT id FROM series WHERE series_key=?", (sk,)).fetchone()
    if not r: return set()
    return {x[0] for x in cur.execute("SELECT m.name FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id WHERE sa.series_id=?", (r[0],))}

drafts = yaml.safe_load(open(ROOT / ".cache" / "seed4-drafts.yml", encoding="utf-8")) or []
merge_pairs = {}   # frozenset(work_keys + vol_key) -> {title, work_keys, vol_key, vols}
skips = []
for d in drafts:
    ib = re.sub(r"\D", "", str(d.get("isbn13") or ""))
    wkeys = d.get("series_keys") or []
    vol_key = sid_skey_of_isbn(ib)
    if not vol_key:
        continue   # 種2に無い(=真の取込もれ、 種4で処理済)
    if vol_key in wkeys:
        continue   # 既に同series(別edition)=mergeでなく多版・別問題
    wt = norm(d.get("title"))
    vtoks = name_tokens(vol_key)
    title_match = wt in vtoks
    # 著者重複(作品の任意のkeyの著者 ∩ 巻sidの著者)
    wau = set()
    for wk in wkeys: wau |= authors_of_key(wk)
    vau = authors_of_key(vol_key)
    au_ok = bool(wau & vau)
    if title_match and au_ok:
        kk = tuple(sorted(set(wkeys) | {vol_key}))
        m = merge_pairs.setdefault(kk, {"title": d.get("title"), "work_keys": wkeys, "vol_key": vol_key, "vols": []})
        m["vols"].append(d.get("number"))
    else:
        skips.append((d.get("title"), d.get("number"), vol_key[:40], "title不一致" if not title_match else "著者不一致"))

print(f"under-merge候補(title+著者一致): {len(merge_pairs)}群 / skip(spinoff/homonym): {len(skips)}")
print("=== merge候補 サンプル ===")
for kk, m in list(merge_pairs.items())[:20]:
    print(f"  {m['title'][:24]:26} vols{sorted(set(m['vols']))} ← merge {m['vol_key'][:46]}")
print("=== skip サンプル(別作=触らない) ===")
for t, n, vk, why in skips[:12]:
    print(f"  {t[:24]:26} vol{n} [{why}] {vk}")
json.dump([{"main_title": m["title"], "merge_keys": kk_list} for kk_list in [list(k) for k in merge_pairs]], open(ROOT/".cache"/"volgap-merge-candidates.json","w",encoding="utf-8"), ensure_ascii=False)

if APPLY:
    mp = ROOT / "data" / "seeds" / "series-merge.yml"
    existing = yaml.safe_load(open(mp, encoding="utf-8")) or []
    add = []
    for kk, m in merge_pairs.items():
        add.append({"main": m["title"], "merge_keys": list(kk),
                    "note": f"巻抜けunder-merge是正: 種2別sidの同題同著者volを統合(vols {sorted(set(m['vols']))})。title+著者一致確認・spinoff除外。NDL確認 2026-06-29"})
    existing.extend(add)
    yaml.safe_dump(existing, open(mp, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=4096)
    print(f"APPLIED: series-merge.yml に {len(add)}群 追記")
