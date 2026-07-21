"""manga.dryrun(補正後) vs manga.v2(補正前) の著者差分を検証。
- 著者が変わったファイル数 / ゼロ著者化(regression) / ドラえもん実例
"""
import glob, os, sys, yaml
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
V2 = ROOT + "/data/manga.v2"
DRY = ROOT + "/data/manga.dryrun"

def authors_of(path):
    try:
        d = yaml.safe_load(open(path, encoding="utf-8")) or {}
    except Exception:
        return None
    a = [x.get("name") for x in (d.get("authors") or [])]
    o = [x.get("name") if isinstance(x, dict) else x for x in (d.get("original_authors") or [])]
    return (a, o)

dry_files = {os.path.basename(p) for p in glob.glob(DRY + "/*.yml")}
v2_files = {os.path.basename(p) for p in glob.glob(V2 + "/*.yml")}
print("v2:%d  dryrun:%d  (差=%d)" % (len(v2_files), len(dry_files), len(dry_files) ^ len(v2_files) if False else len(dry_files) - len(v2_files)))
print("dryrunのみ:%d  v2のみ:%d" % (len(dry_files - v2_files), len(v2_files - dry_files)))

changed = 0
zeroed = []      # 補正後に著者0 = regression
changed_rows = []
import csv as _csv
common = dry_files & v2_files
for fn in common:
    av2 = authors_of(V2 + "/" + fn)
    ad = authors_of(DRY + "/" + fn)
    if av2 is None or ad is None or av2 == ad:
        continue
    changed += 1
    changed_rows.append([fn, " | ".join(av2[0]), " | ".join(ad[0])])
    if ad[0] == [] or ad[0] == ["(unknown)"]:
        if av2[0] and av2[0] != ["(unknown)"]:
            zeroed.append((fn, av2[0]))
with open(ROOT + "/.cache/overlay-changed-authors.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = _csv.writer(f)
    w.writerow(["file", "v2(前)", "dryrun(後)"])
    w.writerows(sorted(changed_rows))
print("著者が変わったファイル:%d / ★ゼロ著者化(regression):%d" % (changed, len(zeroed)))
print("→ .cache/overlay-changed-authors.csv")
for fn, before in zeroed[:20]:
    print("  ZERO:", fn, "←was", before[:4])

print("\n=== ドラえもん実例 ===")
for fn in ["doraemon.yml", "doraemon-2.yml", "doraemon-komikku-kuizu.yml",
           "hajimete-no-doraemon.yml", "totteoki-doraemon.yml", "esper-mami.yml"]:
    if fn in common:
        b = authors_of(V2 + "/" + fn)
        a = authors_of(DRY + "/" + fn)
        if b != a:
            print(f"[{fn}]")
            print(f"   v2 : {b[0][:8]}")
            print(f"   後 : {a[0][:8]}")
