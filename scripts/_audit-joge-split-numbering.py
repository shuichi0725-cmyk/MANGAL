# -*- coding: utf-8 -*-
"""「上下(上中下)の分冊なのに巻番号が飛んでいて欠番に見える」型の監査 (2026-08-29 新設)。

背景: MADB系統は 上=1 / 中=2 / 下=3 を固定で割り当てるため、**2冊本の上下が [1, 3] になり
  2巻が欠番に見える**。promote には是正器 `_fix_complete_sequence_numbers` が在るが、
  2026-08-17 の一括処理が誤番号のまま edition-canonical へ焼き込み、canonical は
  editions を丸ごと置換するので是正が打ち消されていた(2026-08-29 妄想戦士ヤマモトHDリマスターで
  ユーザ発見。「ぬけではなく全部あるのにぬけになってるパターン」)。
  → canonical 適用側にも是正器を通すよう修正済み。本監査はその番人。

判定: 1つの版の volume_label が 上/中/下/前/後 系**だけ**で構成され、巻番号が 1..N の連番でない。
  ★片側だけ(「下」しか無い等)は**真の取りこぼし**なので残る = ここに出続けるのが正しい。
  月次は「揃っているのに連番でない」新規増加が 0 であることを確認する。

  python scripts/_audit-joge-split-numbering.py
"""
import io, os, glob, sys, json
import yaml
try:
    from yaml import CSafeLoader as L
except Exception:
    from yaml import SafeLoader as L
sys.stdout.reconfigure(encoding='utf-8')

JOGE = {'上', '中', '下', '前', '後', '前編', '後編', '上巻', '中巻', '下巻', '上下'}
rows = []
for p in sorted(glob.glob('data/manga.v2/*.yml')):
    try:
        d = yaml.load(io.open(p, encoding='utf-8'), Loader=L) or {}
    except Exception:
        continue
    stem = os.path.basename(p)[:-4]
    for e in d.get('editions') or []:
        vols = e.get('volumes') or []
        labs = [str(v.get('volume_label') or '').strip() for v in vols]
        if not vols or not all(l in JOGE for l in labs):
            continue
        nums = [v.get('number') for v in vols]
        if sorted(nums) == list(range(1, len(nums) + 1)):
            continue          # すでに 1..N = 正常
        rows.append({'slug': stem, 'title': d.get('title'), 'edition': e.get('label'),
                     'type': e.get('type'), 'pub': e.get('publisher'),
                     'vols': [(v.get('number'), str(v.get('volume_label') or ''), v.get('isbn13'),
                               v.get('release_date')) for v in vols]})
print('上下分冊なのに番号が飛んでいる版:', len(rows), '/', len({r['slug'] for r in rows}), '頁')
json.dump(rows, io.open('.cache/_joge_gap.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for r in rows:
    print('  %-44s %-26s %s' % (r['slug'], (r['edition'] or '')[:26], r['vols']))
