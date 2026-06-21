#!/usr/bin/env python3
"""
TRUE_SINGLE 最終分類(READ-ONLY): 種2(各版冊数)+楽天題(collection信号)で
 CLEAN_SINGLE(各版1冊∧collection無∧題一致=番号是正可) / COLLECTION(傑作集/作品集混在=手動flag) / MULTI(真多巻=据置)。
出力 data/seeds/true-single-final.tsv。
"""
import sqlite3, sys, os, re, json, unicodedata
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLL = re.compile(r"(傑作集|傑作選|作品集|選集|短編集|短篇集|名作選|名作集|自選|コレクション|大全集|全集|COLLECTION)", re.I)

def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""
def naz(s): return re.sub(r"[\s　・！!？\?（）\(\)【】「」〔〕〜~,，、。:：;；/／\.．’'\"＆&\-－0-9０-９]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

print("楽天題map読込...", flush=True)
RT = {}
for line in open(os.path.join(ROOT, ".cache", "rakuten-isbn.jsonl"), encoding="utf-8"):
    try: o = json.loads(line)
    except: continue
    it = o.get("item") or {}; ib = to13(o.get("isbn") or it.get("isbn"))
    if ib: RT[ib] = it.get("title", "")
print(f"  {len(RT)}件", flush=True)

c = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
rows = [r.split("\t") for r in open(os.path.join(ROOT, "data", "seeds", "ndl-volnum-classify-A.tsv"), encoding="utf-8").read().splitlines()[1:] if len(r.split("\t")) >= 6]
ts = [r for r in rows if r[4] == "TRUE_SINGLE"]

def analyze(slug, wtitle):
    st = os.path.join(ROOT, "data", "manga", slug + ".yml")
    if not os.path.exists(st): return None
    m = re.search(r"_skey:\s*(.+)", open(st, encoding="utf-8").read())
    if not m: return None
    sids = [r[0] for r in c.execute("SELECT id FROM series WHERE series_key=?", (m.group(1).strip(),)).fetchall()]
    maxed = 0; coll = ""; foreign = []
    wn = naz(wtitle)
    for sid in sids:
        for (eid,) in c.execute("SELECT id FROM editions WHERE series_id=?", (sid,)).fetchall():
            vs = c.execute("SELECT isbn13 FROM volumes WHERE edition_id=?", (eid,)).fetchall()
            maxed = max(maxed, len(vs))
            for (ib,) in vs:
                rt = RT.get(to13(ib), "")
                if rt and COLL.search(rt): coll = rt
                if rt and wn and naz(rt) and wn not in naz(rt) and naz(rt) not in wn:
                    foreign.append(rt[:24])
    return maxed, coll, foreign

out = open(os.path.join(ROOT, "data", "seeds", "true-single-final.tsv"), "w", encoding="utf-8")
out.write("slug\ttitle\tdb_nums\tclass\tcollection_title\tforeign_titles\n")
cnt = {"CLEAN_SINGLE": 0, "COLLECTION": 0, "MULTI": 0, "NO_S2": 0}
for r in ts:
    a = analyze(r[0], r[1])
    if a is None: cls = "NO_S2"; coll = ""; fg = []
    else:
        maxed, coll, fg = a
        if maxed > 1: cls = "MULTI"
        elif coll: cls = "COLLECTION"
        else: cls = "CLEAN_SINGLE"
    cnt[cls] += 1
    out.write(f"{r[0]}\t{r[1]}\t{r[2]}\t{cls}\t{coll[:30]}\t{';'.join(fg[:3])}\n")
out.close()
print(f"\nTRUE_SINGLE {len(ts)}件 最終分類:")
for k, v in cnt.items(): print(f"  {k}: {v}")
print("\n=== COLLECTION(傑作集/作品集=手動flag) ===")
for r in open(os.path.join(ROOT, "data", "seeds", "true-single-final.tsv"), encoding="utf-8").read().splitlines()[1:]:
    cc = r.split("\t")
    if cc[3] == "COLLECTION": print(f"  {cc[1][:20]} | collection題: {cc[4]}")
