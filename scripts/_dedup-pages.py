"""本番 manga.v2 の重複ページ検出(提案のみ・変更なし)。
判定 = ★ISBN集合の完全一致(最保守)。 ISBNが1つも無いページは対象外。
  - 同一ISBN集合 + 同一title → DUP(dedup提案)
  - 同一ISBN集合 + 別title  → FLAG(自動処理しない・個別判断)
canonical 選定: ①末尾 -数字 suffix 無し優先 ②短い方 ③辞書順。
出力: .cache/dedup-proposal.csv
"""
import glob, os, sys, re, collections, csv
import yaml
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)

pages = {}
for p in glob.glob(ROOT + "/data/manga.v2/*.yml"):
    try:
        d = yaml.safe_load(open(p, encoding="utf-8"))
    except Exception:
        continue
    if not d:
        continue
    isbns = set()
    nvol = 0
    for e in d.get("editions", []):
        for v in e.get("volumes", []):
            nvol += 1
            i = v.get("isbn13")
            if i:
                isbns.add(str(i))
    pages[d["slug"]] = {"title": d.get("title"), "isbns": frozenset(isbns), "nvol": nvol}

print("ページ:", len(pages))
bykey = collections.defaultdict(list)
for slug, info in pages.items():
    if info["isbns"]:                      # ISBN無しは対象外(保守)
        bykey[info["isbns"]].append(slug)

groups = {k: v for k, v in bykey.items() if len(v) >= 2}
print("ISBN集合が完全一致するグループ:", len(groups))

def canonical_rank(slug):
    has_suffix = 1 if re.search(r"-\d{1,4}$", slug) else 0
    return (has_suffix, len(slug), slug)

rows = []
flags = []
for key, slugs in groups.items():
    titles = {pages[s]["title"] for s in slugs}
    slugs_sorted = sorted(slugs, key=canonical_rank)
    canon = slugs_sorted[0]
    others = slugs_sorted[1:]
    if len(titles) == 1:
        for o in others:
            rows.append([o, canon, list(titles)[0], len(key), pages[o]["nvol"], pages[canon]["nvol"]])
    else:
        flags.append([" | ".join(slugs), " | ".join(sorted(t or "" for t in titles)), len(key)])

with open(ROOT + "/.cache/dedup-proposal.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["drop_slug", "canonical_slug", "title", "isbn数", "drop側vol数", "canon側vol数"])
    w.writerows(sorted(rows))
with open(ROOT + "/.cache/dedup-flag-difftitle.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["slugs", "titles(異なる!)", "isbn数"])
    w.writerows(flags)
print("DUP提案(同title+同ISBN集合):", len(rows), "→ .cache/dedup-proposal.csv")
print("FLAG(同ISBN集合だがtitle違い=要個別):", len(flags), "→ .cache/dedup-flag-difftitle.csv")
