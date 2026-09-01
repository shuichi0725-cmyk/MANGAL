# -*- coding: utf-8 -*-
"""Web/魚材料エンリッチのバッチ書き出し(字数・丸写しを書く前に検算)。

stdin に {slug: {"src": 材料テキスト, "catch": ..., "synopsis": ..(任意).., "genres_add": [..]}} の JSON。
  python scripts/_enrich-web-batch.py <バッチ番号> < in.json
出力: .cache/enrich-batches/batch-N.json(材料) と data/enrich-out-2026-07/batch-N.json(生成物)
違反(catch 48-74 / syn 78-114 / 8gram重なり>=0.4 / 頭20字一致)があれば **書かずに** 一覧表示して exit 1。
"""
import io, json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = sys.argv[1]
D = json.load(sys.stdin)

def ol(a, b, k=8):
    a = re.sub(r'\s', '', a); b = re.sub(r'\s', '', b)
    if len(a) < k or len(b) < k:
        return 0.0
    bs = {b[i:i+k] for i in range(len(b)-k+1)}
    return sum(1 for i in range(len(a)-k+1) if a[i:i+k] in bs) / max(1, len(a)-k+1)

bad = []
for s, v in D.items():
    c = (v.get('catch') or '').strip(); y = (v.get('synopsis') or '').strip(); src = v.get('src') or ''
    if not os.path.exists(os.path.join(ROOT, 'data', 'manga.v2', s + '.yml')):
        bad.append((s, 'NOFILE(SRC stemで指定する)'))
    # ★promote の catch/synopsis join キーは **源頁(data/manga/<stem>.yml)の slug** であって
    #   ファイル名ではない。 両者がズレている頁に stem キーで書くと **無警告で頁に出ない**
    #   (2026-09-01 実踏: tales-of-the-abyss-rei2006 の源頁slugは tales-of-the-abyss-rei)。
    _sp = os.path.join(ROOT, 'data', 'manga', s + '.yml')
    if os.path.exists(_sp):
        _m = re.search(r'^slug: (.*)$', io.open(_sp, encoding='utf-8').read(400), re.M)
        if _m and _m.group(1).strip() != s:
            bad.append((s, 'KEY不一致(源頁slug=%s で書くこと)' % _m.group(1).strip()))
    if c and not (48 <= len(c) <= 74):
        bad.append((s, 'catch%d' % len(c)))
    if y and not (78 <= len(y) <= 114):
        bad.append((s, 'syn%d' % len(y)))
    if c and y and c[:20] == y[:20]:
        bad.append((s, '頭20字一致'))
    for lab, t in (('catch', c), ('syn', y)):
        if t and src and ol(t, src) >= 0.4:
            bad.append((s, '%s丸写し%.2f' % (lab, ol(t, src))))
if bad:
    print('VIOLATIONS', len(bad))
    for x in bad:
        print('  ', x)
    sys.exit(1)
io.open(f'{ROOT}/.cache/enrich-batches/batch-{N}.json', 'w', encoding='utf-8').write(json.dumps(
    {"items": [{"slug": s, "title": s, "source": v.get('source', 'web'),
                "captions": [{"vol": 0, "isbn": "", "caption": v.get('src') or ''}]} for s, v in D.items()]},
    ensure_ascii=False, indent=1))
io.open(f'{ROOT}/data/enrich-out-2026-07/batch-{N}.json', 'w', encoding='utf-8').write(json.dumps(
    {s: {k: v[k] for k in ('catch', 'synopsis', 'genres_add') if v.get(k)} for s, v in D.items()},
    ensure_ascii=False, indent=1))
print('OK %d entries -> batch-%s' % (len(D), N))
