"""新刊著者の統合修正(再パース): 源creators_roled(ISBN/題名突合)から①共著者カンマ分割②空role時の末尾役割(ブラケット/スペース)分離③&amp;デコード。
dry-run(既定): 表示。 --apply で .preview-data + data/manga.v2 に適用(backup付)。"""
import yaml, glob, os, csv, re, html, sys, datetime, shutil, unicodedata
ROOT = "C:/Users/shuic/code/MANGAL"
APPLY = "--apply" in sys.argv
def basetitle(t):
    t = unicodedata.normalize("NFKC", str(t or "")); t = re.sub(r"[\s　]+", "", t)
    t = re.sub(r"[.:：].*$", "", t); t = re.sub(r"\(?\d{1,3}\)?$", "", t)
    return t
roledmap = {}; titlemap = {}
for fn in ["data/seeds/ndl-discovery-2024.tsv","data/seeds/ndl-discovery-2025.tsv","data/seeds/ndl-discovery-2026.tsv","data/seeds/distill-author-supplement-2026.tsv"]:
    p = ROOT + "/" + fn
    if not os.path.exists(p): continue
    for r in csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"):
        ib = r.get("isbn13"); rl = r.get("creators_roled", ""); ti = r.get("title", "")
        if ib and rl: roledmap.setdefault(ib, rl)
        if ti and rl: titlemap.setdefault(basetitle(ti), rl)
print(f"源マップ: ISBN {len(roledmap)} / 題名 {len(titlemap)}", flush=True)
ROLEW = r"(ストーリー協力|キャラクターデザイン原案|キャラクター原案|キャラクターデザイン|スーパーヴァイザー|ネーム構成|脚本構成|脚本・構成|原作・監修|監修協力|劇画|原作|原案|作画|漫画|まんが|マンガ|コミック|構成|脚本|監修|企画|ストーリー|協力|著|画|編|訳|案|作)"
ROLE_TAIL = re.compile(r"[\s　]+" + ROLEW + r"$")
BRACKET = re.compile(r"[〔\[【(（]\s*([^〕\]】)）]+?)\s*[〕\]】)）]\s*$")
ORIG_ROLES = {"原作","原案","ストーリー","脚本","原作・監修"}
ART_ROLES = {"漫画","作画","画","著","劇画","作","","コミック","まんが","マンガ","画担当"}
def clean(nm): return re.sub(r",?\s*\d{4}-?$","",html.unescape(str(nm))).strip().strip(",、 　・")
def parse_v2(roled):
    arts, orig, creds = [], [], []
    for c in (roled or "").split("/"):
        c = html.unescape(c.strip()); np, _, role = c.partition(":"); role = role.strip()
        if not role:
            bm = BRACKET.search(np)
            if bm: role = bm.group(1).strip(); np = np[:bm.start()].strip()
        if not role:
            m = ROLE_TAIL.search(np)
            if m: role = m.group(1); np = np[:m.start()].strip()
        for nm in re.split(r"[∥／,、]", np):
            name = clean(nm)
            if not name: continue
            if role in ORIG_ROLES: orig.append(name)
            elif role in ART_ROLES: arts.append(name)
            else: creds.append({"name": name, "role": role})
    return arts, orig, creds
def names(lst): return [a.get("name") for a in (lst or [])]
changed = []; applied = 0; via = {"isbn":0,"title":0}
bakdir = ROOT + "/.cache/authors-bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") if APPLY else None
if bakdir: os.makedirs(bakdir, exist_ok=True)
for f in glob.glob(ROOT + "/.preview-data/manga/*.yml"):
    try: d = yaml.safe_load(open(f, encoding="utf-8"))
    except: continue
    if not d: continue
    isbns = [v.get("isbn13") for e in d.get("editions", []) for v in e.get("volumes", []) if v.get("isbn13")]
    rl = next((roledmap[ib] for ib in isbns if ib in roledmap), None); src="isbn"
    if not rl: rl = titlemap.get(basetitle(d.get("title"))); src="title"
    if not rl: continue
    arts, orig, creds = parse_v2(rl)
    if not arts: continue
    cur_a, cur_o = names(d.get("authors")), names(d.get("original_authors"))
    if cur_a == arts and cur_o == orig: continue
    via[src]+=1
    changed.append((d["slug"], src, cur_a + (["|原"]+cur_o if cur_o else []), arts + (["|原"]+orig if orig else [])))
    if APPLY:
        for tp in [f, ROOT + "/data/manga.v2/" + d["slug"] + ".yml"]:
            if os.path.exists(tp):
                shutil.copy(tp, bakdir + "/" + os.path.basename(tp) + ("." + ("pv" if tp==f else "v2")))
                dd = yaml.safe_load(open(tp, encoding="utf-8"))
                role0 = (dd.get("authors") or [{}])[0].get("role", "artist")
                dd["authors"] = [{"name": n, "role": role0} for n in arts]
                dd["original_authors"] = [{"name": n, "role": "writer"} for n in orig]
                if creds: dd["credits"] = creds
                yaml.safe_dump(dd, open(tp, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
        applied += 1
import csv as _c
with open(ROOT+"/docs/author-reparse-review.tsv","w",encoding="utf-8",newline="") as fp:
    w=_c.writer(fp,delimiter="\t"); w.writerow(["slug","突合","旧","新"])
    for sl,src,o,n in changed: w.writerow([sl,src," / ".join(o)," / ".join(n)])
print(f"\n変化: {len(changed)}作 (ISBN突合{via['isbn']} / 題名突合{via['title']})" + (f" / 適用{applied}" if APPLY else " dry-run") + " → docs/author-reparse-review.tsv", flush=True)
for sl,src,o,n in [c for c in changed if 'flanagan' in c[0] or 'joukyou' in c[0]][:3]:
    print(f"  [{src}] {sl}\n    旧:{o}\n    新:{n}")
