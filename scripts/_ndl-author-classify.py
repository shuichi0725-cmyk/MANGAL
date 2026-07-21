"""B分析: 回収したNDL典拠IDで新規著者を分類 + 同名異人(homonym)を確定。

入力:
  data/seeds/ndl-author-authority.jsonl   (回収: authority_id→name/yomi/isbns)
  .cache/ndl-authority-known.json          (metadata504 ma:ndla = 既知人物 39,677)
  docs/ndl-new-authors-2024-2025.tsv       (271新規著者)

出力:
  docs/ndl-new-author-classification.tsv : 新規著者毎 = known(既存人物)/new(真の新規)/ambiguous
  docs/ndl-homonym-confirmed.tsv          : 同一name(norm)→複数authority(=同名異人)。既知+回収を統合
"""
import json, re, os, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)

def nm(s):
    return re.sub(r"[\s　,、・]", "", str(s or ""))

known = json.load(open(f"{ROOT}/.cache/ndl-authority-known.json", encoding="utf-8"))  # aid -> name
# name(norm) -> set(aid) を既知から
name_auth = collections.defaultdict(set)
aid_name = {}
aid_yomi = {}
for aid, name in known.items():
    name_auth[nm(name)].add(aid)
    aid_name[aid] = name

# 回収分を統合
rec_aid = {}  # aid -> {name,yomi,n_isbn}
recp = f"{ROOT}/data/seeds/ndl-author-authority.jsonl"
if os.path.exists(recp):
    for line in open(recp, encoding="utf-8"):
        r = json.loads(line)
        aid = r["ndl_authority_id"]
        rec_aid[aid] = r
        name_auth[nm(r["name"])].add(aid)
        aid_name.setdefault(aid, r["name"])
        if r.get("yomi"):
            aid_yomi[aid] = r["yomi"]

# ★ISBN linkage: new著者→discovery ISBN→そのrecordのauthority(名前再マッチ不要で確実)
import re as _re
CRE = _re.compile(
    r'<foaf:Agent\s+rdf:about="https?://id\.ndl\.go\.jp/auth/entity/(\d+)">\s*'
    r'<foaf:name>([^<]+)</foaf:name>(?:\s*<dcndl:transcription>([^<]+)</dcndl:transcription>)?', _re.S)
import json as _json
cache = _json.load(open(f"{ROOT}/.cache/ndl-sru-raw-cache.json", encoding="utf-8"))
isbn_creators = {}  # isbn -> [(nm(name), nm(yomi), aid)]
for isbn, xml in cache.items():
    if "auth/entity" not in xml:
        continue
    cr = []
    for m in CRE.finditer(xml):
        cr.append((nm(m.group(2)), nm(m.group(3) or ""), m.group(1)))
    if cr:
        isbn_creators[isbn] = cr
# new著者名(norm) -> discovery ISBNs
author_isbns = collections.defaultdict(set)
for fn in (f"{ROOT}/data/seeds/ndl-discovery-2024.tsv", f"{ROOT}/data/seeds/ndl-discovery-2025.tsv"):
    if not os.path.exists(fn):
        continue
    rows = open(fn, encoding="utf-8").read().splitlines()
    h = rows[0].split("\t"); ci = h.index("creators"); ii = h.index("isbn13")
    for l in rows[1:]:
        c = l.split("\t")
        if len(c) <= ci:
            continue
        for cr in c[ci].split("/"):
            if cr.strip():
                author_isbns[nm(cr)].add(c[ii])

def resolve_by_isbn(author_norm):
    """new著者のISBN群のrecordから、name or yomi が一致する authority を返す。"""
    aids = set()
    for isbn in author_isbns.get(author_norm, ()):
        for cname, cyomi, aid in isbn_creators.get(isbn, ()):
            if author_norm == cname or author_norm == cyomi:
                aids.add(aid)
    return aids

# 新規著者分類
new_rows = open(f"{ROOT}/docs/ndl-new-authors-2024-2025.tsv", encoding="utf-8").read().splitlines()[1:]
cls = collections.Counter()
out = []
for l in new_rows:
    if not l.strip():
        continue
    c = l.split("\t")
    name = c[0]
    # ISBN linkage優先(確実) + name一致(補助)
    aids = resolve_by_isbn(nm(name)) | name_auth.get(nm(name), set())
    rec_aids = [a for a in aids if a in rec_aid]
    known_aids = [a for a in aids if a in known]
    if not aids:
        kind = "unresolved"  # 典拠未回収(throttleで未取得 or NDL未登録)
    elif len(aids) > 1:
        kind = "homonym"     # 同名で複数人物
    elif known_aids:
        kind = "known"       # 既存MADB人物と同一典拠 = 真の新規でない(別作/共著の表記)
    else:
        kind = "new"         # 回収のみ・504未登録 = 凍結後の真の新規人物
    cls[kind] += 1
    out.append((name, kind, ",".join(sorted(aids)), c[1] if len(c) > 1 else ""))

with open(f"{ROOT}/docs/ndl-new-author-classification.tsv", "w", encoding="utf-8") as f:
    f.write("author\tclass\tauthority_ids\tndl_works\n")
    for name, kind, aids, w in out:
        f.write(f"{name}\t{kind}\t{aids}\t{w}\n")

# homonym確定(既知∪回収で name→複数authority)
homon = {n: a for n, a in name_auth.items() if len(a) > 1}
with open(f"{ROOT}/docs/ndl-homonym-confirmed.tsv", "w", encoding="utf-8") as f:
    f.write("name\tn_persons\tauthority_ids\tnames_yomi\n")
    for n0, aids in sorted(homon.items(), key=lambda x: -len(x[1])):
        det = " || ".join(f"{a}:{aid_name.get(a,'')}({aid_yomi.get(a,'')})" for a in sorted(aids))
        f.write(f"{n0}\t{len(aids)}\t{','.join(sorted(aids))}\t{det}\n")

print("新規著者分類:", dict(cls))
print(f"既知typ典拠(504): {len(known):,} / 回収typ: {len(rec_aid)}")
print(f"同名異人(既知∪回収, name→複数authority): {len(homon):,}")
print("出力: docs/ndl-new-author-classification.tsv / docs/ndl-homonym-confirmed.tsv")
