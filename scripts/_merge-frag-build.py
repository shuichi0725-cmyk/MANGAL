"""merge377清掃の提案生成+検証ダンプ(まだ書き込まない・read-only)。

同題+著者共有の分裂クラスタごとに、 ★関係する auto群の全 series_key を漏れなく union
(上書き式 load_merge_sids で orphan を出さないため)。 各ページの巻/年/副題/著者を
並べ、 版違い(=統合OK)か別作品(=誤統合)かを目視できる形で出力。
提案は .cache/merge-frag-proposal.json に保存(適用は別ステップ)。
"""
import sys, json, csv, sqlite3, importlib.util, re, unicodedata
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]  # 旧PCパス→動的導出(2026-07-21一括是正)
csv.field_size_limit(10**7)
spec = importlib.util.spec_from_file_location("promote", ROOT / "scripts/_promote-bulk-v2.py")
pm = importlib.util.module_from_spec(spec); sys.argv = ["x"]; spec.loader.exec_module(pm)
PRE, CON, SUBP = pm.DROP_TITLE_PREFIX_PATTERNS, pm.DROP_TITLE_CONTAINS_PATTERNS, pm.DROP_SUBTITLE_PATTERNS

def norm(s):
    return re.sub(r"[^a-z0-9ぁ-んァ-ヶ一-龯]", "", unicodedata.normalize("NFKC", s or "").lower())

# auto-merge: canonical → 全merge_keys、 key → canonical
auto_full = {}; key2page = {}
for g in json.load((ROOT / "data/seeds/series-merge-auto.json").open(encoding="utf-8"))["merges"]:
    mk = g.get("merge_keys") or []
    if not mk: continue
    auto_full[mk[0]] = mk
    for k in mk: key2page[k] = mk[0]

# ページ構築 + 各ページの slug-final メンバー
pages = defaultdict(lambda: {"members": [], "title": None, "vols": 0, "year": ""})
with (ROOT / ".cache/slug-final.tsv").open(encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        pid = key2page.get(row["key"], row["rep"])
        p = pages[pid]; p["members"].append(row["key"])
        try: v = int(row["vols"] or 0)
        except: v = 0
        if p["title"] is None or v > p["vols"]:
            p["title"] = row["title"]; p["vols"] = v; p["year"] = row.get("year", "")

con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite"); con.text_factory = lambda b: b.decode("utf-8", "replace")
id2key = {}; s_sub = {}; s_adult = {}
for sid, k, sub, ad in con.execute("SELECT id, series_key, subtitle, adult_score FROM series"):
    id2key[sid] = k; s_sub[k] = sub or ""; s_adult[k] = ad or 0
key_auth = defaultdict(set)
for sid, mid in con.execute("SELECT series_id, mangaka_id FROM series_authors"):
    if sid in id2key: key_auth[id2key[sid]].add(mid)
aname = {i: n for i, n in con.execute("SELECT id, name FROM mangaka")}
con.close()
mag = set()
import yaml
for e in (yaml.safe_load((ROOT / "data/seeds/magazines-drop.yml").read_text(encoding="utf-8")) or {}).get("magazines", []):
    if e.get("series_key"): mag.add(e["series_key"])

# 公開フィルタ
pub = {}
for pid, p in pages.items():
    title = p["title"] or ""; members = p["members"]
    if any(title.startswith(x) for x in PRE): continue
    if any(x in title for x in CON): continue
    if any(m in mag for m in members): continue
    if any(x in s_sub.get(m, "") for m in members for x in SUBP): continue
    authors = set()
    for m in members: authors |= key_auth.get(m, set())
    pub[pid] = {"title": title, "ntitle": norm(title), "authors": authors,
                "members": members, "vols": p["vols"], "year": p["year"]}

def full_keys(pid, members):
    """ページの完全 series_key 集合 = auto群全体 ∪ slug-finalメンバー。"""
    ks = set(members)
    if pid in auto_full: ks |= set(auto_full[pid])
    return ks

# 同題で著者共有クラスタリング
bytitle = defaultdict(list)
for pid, p in pub.items():
    if p["ntitle"]: bytitle[p["ntitle"]].append(pid)

# ★著者集合「完全一致」でグループ化(交差でなく=ハブ著者連結を断つ)。
#   さらに 単著者(=監修/常連の巻き込みが起きにくい)を安全側とする。
proposals = []
for nt, pids in bytitle.items():
    if len(pids) < 2: continue
    by_aset = defaultdict(list)
    for pid in pids:
        a = pub[pid]["authors"]
        if not a: continue  # 無著者は対象外(誤統合源)
        by_aset[frozenset(a)].append(pid)
    for aset, grp in by_aset.items():
        if len(grp) < 2: continue
        allkeys = set()
        for pid in grp: allkeys |= full_keys(pid, pub[pid]["members"])
        # 副題整合チェック: cluster内メンバーの非空副題集合。 1種以上=スピンオフ混入疑い→要レビュー
        subs = set()
        for pid in grp:
            for m in pub[pid]["members"]:
                s = s_sub.get(m, "").strip()
                if s: subs.add(s)
        safe = (len(subs) == 0)  # 全員無副題のみ安全(番外編/外伝混入を排除)
        main = max(grp, key=lambda x: pub[x]["vols"])
        proposals.append({"main": pub[main]["title"], "ntitle": nt,
                          "pages": grp, "merge_keys": sorted(allkeys),
                          "n_authors": len(aset), "safe": safe, "subs": sorted(subs)})

proposals.sort(key=lambda x: -len(x["pages"]))
safe = [p for p in proposals if p["safe"]]
review = [p for p in proposals if not p["safe"]]
json.dump(safe, (ROOT / ".cache/merge-frag-proposal.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"全クラスタ {len(proposals)} = ★安全(無副題){len(safe)} + 要レビュー(副題混在){len(review)}")
print(f"安全分の統合keys合計: {sum(len(p['merge_keys']) for p in safe):,}  / 消えるページ {sum(len(p['pages'])-1 for p in safe):,}")

print("\n=== ★安全クラスタ(全員無副題=版違いのみ。 上位25)===")
for pr in safe[:25]:
    au = ",".join(aname.get(x, "?") for x in list(pub[pr['pages'][0]]['authors'])[:2])
    yrs = sorted({pub[pid]['year'] or '?' for pid in pr['pages']})
    print(f"  「{pr['main'][:24]}」{len(pr['pages'])}p 著者[{au[:22]}] 年{yrs}")

print(f"\n=== 要レビュー(副題混在=番外編/外伝の疑い、 統合しない。 {len(review)}件)===")
for pr in review[:15]:
    print(f"  「{pr['main'][:24]}」{len(pr['pages'])}p 副題{pr['subs'][:3]}")
