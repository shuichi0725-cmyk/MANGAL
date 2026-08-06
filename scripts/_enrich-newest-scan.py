# -*- coding: utf-8 -*-
"""「新しい順」エンリッチ柱の作業リスト生成 (= skill enrich-catch-synopsis 優先①の実務版)。

data/manga.v2 を全走査し、catch / synopsis が空で **2巻以上** の頁を
「最新巻の発売日 降順」で並べた TSV を出す。
(2026-08-03 ユーザ裁定 = 1巻頁はキャッチ/詳細を書かないので対象外)

usage: python scripts/_enrich-newest-scan.py [出力先TSV]
出力列: latest_date / n_vols / slug / title / missing(catch|syn|both) / authors
"""
import io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data', 'manga.v2')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '.cache', 'enrich-newest-backlog.tsv')

RE_DATE = re.compile(r"^\s+release_date: '?(\d{4}-\d{2}-\d{2})")
RE_NUM = re.compile(r'^\s+- number: (\d+)')
RE_TITLE = re.compile(r'^title: (.*)$')
RE_NAME = re.compile(r'^- name: (.*)$')

rows = []
for fn in sorted(os.listdir(SRC)):
    if not fn.endswith('.yml'):
        continue
    txt = io.open(os.path.join(SRC, fn), encoding='utf-8').read()
    # catch / synopsis の充填判定 (= '' や空は欠け)
    has_catch = bool(re.search(r"^catch: (?!''\s*$)\S", txt, re.M))
    has_syn = bool(re.search(r"^synopsis: (?!''\s*$)\S", txt, re.M))
    if has_catch and has_syn:
        continue
    nums = set()
    dates = []
    in_auth = False
    authors = []
    title = ''
    for line in txt.split('\n'):
        m = RE_NUM.match(line)
        if m:
            nums.add(int(m.group(1)))
            continue
        m = RE_DATE.match(line)
        if m:
            dates.append(m.group(1))
            continue
        if line.startswith('title: '):
            title = line[7:].strip()
        elif line.startswith('authors:'):
            in_auth = True
        elif in_auth:
            if line.startswith('- name: '):
                authors.append(line[8:].strip())
            elif line and not line.startswith(' ') and not line.startswith('-'):
                in_auth = False
    if len(nums) < 2:
        continue
    missing = 'both' if (not has_catch and not has_syn) else ('catch' if not has_catch else 'syn')
    rows.append((max(dates) if dates else '', len(nums), fn[:-4], title, missing, '/'.join(authors)))

rows.sort(key=lambda r: r[0], reverse=True)
with io.open(OUT, 'w', encoding='utf-8', newline='') as f:
    f.write('latest_date\tn_vols\tslug\ttitle\tmissing\tauthors\n')
    for r in rows:
        f.write('%s\t%d\t%s\t%s\t%s\t%s\n' % r)
sys.stdout.reconfigure(encoding='utf-8')
print('%d rows -> %s' % (len(rows), OUT))
