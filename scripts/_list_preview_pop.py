import yaml, glob, os
rows = []
for f in glob.glob('.preview-data/manga/*.yml'):
    d = yaml.safe_load(open(f, encoding='utf-8'))
    rows.append((d.get('popularity') or 0, d.get('title', ''), d.get('anilist_id'),
                 bool(d.get('synopsis')), os.path.basename(f)))
rows.sort(reverse=True)
for r in rows[:70]:
    print(f"{r[0]:6d} | {r[1]} | aid={r[2]} | syn={int(r[3])} | {r[4]}")
