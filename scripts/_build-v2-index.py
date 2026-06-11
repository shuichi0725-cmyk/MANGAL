"""manga.v2 全yml を 1つの索引(.cache/v2-index.json)に集約。 以降の分析はこれを読む=高速。 CSafeLoader使用。"""
import glob,json,sys,time
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L
t0=time.time(); idx=[]
for f in glob.glob("data/manga.v2/*.yml"):
    try: d=yaml.load(open(f,encoding="utf-8"),Loader=L)
    except: continue
    if not d: continue
    def aus(key): return [[a.get("name"),a.get("role"),a.get("kana") or ""] for a in (d.get(key) or [])]
    vt=vn=0
    for e in (d.get("editions") or []):
        for v in (e.get("volumes") or []):
            vt+=1
            if not (v.get("isbn13") or v.get("asin")): vn+=1
    idx.append({"slug":d.get("slug"),"title":d.get("title"),"subtitle":d.get("subtitle"),
        "year":d.get("year_started"),"demo":d.get("demographic"),"pub":d.get("publisher"),
        "pubs":d.get("publishers") or [],"mag":d.get("magazine"),"syn":len(d.get("synopsis") or ""),
        "aid":d.get("anilist_id"),"wqid":d.get("work_wikidata_qid"),"genres":d.get("genres") or [],
        "au":aus("authors"),"oau":aus("original_authors"),"vt":vt,"vn":vn})
json.dump(idx,open(".cache/v2-index.json","w",encoding="utf-8"),ensure_ascii=False)
print("索引: %d作品 / %.1f秒 / %.1fMB"%(len(idx),time.time()-t0,__import__("os").path.getsize(".cache/v2-index.json")/1e6))
