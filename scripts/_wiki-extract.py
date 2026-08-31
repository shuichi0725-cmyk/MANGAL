# -*- coding: utf-8 -*-
"""日本語Wikipediaの記事冒頭+あらすじを取ってくる小道具(エンリッチ材料用)。
usage: python scripts/_wiki-extract.py "題名" ["題名2" ...] [--chars N]
"""
import json, sys, urllib.parse, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
UA = {'User-Agent': 'MANGAL-research/1.0 (shuichi0725@gmail.com)'}
N = 2200
args = [a for i, a in enumerate(sys.argv[1:]) if not a.startswith("--") and sys.argv[i] != "--chars"]
for i, a in enumerate(sys.argv):
    if a == '--chars':
        N = int(sys.argv[i+1])
for t in args:
    q = {'action': 'query', 'prop': 'extracts', 'explaintext': 1, 'format': 'json', 'titles': t, 'redirects': 1}
    r = urllib.request.Request('https://ja.wikipedia.org/w/api.php?' + urllib.parse.urlencode(q), headers=UA)
    d = json.loads(urllib.request.urlopen(r, timeout=30).read())
    p = list(d['query']['pages'].values())[0]
    txt = p.get('extract') or ''
    print('\n### %s -> %s %s (%d字)' % (t, p.get('title'), 'MISSING' if 'missing' in p else '', len(txt)))
    # あらすじ節があればそこを優先して見せる
    key = None
    for k in ('== あらすじ ==', '== ストーリー ==', '== 概要 =='):
        if k in txt:
            key = k; break
    print(txt[:N])
    if key and txt.find(key) > N:
        i = txt.find(key)
        print('--- [%s] ---' % key.strip('= '))
        print(txt[i:i+1400])
