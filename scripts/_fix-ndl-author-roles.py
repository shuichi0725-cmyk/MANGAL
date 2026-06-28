"""NDL preview 223作の著者を NDL creators_roled から正確なrole付きに是正。
★一律writer_artist禁止([[feedback_never_default_author_role]])。原作/作画を分ける。
- 原作→writer / 作画・画→artist / 著・漫画・作(原作有時はartist,単独時writer_artist) / 編・監修・原案・訳等→credits(著者外)
- 役割不明(空)で単独creator→writer_artist(=単独漫画家の正しい解釈)。複数で空はwriter_artist(暫定)。
- authors が空になる作(編集/監修のみ=mook)はreportのみ(別途filter)。
"""
import glob, os, re, yaml, json, collections
ROOT = "C:/Users/shuic/code/MANGAL"
PREV = f"{ROOT}/.preview-data/manga"

# ISBN -> creators_roled (NDL discovery)
rl = {}
for fn in (f"{ROOT}/data/seeds/ndl-discovery-2024.tsv", f"{ROOT}/data/seeds/ndl-discovery-2025.tsv"):
    rows = open(fn, encoding="utf-8").read().splitlines()
    h = rows[0].split("\t"); I = {k: h.index(k) for k in h}
    if "creators_roled" not in I:
        continue
    for l in rows[1:]:
        c = l.split("\t"); ib = re.sub(r"\D", "", c[0]) if c else ""
        if ib and len(c) > I["creators_roled"]:
            rl[ib] = c[I["creators_roled"]]

CREDIT = {"編": "editor", "監修": "supervisor", "キャラクター原案": "character_design",
          "キャラクターデザイン": "character_design", "原案": "original_concept",
          "訳": "translator", "インタビュアー": "interviewer", "構成": "composition",
          "脚本": "screenplay", "企画": "planning", "協力": "cooperation"}

def parse_authors(cr):
    parts = [p for p in str(cr or "").split("/") if p.strip()]
    flat = []
    for p in parts:
        if ":" in p:
            nm, role = p.rsplit(":", 1)
        else:
            nm, role = p, ""
        role = role.strip()
        for n in re.split(r"[,、]", nm):
            n = n.strip()
            n = re.sub(r"\s+(インタビュアー|編集部)$", "", n)
            if n:
                flat.append((n, role))
    has_gensaku = any(r == "原作" for _, r in flat)
    n_main = sum(1 for _, r in flat if r in ("", "著", "漫画", "作", "原作", "作画", "画"))
    authors, credits = [], []
    for n, r in flat:
        if r == "原作":
            authors.append({"name": n, "role": "writer"})
        elif r in ("作画", "画"):
            authors.append({"name": n, "role": "artist"})
        elif r in ("著", "漫画", "作"):
            authors.append({"name": n, "role": "artist" if has_gensaku else "writer_artist"})
        elif r in CREDIT:
            credits.append({"name": n, "role": CREDIT[r]})
        elif r == "":
            # 役割タグ無し: 単独主creator=writer_artist(単独漫画家)。複数なら暫定writer_artist。
            authors.append({"name": n, "role": "writer_artist"})
        else:
            credits.append({"name": n, "role": "editor"})
    return authors, credits

dist = collections.Counter()
fixed = empty = 0
empties = []
for p in glob.glob(f"{PREV}/*.yml"):
    d = yaml.safe_load(open(p, encoding="utf-8"))
    if not d or d.get("source") != "ndl-discovery-2425":
        continue
    isbns = [re.sub(r"\D", "", str(v.get("isbn13") or "")) for e in (d.get("editions") or []) for v in (e.get("volumes") or [])]
    # 全巻の creators_roled を集約(最も creator 多いものを採用)
    best = ""
    for ib in isbns:
        cr = rl.get(ib, "")
        if len([x for x in cr.split("/") if x]) > len([x for x in best.split("/") if x]):
            best = cr
    authors, credits = parse_authors(best)
    # 既存の name(generator由来) を保持できるよう、authorsが空なら旧authorを温存
    if not authors:
        empty += 1
        empties.append((d["slug"], d.get("title"), best))
        continue   # 著者導出不可=後でfilter。 ページは触らない(旧writer_artistのまま残る=次でdrop)
    d["authors"] = authors
    if credits:
        d["credits"] = credits
    for a in authors:
        dist[a["role"]] += 1
    yaml.safe_dump(d, open(p, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=4096)
    fixed += 1

print(f"role是正: {fixed}ページ / 著者導出不可(要filter) {empty}")
print("role分布:", dict(dist))
print("\n導出不可サンプル(編集/監修のみ等):")
for sl, t, cr in empties[:10]:
    print(f"  {sl[:24]} | {str(t)[:18]} | {cr[:40]}")
