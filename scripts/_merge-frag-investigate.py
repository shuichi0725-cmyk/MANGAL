"""merge改善 調査(read-only): 公開ページの「真の分裂」を著者重複で定量化。

同題で複数ページの衝突を、 ページ間の著者(mangaka_id)重複で2分類:
  - 著者を共有 → ★分裂(同作品が別ページ = merge改善で統合すべき)
  - 著者が完全に別 → 真の同名異作(task2=表示区別の領域)
出力: 分裂クラスタ数・統合で消えるページ数・サンプル。 種2/種3/promote 不変。
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

# auto-merge canonical
key2page = {}
for g in json.load((ROOT / "data/seeds/series-merge-auto.json").open(encoding="utf-8"))["merges"]:
    mk = g.get("merge_keys") or []
    for k in mk: key2page[k] = mk[0]

# 公開ページ構築(dryrun report と同ロジック)
pages = defaultdict(lambda: {"members": [], "title": None, "vols": 0})
with (ROOT / ".cache/slug-final.tsv").open(encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        pid = key2page.get(row["key"], row["rep"])
        p = pages[pid]; p["members"].append(row["key"])
        try: v = int(row["vols"] or 0)
        except: v = 0
        if p["title"] is None or v > p["vols"]: p["title"] = row["title"]; p["vols"] = v

# 種2: series_key → 著者set / subtitle / adult
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

# 公開フィルタ後のページ + ページ著者集合
pub = {}
for pid, p in pages.items():
    title = p["title"] or ""; members = p["members"]
    if any(title.startswith(x) for x in PRE): continue
    if any(x in title for x in CON): continue
    if any(m in mag for m in members): continue
    if any(x in s_sub.get(m, "") for m in members for x in SUBP): continue
    authors = set()
    for m in members: authors |= key_auth.get(m, set())
    pub[pid] = {"title": title, "ntitle": norm(title), "authors": authors, "members": members}
print(f"公開ページ: {len(pub):,}")

# 同題グループ内で著者重複クラスタリング(union-find)
bytitle = defaultdict(list)
for pid, p in pub.items():
    if p["ntitle"]: bytitle[p["ntitle"]].append(pid)

frag_clusters = 0; frag_pages_collapsed = 0; distinct_pairs = 0
frag_examples = []; distinct_examples = []
for nt, pids in bytitle.items():
    if len(pids) < 2: continue
    # union-find: 著者を共有するページを統合
    parent = {pid: pid for pid in pids}
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for i in range(len(pids)):
        for j in range(i + 1, len(pids)):
            if pub[pids[i]]["authors"] & pub[pids[j]]["authors"]:
                parent[find(pids[i])] = find(pids[j])
    clusters = defaultdict(list)
    for pid in pids: clusters[find(pid)].append(pid)
    for root, grp in clusters.items():
        if len(grp) >= 2:  # 著者共有で繋がった = 分裂
            frag_clusters += 1; frag_pages_collapsed += len(grp) - 1
            if len(frag_examples) < 12:
                t = pub[grp[0]]["title"]; a = pub[grp[0]]["authors"]
                an = ",".join(aname.get(x, "?") for x in list(a)[:2])
                frag_examples.append(f"「{t[:22]}」{len(grp)}ページ 著者[{an}]")
    # 同題で著者disjointな別クラスタが2+ = 真の同名異作
    if len(clusters) >= 2:
        distinct_pairs += 1
        if len(distinct_examples) < 8:
            distinct_examples.append(f"「{pub[pids[0]]['title'][:22]}」 {len(clusters)}作品")

print(f"\n=== ★分裂(同題+著者共有 = 統合すべき)===")
print(f"  分裂クラスタ: {frag_clusters:,}  / 統合で消えるページ: {frag_pages_collapsed:,}")
for e in frag_examples: print(f"    {e}")
print(f"\n=== 真の同名異作(同題+著者別 = task2領域)===")
print(f"  同題で複数作品の題: {distinct_pairs:,}")
for e in distinct_examples: print(f"    {e}")
print(f"\n=== 結論 ===")
print(f"  merge改善で {frag_pages_collapsed:,} ページの重複が解消 → 公開 {len(pub)-frag_pages_collapsed:,} に")
