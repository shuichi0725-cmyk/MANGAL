"""slug衝突22の裁定適用(docs/collision-22-resolution.tsv)。suffix/subtitle=candidate改名 / swap・edge=両者改名 / dedup=incumbent drop+candidate改名。
durable=slug-overrides.yml(+dedupはpage-dedup.yml drop) / redirect=slug-aliases.yml+_redirects / 可逆=backup+changelog。"""
import csv, os, yaml, shutil, json, sys
ROOT = "C:/Users/shuic/code/MANGAL"; NOW = "2026-06-26"
v2dir, pvdir = ROOT + "/data/manga.v2", ROOT + "/.preview-data/manga"
bakdir = ROOT + "/.cache/collision22-bak"; os.makedirs(bakdir, exist_ok=True)
so = yaml.safe_load(open(ROOT+"/data/seeds/slug-overrides.yml", encoding="utf-8")) or {"overrides": {}}
pd = yaml.safe_load(open(ROOT+"/data/seeds/page-dedup.yml", encoding="utf-8")) or {"dedup": []}
aliases = []; clog = open(ROOT+"/.cache/slug-fix-834-changelog.jsonl", "a", encoding="utf-8")
def rename(old, new, reason):
    moved = False
    for d in [v2dir, pvdir]:
        of, nf = d+"/"+old+".yml", d+"/"+new+".yml"
        if os.path.exists(of) and not os.path.exists(nf):
            dd = yaml.safe_load(open(of, encoding="utf-8")); dd["slug"] = new
            yaml.safe_dump(dd, open(nf, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
            os.remove(of); moved = True
    so["overrides"][old] = {"at": NOW, "reason": reason, "slug": new}
    aliases.append((old, new)); clog.write(json.dumps({"old": old, "new": new, "at": NOW, "via": "collision22"}, ensure_ascii=False)+"\n")
    return moved
def drop_page(slug):
    for d in [v2dir, pvdir]:
        f = d+"/"+slug+".yml"
        if os.path.exists(f): shutil.copy(f, bakdir+"/"+os.path.basename(f)+("."+("pv" if d==pvdir else "v2"))); os.remove(f)
cnt = {}
for r in csv.DictReader(open(ROOT+"/docs/collision-22-resolution.tsv", encoding="utf-8"), delimiter="\t"):
    old, inc, action = r["old_slug"], r["incumbent_slug"], r["action"]
    pc, pi = r["proposed_candidate_slug"].strip(), r["proposed_incumbent_slug"].strip()
    cnt[action] = cnt.get(action, 0) + 1
    if action in ("suffix", "subtitle"):
        rename(old, pc, f"slug衝突{action}(同名異作/サブ): {r['reason'][:36]}")
    elif action == "swap":
        rename(inc, pi, "slug衝突swap:incumbent退避(candidateが主版)"); rename(old, pc, "slug衝突swap:candidate無印化")
    elif action == "edge":
        rename(inc, pi, "slug衝突edge:incumbent誤slug退避"); rename(old, inc, "slug衝突edge:candidateが正slug")
    elif action == "dedup":
        drop_page(inc); rename(old, inc, "重複dedup:incumbent⊂candidate(完全版採用)")
        pd["dedup"].append({"drop": inc, "canonical": inc, "title": r["candidate_title"], "isbns": "subset(collision22)"})
yaml.safe_dump(so, open(ROOT+"/data/seeds/slug-overrides.yml", "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
yaml.safe_dump(pd, open(ROOT+"/data/seeds/page-dedup.yml", "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
with open(ROOT+"/data/slug-aliases.yml", "a", encoding="utf-8") as f:
    for o, n in aliases: f.write(f"{o}: {n}\n")
with open(ROOT+"/public/_redirects", "a", encoding="utf-8") as f:
    for o, n in aliases: f.write(f"/{o} /{n} 301\n")
clog.close()
print(f"適用: {cnt} / alias{len(aliases)}本追記", flush=True)
