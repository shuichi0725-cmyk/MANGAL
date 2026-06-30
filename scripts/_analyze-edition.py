"""奇子型per-case用 版アナライザ。 引数=slug。 現データの全巻(num/label/isbn/date/cover/実題)
+ NDL取得データの版グループ(出版社×年×巻)を一望して、 版分離(edition-override)判断の材料を出す。"""
import json, re, os, sys, yaml
ROOT = "C:/Users/shuic/code/MANGAL"
sys.stdout.reconfigure(encoding="utf-8")
slug = sys.argv[1]
tmap = json.load(open(f"{ROOT}/.cache/isbn-title-map.json", encoding="utf-8"))
# NDL records for this slug
ndl = None
for l in open(f"{ROOT}/.cache/volgap-ndl.jsonl", encoding="utf-8"):
    d = json.loads(l)
    if d["slug"] == slug:
        ndl = d; break

d = yaml.safe_load(open(f"{ROOT}/data/manga.v2/{slug}.yml", encoding="utf-8"))
print(f"■ {d['title']} ({slug}) 著{[a['name'] for a in d.get('authors',[])]} pub={d.get('publisher')}")
print("=== 現データ(本番) ===")
for e in d.get("editions", []):
    print(f"  [type={e.get('type')} label={e.get('label')} pub={e.get('publisher')}]")
    for v in sorted(e.get("volumes", []), key=lambda x: x.get("number") or 0):
        ib = re.sub(r"\D", "", str(v.get("isbn13") or ""))
        rt = tmap.get(ib, "")
        print(f"    vol{v.get('number'):>3} label[{v.get('volume_label') or ''}] {ib or '無':14} {str(v.get('release_date') or ''):10} cov[{'有' if v.get('cover_url') else '無'}] {rt[:26]}")

print("=== NDL版グループ(出版社×年) ===")
if ndl:
    groups = {}
    for r in ndl["records"]:
        key = (r.get("publisher", "")[:16], (r.get("date", "") or "")[:4])
        groups.setdefault(key, []).append((r.get("volume", ""), r.get("isbn") or "", (r.get("date") or "")[:7]))
    for (pub, yr), vs in sorted(groups.items(), key=lambda x: (x[0][1], x[0][0])):
        vols = sorted(set(v[0] for v in vs if v[0]))
        isbns = [v for v in vs if v[1]]
        print(f"  {yr:5} {pub:16} 巻{vols[:12]} ({len(vs)}件 ISBN{len(isbns)})")
else:
    print("  (NDLデータ無)")
