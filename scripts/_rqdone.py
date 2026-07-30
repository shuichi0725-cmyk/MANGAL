# -*- coding: utf-8 -*-
"""短キャッチ requeue の消し込み。

    python scripts/_rqdone.py 0085 0086

指定バッチの生成物 data/enrich-out-2026-07/batch-NNNN.json に載っている slug を
docs/production-diagnostics/catch-short-requeue.txt から除去し、残件数を表示する。
(changelog への記録は _apply-enrich-batch.py が済ませている)
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'enrich-out-2026-07')
RQ = os.path.join(ROOT, 'docs', 'production-diagnostics', 'catch-short-requeue.txt')


def main(batches):
    done = set()
    for b in batches:
        p = os.path.join(OUT, 'batch-%s.json' % b)
        done |= set(json.load(io.open(p, encoding='utf-8')).keys())

    lines = [l.strip() for l in io.open(RQ, encoding='utf-8') if l.strip()]
    kept = [l for l in lines if l not in done]
    removed = len(lines) - len(kept)
    io.open(RQ, 'w', encoding='utf-8', newline='\n').write('\n'.join(kept) + '\n')
    print('removed=%d (batch slugs=%d) / remaining=%d' % (removed, len(done), len(kept)))
    print(','.join(sorted(done)))


if __name__ == '__main__':
    main(sys.argv[1:])
