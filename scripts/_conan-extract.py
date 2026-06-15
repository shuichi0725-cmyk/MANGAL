import glob, os, yaml, json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
paths = sorted(set(glob.glob("data/manga.v2/meitantei-conan-*.yml")
                   + glob.glob("data/manga.v2/conan-*.yml")
                   + glob.glob("data/manga.v2/lupin-iii-vs-meitantei-conan*.yml")))
out = []
for p in paths:
    try:
        d = yaml.safe_load(open(p, encoding="utf-8")) or {}
    except Exception:
        continue
    slug = os.path.basename(p)[:-4]
    au = "/".join(a.get("name", "") for a in d.get("authors", []))
    oau = "/".join(a.get("name", "") for a in d.get("original_authors", []))
    isbns = [(v.get("number"), str(v.get("release_date") or ""), str(v.get("isbn13") or ""))
             for ed in d.get("editions", []) for v in ed.get("volumes", [])]
    out.append({"slug": slug, "title": d.get("title"), "au": au, "oau": oau,
                "aid": d.get("anilist_id"), "isbns": isbns})
json.dump(out, open(".cache/conan-slugs.json", "w", encoding="utf-8"), ensure_ascii=False)
print("slug数", len(out))
for o in out:
    print(f'{o["slug"]:<46} | {(o["title"] or "")[:22]:<22} | 巻{len(o["isbns"]):>3} | au={o["au"]} | aid={o["aid"]}')
