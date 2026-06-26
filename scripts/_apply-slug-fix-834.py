"""slug修正834のクリーン適用: フリガナ基点のハイフン区切り是正。
クリーン(old!=new かつ new未使用 かつ new重複なし かつ 上書き衝突なし)のみ rename。 衝突22/重複new/no-op は除外(別途)。
dry-run(既定)/--apply。 durable=slug-overrides.yml、 redirect=slug-aliases.yml+_redirects(★追記モード=数値キーsortエラー回避)、 可逆=changelog。"""
import json, os, yaml, glob, sys, collections
ROOT = "C:/Users/shuic/code/MANGAL"
APPLY = "--apply" in sys.argv
NOW = "2026-06-26"
cand = json.load(open(ROOT + "/data/seeds/slug-fix-candidates-2026.json", encoding="utf-8"))
v2dir, pvdir = ROOT + "/data/manga.v2", ROOT + "/.preview-data/manga"
v2 = set(os.path.basename(f)[:-4] for f in glob.glob(v2dir + "/*.yml"))
clean = {o: n for o, n in cand.items() if o != n and n not in v2}
newcount = collections.Counter(clean.values())
dup_new = {n for n, c in newcount.items() if c > 1}
held_dup = {o: n for o, n in clean.items() if n in dup_new}
clean = {o: n for o, n in clean.items() if n not in dup_new}
overwrite = {o: n for o, n in clean.items() if os.path.exists(v2dir+"/"+n+".yml") or os.path.exists(pvdir+"/"+n+".yml")}
clean = {o: n for o, n in clean.items() if o not in overwrite}
print(f"候補834 → クリーン適用={len(clean)} / 重複new除外={len(held_dup)} / 上書き衝突除外={len(overwrite)}", flush=True)
if not APPLY:
    print("[dry-run] --apply で実行", flush=True); sys.exit()
sop = ROOT + "/data/seeds/slug-overrides.yml"
so = yaml.safe_load(open(sop, encoding="utf-8")) or {"overrides": {}}
clog = open(ROOT + "/.cache/slug-fix-834-changelog.jsonl", "a", encoding="utf-8")
renamed = 0
for old, new in clean.items():
    for d in [v2dir, pvdir]:
        of, nf = d + "/" + old + ".yml", d + "/" + new + ".yml"
        if os.path.exists(of) and not os.path.exists(nf):
            dd = yaml.safe_load(open(of, encoding="utf-8")); dd["slug"] = new
            yaml.safe_dump(dd, open(nf, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
            os.remove(of)
    so["overrides"][old] = {"at": NOW, "reason": "フリガナ基点でハイフン区切り是正(slug-fix-834)", "slug": new}
    clog.write(json.dumps({"old": old, "new": new, "at": NOW}, ensure_ascii=False) + "\n")
    renamed += 1
yaml.safe_dump(so, open(sop, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
# ★slug-aliases/_redirects = 追記モード(load+rewriteは数値キーでsortエラー+truncate事故)
with open(ROOT + "/data/slug-aliases.yml", "a", encoding="utf-8") as f:
    for old, new in clean.items(): f.write(f"{old}: {new}\n")
with open(ROOT + "/public/_redirects", "a", encoding="utf-8") as f:
    for old, new in clean.items(): f.write(f"/{old} /{new} 301\n")
clog.close()
print(f"適用完了: rename={renamed} / slug-overrides+aliases+_redirects+changelog 更新", flush=True)
