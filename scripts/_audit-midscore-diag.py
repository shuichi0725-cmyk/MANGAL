"""S100/S130/S150 (= 中スコア帯) が なぜ S180 に届かないか 診断。

各 verdict で 欠けた signal を 定量化:
  - year 欠落 (種3 or 種a で 発売年 不明)
  - vol 欠落
  - author 欠落 (種2 作者 紐付け なし or 種a staff なし)
  - channel 数 (1 のみ = 加点なし)
  - en 両方あり / en 一致 (= 格上げ用 裏取り signal の 当たり率)
  - genre 一致 可能性

格上げに使える signal の 当たり率 を 出す。
"""
import sys, csv, re, yaml
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict, Counter

TSV = '.cache/match-v8-all.tsv'

def en_norm_loose(s):
    if not s: return ''
    s = s.lower().replace('&','and')
    s = re.sub(r"['’‘]", '', s)
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', '', s)
    return s

# 種3 の genre / synopsis を key で引けるよう load (= 格上げ signal 候補)
print('loading 種3 genre/synopsis...', flush=True)
s3_genre = {}
with open('data/seeds/series-supplement-v2.yml','r',encoding='utf-8') as f:
    data = yaml.safe_load(f)
for e in data['series']:
    k = e.get('key','')
    g = e.get('genres') or []
    if g: s3_genre[k] = set(x.lower() for x in g)

print('analyzing TSV...', flush=True)
csv.field_size_limit(10**7)
diag = {v: defaultdict(int) for v in ['S100','S130','S150','S180']}
reason_tokens = {v: Counter() for v in ['S100','S130','S150']}
total = {v: 0 for v in ['S100','S130','S150','S180']}

with open(TSV, 'r', encoding='utf-8') as f:
    r = csv.reader(f, delimiter='\t')
    header = next(r)
    for row in r:
        if len(row) < 19:
            row = row + [''] * (19 - len(row))
        v = row[0]
        if v not in total: continue
        total[v] += 1
        score, channels, reason = row[1], row[2], row[3]
        s3_year, s3_vols, s3_auth, s3_en = row[8], row[9], row[10], row[11]
        a_en, a_year, a_vols, a_auth = row[14], row[16], row[17], row[18]
        s3_key = row[5]
        d = diag[v]
        # signal 欠落
        if not s3_year: d['s3_year_missing'] += 1
        if not a_year: d['a_year_missing'] += 1
        if not s3_vols: d['s3_vols_missing'] += 1
        if not a_vols: d['a_vols_missing'] += 1
        if not s3_auth: d['s3_author_missing'] += 1
        if not a_auth: d['a_author_missing'] += 1
        if s3_auth and a_auth: d['both_author'] += 1
        nch = len(channels.split('+')) if channels else 0
        d[f'ch{nch}'] += 1
        # 格上げ用 裏取り signal
        if a_en and s3_en:
            d['en_both'] += 1
            if en_norm_loose(a_en) == en_norm_loose(s3_en):
                d['en_loose_match'] += 1
        # genre (種3 と 種a の genre 一致は 種a genre が英語なので 直接比較不可、 種3 genre 有無のみ)
        if s3_key in s3_genre: d['s3_has_genre'] += 1
        if v in reason_tokens:
            for tok in reason.split(','):
                tok = re.sub(r'=\d+', '', tok)
                reason_tokens[v][tok] += 1

for v in ['S100','S130','S150']:
    t = total[v] or 1
    d = diag[v]
    print()
    print(f'=== {v} ({total[v]:,} 件) なぜ S180 に届かないか ===')
    print(f'  [signal 欠落]')
    print(f'    種3 year 不明     : {d["s3_year_missing"]:,} ({d["s3_year_missing"]*100/t:.0f}%)')
    print(f'    種a year 不明     : {d["a_year_missing"]:,} ({d["a_year_missing"]*100/t:.0f}%)')
    print(f'    種3 vols 不明     : {d["s3_vols_missing"]:,} ({d["s3_vols_missing"]*100/t:.0f}%)')
    print(f'    種a vols 不明     : {d["a_vols_missing"]:,} ({d["a_vols_missing"]*100/t:.0f}%)')
    print(f'    種3 author 不明   : {d["s3_author_missing"]:,} ({d["s3_author_missing"]*100/t:.0f}%)')
    print(f'    種a author 不明   : {d["a_author_missing"]:,} ({d["a_author_missing"]*100/t:.0f}%)')
    print(f'    両方 author あり  : {d["both_author"]:,} ({d["both_author"]*100/t:.0f}%)')
    print(f'  [channel 数]')
    for n in range(5):
        if d.get(f'ch{n}'): print(f'    {n} ch: {d[f"ch{n}"]:,} ({d[f"ch{n}"]*100/t:.0f}%)')
    print(f'  [★ 格上げ裏取り signal の 当たり率]')
    print(f'    en 両方あり       : {d["en_both"]:,} ({d["en_both"]*100/t:.0f}%)')
    print(f'    └ en 軽微一致     : {d["en_loose_match"]:,} ({d["en_loose_match"]*100/t:.0f}%)  ← これは ほぼ確実に正しいマッチ')
    print(f'    種3 genre あり    : {d["s3_has_genre"]:,} ({d["s3_has_genre"]*100/t:.0f}%)')
    print(f'  [reason token 頻度]')
    for tok, c in reason_tokens[v].most_common(12):
        print(f'    {tok:22s}: {c:,}')
