# -*- coding: utf-8 -*-
"""エンリッチ未了ページの作業リスト生成 (= 巻数/年で絞れる汎用版)。

`_enrich-newest-scan.py`(2巻以上・最新巻降順の固定仕様)を一般化したもの。
data/manga.v2 を全走査し、catch / synopsis が欠けた頁を条件で絞って TSV 出力する。

usage:
  python scripts/_enrich-backlog-scan.py --min-vols 5 --since 2010 --basis first [-o OUT.tsv]

  --min-vols N   巻数(edition横断の distinct 巻番号)が N 以上
  --since YYYY   発売年が YYYY 以上
  --basis        first = 1巻(最古)の発売日 / latest = 最新巻の発売日 / any = どちらかが条件を満たす
  --missing      both(既定=catch/syn両方欠け) / any(どちらか欠け)
出力列: first_date / latest_date / n_vols / slug / title / missing / genres / authors
"""
import argparse, io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data', 'manga.v2')

RE_DATE = re.compile(r"^\s+release_date: '?(\d{4}-\d{2}-\d{2})")
RE_NUM = re.compile(r'^\s+- number: (\d+)')

ap = argparse.ArgumentParser()
ap.add_argument('--min-vols', type=int, default=2)
ap.add_argument('--since', type=int, default=0)
ap.add_argument('--until', type=int, default=0, help='basis の年が YYYY 以下(=それ以前の作品だけ)')
ap.add_argument('--basis', choices=['first', 'latest', 'any'], default='first')
ap.add_argument('--missing', choices=['both', 'any'], default='both')
ap.add_argument('-o', '--out', default=os.path.join(ROOT, '.cache', 'enrich-backlog.tsv'))
a = ap.parse_args()

rows = []
for fn in sorted(os.listdir(SRC)):
    if not fn.endswith('.yml'):
        continue
    txt = io.open(os.path.join(SRC, fn), encoding='utf-8').read()
    has_catch = bool(re.search(r"^catch: (?!''\s*$)\S", txt, re.M))
    has_syn = bool(re.search(r"^synopsis: (?!''\s*$)\S", txt, re.M))
    if a.missing == 'both':
        if has_catch or has_syn:
            continue
    else:
        if has_catch and has_syn:
            continue
    nums, dates, authors, genres = set(), [], [], []
    title = ''
    in_auth = in_gen = False
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
            in_auth, in_gen = True, False
        elif line.startswith('genres:'):
            in_gen, in_auth = True, False
        elif in_auth:
            if line.startswith('- name: '):
                authors.append(line[8:].strip())
            elif line and not line.startswith(' ') and not line.startswith('-'):
                in_auth = False
        elif in_gen:
            if line.startswith('- '):
                genres.append(line[2:].strip())
            elif line and not line.startswith(' '):
                in_gen = False
    if len(nums) < a.min_vols or not dates:
        continue
    first, latest = min(dates), max(dates)
    yf, yl = int(first[:4]), int(latest[:4])
    if a.since:
        ok = {'first': yf >= a.since, 'latest': yl >= a.since, 'any': (yf >= a.since or yl >= a.since)}[a.basis]
        if not ok:
            continue
    if a.until:
        ok = {'first': yf <= a.until, 'latest': yl <= a.until, 'any': (yf <= a.until and yl <= a.until)}[a.basis]
        if not ok:
            continue
    missing = 'both' if (not has_catch and not has_syn) else ('catch' if not has_catch else 'syn')
    rows.append((first, latest, len(nums), fn[:-4], title, missing, ','.join(genres), '/'.join(authors)))

rows.sort(key=lambda r: (-r[2], r[1]), reverse=False)  # 巻数降順 → 同数は最新巻の古い順
with io.open(a.out, 'w', encoding='utf-8', newline='') as f:
    f.write('first_date\tlatest_date\tn_vols\tslug\ttitle\tmissing\tgenres\tauthors\n')
    for r in rows:
        f.write('%s\t%s\t%d\t%s\t%s\t%s\t%s\t%s\n' % r)
sys.stdout.reconfigure(encoding='utf-8')
print('%d rows -> %s' % (len(rows), a.out))
