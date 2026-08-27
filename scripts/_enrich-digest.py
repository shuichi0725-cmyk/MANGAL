# -*- coding: utf-8 -*-
"""材料バッチを人間可読ダイジェストへ(UTF-8ファイル出力=Windowsコンソール文字化け回避)。
  python scripts/_enrich-digest.py 9301 [--caplen 260]
"""
import io, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
n = sys.argv[1]
caplen = int(os.environ.get("CAPLEN", "260"))
d = json.load(io.open(os.path.join(ROOT, ".cache", "enrich-batches", f"batch-{n}.json"), encoding="utf-8"))
out = io.open(os.path.join(ROOT, ".cache", "enrich-batches", f"digest-{n}.txt"), "w", encoding="utf-8")
for i, e in enumerate(d["items"], 1):
    caps = []
    for c in (e.get("captions") or [])[:3]:
        t = c.get("caption") if isinstance(c, dict) else c
        if isinstance(t, dict): t = json.dumps(t, ensure_ascii=False)
        caps.append(f"v{c.get('vol') if isinstance(c, dict) else '?'}: " + " ".join(str(t).split())[:caplen])
    out.write(f"[{i}] {e['slug']} | {e['title']} | {'・'.join((a.get('name') if isinstance(a, dict) else str(a)) for a in e['authors'][:3])} | {e['n_vols']}巻 | g={e['genres_now']} | dem={e['demographic']} | {e['src']}\n")
    for c in caps:
        out.write("    " + c + "\n")
out.close()
print(f"digest-{n}.txt written ({len(d['items'])} items)")
