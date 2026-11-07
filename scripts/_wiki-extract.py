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
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _wiki_local as WL   # ★2026-11-07: 手元の Wikipedia ダンプ(C:)から(API は使わない)
for t in args:
    g = WL.get(t)
    txt = WL.to_text(g[1]) if g else ''
    print('\n### %s -> %s %s (%d字・ダンプ %s)' % (t, g[0] if g else None, '' if g else 'MISSING', len(txt), WL.dump_date()))
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
