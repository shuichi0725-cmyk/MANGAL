# -*- coding: utf-8 -*-
# requeue(短キャッチ再生成)用ダイジェスト。指定バッチのうち requeue リスト掲載slugだけ出力。
# 現行の短いcatch/synopsisも表示する(何を作り直すのか判るように)。
import json, os, sys, html, re
sys.stdout.reconfigure(encoding='utf-8')
import yaml
try: from yaml import CSafeLoader as L
except Exception: from yaml import SafeLoader as L

ROOT = r'C:\Users\chiba shuichi\code\MANGAL'
CAP = int(os.environ.get('CAPLEN', '300'))
RQ = {l.strip() for l in open(f'{ROOT}/docs/production-diagnostics/catch-short-requeue.txt', encoding='utf-8') if l.strip()}

def prod(slug):
    p = f'{ROOT}/data/manga.v2/{slug}.yml'
    if not os.path.exists(p): return None
    try: d = yaml.load(open(p, encoding='utf-8'), Loader=L) or {}
    except Exception: return {}
    return {'catch': (d.get('catch') or '').strip(),
            'syn': (d.get('synopsis') or '').strip(),
            'genres': d.get('genres') or []}

n_out = 0
for n in sys.argv[1:]:
    d = json.load(open(f'{ROOT}/.cache/enrich-batches/batch-{n}.json', encoding='utf-8'))
    print(f'===== batch-{n} kind={d["kind"]} =====')
    for it in d['items']:
        if it['slug'] not in RQ: continue
        st = prod(it['slug'])
        if st is None: continue
        n_out += 1
        need = [] if st['genres'] else ['genre']
        print(f'--- {it["slug"]} | {it["title"]} | {"/".join(it.get("authors") or [])} | {it.get("n_vols")}巻 '
              f'| 既genre={",".join(st["genres"]) or "-"} | demo={it.get("demographic") or "-"}'
              + (' | 要genre' if need else ''))
        print(f'  [旧catch{len(st["catch"])}字] {st["catch"]}')
        if st['syn']: print(f'  [旧syn{len(st["syn"])}字] {st["syn"]}')
        for c in it.get('captions') or []:
            cap = re.sub(r'\s+', ' ', html.unescape(c.get('caption') or '')).strip()[:CAP]
            print(f'  [v{c.get("vol")}] {cap}')
print(f'### 対象 {n_out}件', file=sys.stderr)
