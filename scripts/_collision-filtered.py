"""collision-detail を promote 全 filter 適用後で再生成 = 真の本番衝突のみ。

適用 filter(promote 相当):
  - merge(slug-final の rep でページ集約済)
  - 成年除外(adult_score >= 3)
  - kept edition(standard/bunkobon/wideban/kanzenban/shinsoban/aizoban/deluxe を持つ)
  - title prefix drop(アニメ版/劇場版/ノベライズ/英訳…)
  - title contains drop(アンソロジー/ガイド/画集/傑作選…)
  - 雑誌 drop(magazines-drop.yml confirmed:true)
ページは「上記を全て通る member が1つでもあれば」生存。 生存ページ間の同 base_slug を衝突に。
出力: .cache/collisions-filtered.tsv + 集計。
"""
import sqlite3, json, csv, sys, re, unicodedata
from collections import defaultdict
from pathlib import Path
import yaml

sys.stdout.reconfigure(encoding="utf-8")
DB = Path(".cache/db-v2.sqlite")
KEEP = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban", "deluxe"}
PREFIX = ["テレビアニメ版", "TVアニメ版", "TVアニメ", "アニメコミック", "劇場版", "映画", "OVA", "ノベライズ", "ノベル", "英訳・", "英訳"]
CONTAINS = ["ガイドブック", "ファンブック", "設定資料集", "公式図録", "公式読本", "公式ファン", "公式コミックガイド",
            "アンソロジー", "キャラクター名鑑", "人物名鑑", "キャラクターブック", "心理分析", "心理解析", "完全解析",
            "完全攻略", "攻略本", "解析書", "解体新書", "解体全書", "大研究", "最終研究", "超研究", "大事典", "大百科",
            "大解剖", "パーフェクトガイド", "完全読本", "完全ガイド", "必勝法", "の秘密", "の謎", "コミック大全",
            "コミックスペシャル", "ナビゲーション", "考察", "傑作選", "傑作集", "ベストセレクション", "特集号",
            "特別総集編", "名作集", "名作選", "自選", "総集編", "原画集", "画集", "ポケット画廊", "うちあけ話"]


def norm(s):
    return re.sub(r"[^a-z0-9ぁ-んァ-ヶ一-龯]", "", unicodedata.normalize("NFKC", s or "").lower())


def main():
    mag = set()
    for e in yaml.safe_load(Path("data/seeds/magazines-drop.yml").read_text(encoding="utf-8"))["magazines"]:
        if e["confirmed"]:
            mag.add(norm(e["title"]))

    con = sqlite3.connect(DB); con.text_factory = lambda b: b.decode("utf-8", "replace")
    c = con.cursor()
    adult = {}; title = {}
    for sid, t, a in c.execute("SELECT id, title, adult_score FROM series"):
        adult[sid] = a or 0; title[sid] = t or ""
    etype = defaultdict(set)
    for sid, typ in c.execute("SELECT series_id, type FROM editions"):
        etype[sid].add(typ)
    key2sid = {k: sid for sid, k in c.execute("SELECT id, series_key FROM series")}
    con.close()

    def member_ok(sid):
        if adult.get(sid, 0) >= 3: return False
        if not (etype.get(sid, set()) & KEEP): return False
        t = title.get(sid, "")
        if any(t.startswith(p) for p in PREFIX): return False
        if any(p in t for p in CONTAINS): return False
        if norm(t) in mag: return False
        return True

    mg = json.loads(Path("data/seeds/series-merge-auto.json").read_text(encoding="utf-8"))["merges"]
    grp_keys = defaultdict(list)
    key2grp = {}
    for i, g in enumerate(mg):
        for k in g["merge_keys"]:
            key2grp[k] = i; grp_keys[i].append(k)

    rows = list(csv.DictReader(Path(".cache/slug-final.tsv").open(encoding="utf-8"), delimiter="\t"))
    page_base = {}; page_members = {}
    for r in rows:
        rep = r["rep"]
        if rep in page_members: continue
        gi = key2grp.get(rep)
        keys = grp_keys[gi] if gi is not None else [rep]
        page_members[rep] = [key2sid.get(k) for k in keys if k in key2sid]
        page_base[rep] = r["base_slug"]

    surv = {rep for rep, sids in page_members.items() if any(member_ok(s) for s in sids if s)}
    base2pages = defaultdict(set)
    for rep in surv:
        base2pages[page_base[rep]].add(rep)
    coll = {b: ps for b, ps in base2pages.items() if len(ps) > 1}

    print(f"slug-final ページ: {len(page_members):,}")
    print(f"  ★promote 生存ページ(全filter後): {len(surv):,}")
    print(f"  ★生存ページ間の真の衝突 base: {len(coll):,}")
    print(f"  巻き込まれ生存ページ: {sum(len(ps) for ps in coll.values()):,}")

    aname = {}
    con = sqlite3.connect(DB); con.text_factory = lambda b: b.decode("utf-8", "replace")
    for mid, nm in con.execute("SELECT id, name FROM mangaka"): aname[mid] = nm
    sa = defaultdict(list)
    for sid, mid in con.execute("SELECT series_id, mangaka_id FROM series_authors"): sa[sid].append(aname.get(mid, '?'))
    con.close()
    with open(".cache/collisions-filtered.tsv", "w", encoding="utf-8") as f:
        f.write("base\ttitle\tauthors\tadult\n")
        for b, ps in sorted(coll.items()):
            for rep in ps:
                sids = [s for s in page_members[rep] if s]
                ttl = title.get(sids[0], "") if sids else ""
                au = set(); ad = 0
                for s in sids:
                    au |= set(sa.get(s, [])); ad = max(ad, adult.get(s, 0))
                f.write(f"{b}\t{ttl}\t{'|'.join(sorted(au)[:4])}\t{ad}\n")
    print("wrote .cache/collisions-filtered.tsv")


if __name__ == "__main__":
    main()
