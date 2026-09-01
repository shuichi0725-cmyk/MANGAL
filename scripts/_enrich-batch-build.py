# -*- coding: utf-8 -*-
"""外部エンリッチ生成物を組み立てて字数リントする (= skill external-enrich の Step4 前段)。

入力(いずれも .cache/ 直下、キー=SRC stem):
  s<N>.json = {stem: 材料テキスト}   ← Wikipedia/魚から取った一次情報(丸写し検査の突合先)
  c<N>.json = {stem: キャッチ}
  y<N>.json = {stem: 詳細}          ← 任意(キャッチのみの頁は入れない)
出力: stdout に _enrich-web-batch.py へ渡す JSON。stderr に字数リント(★印が違反)。

usage: python scripts/_enrich-batch-build.py 9436 > .cache/in9436.json
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
N = sys.argv[1]
S = json.load(open(".cache/s%s.json" % N, encoding="utf-8"))
C = json.load(open(".cache/c%s.json" % N, encoding="utf-8"))
try:
    Y = json.load(open(".cache/y%s.json" % N, encoding="utf-8"))
except Exception:
    Y = {}

out = {}
for k in S:
    v = {"src": S[k], "source": "wikipedia/出版社・電子書店 via TinyFish"}
    if k in C:
        v["catch"] = C[k]
    if k in Y:
        v["synopsis"] = Y[k]
    out[k] = v

ng = 0
for k, v in out.items():
    c = len(v.get("catch") or "")
    y = len(v.get("synopsis") or "")
    f = ""
    if c and not (48 <= c <= 74):
        f += " ★catch"
        ng += 1
    if y and not (78 <= y <= 114):
        f += " ★syn"
        ng += 1
    print("%-52s c%d y%d%s" % (k, c, y, f), file=sys.stderr)
print("NG=%d" % ng, file=sys.stderr)
print(json.dumps(out, ensure_ascii=False))
