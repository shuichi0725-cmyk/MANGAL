# -*- coding: utf-8 -*-
# 和名タグ監査(2026-08-11): 対訳表にもwamei-tags.ymlにも載らず非表示に落ちているタグを集計。
# 月次で走らせ、新規に出現数>=3へ育った語を人が確認して data/seeds/wamei-tags.yml の allow へ追記する。
# (自動追記はしない=ゴミタグ流入防止。閾値未満の長尾は報告のみ)
import glob, io, os, sys
sys.stdout.reconfigure(encoding='utf-8')
import yaml
try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

t = yaml.load(open(f'{ROOT}/data/seeds/tag-i18n.yml', encoding='utf-8'), Loader=L)
translated = set((t.get('tags', t)).keys())
w = yaml.load(open(f'{ROOT}/data/seeds/wamei-tags.yml', encoding='utf-8'), Loader=L) or {}
known = set(w.get('allow') or []) | set(w.get('alias') or {}) | set(w.get('exclude') or [])
# ビルダーのfallback辞書(_build-list-index.py ANILIST_TAG_JA)と同じ英語タグは対訳側でカバー済み扱い
FB = {"Surreal Comedy", "Slapstick", "Heterosexual", "Female Harem", "Male Harem", "Youkai", "Aliens",
      "Shounen", "Shoujo", "Seinen", "Josei", "Kodomo", "School", "School Club", "Magic", "Military",
      "Police", "Yakuza", "Tsundere", "Yandere", "Kuudere", "Dandere", "Male Protagonist",
      "Female Protagonist", "Anti-Hero", "Love Triangle", "Animals", "Shapeshifting", "Episodic",
      "Nudity", "Isekai", "Reincarnation", "Time Travel", "Vampire", "Zombie", "Ghost", "Demon",
      "Cyborg", "Robot", "Samurai", "Ninja"}
NOISE = {"Heterosexual", "Male Protagonist", "Female Protagonist",
         "Primarily Adult Cast", "Primarily Child Cast", "Primarily Teen Cast"}

from collections import Counter
miss = Counter()
for p in glob.iglob(f'{ROOT}/data/manga.v2/*.yml'):
    d = yaml.load(open(p, encoding='utf-8'), Loader=L)
    if not d:
        continue
    for tg in (d.get('tags') or []):
        name = str(tg.get('name') or '')
        cat = tg.get('category') or ''
        if not name or cat == 'Demographic' or cat.startswith('Theme-Game-Sport') or name in NOISE:
            continue
        if name in translated or name in FB or name in known:
            continue
        miss[name] += 1

hot = [(k, v) for k, v in miss.most_common() if v >= 3]
print(f'非表示タグ {len(miss)}種(総付与{sum(miss.values())})/ うち閾値(>=3)超え={len(hot)}種 ← allowへの追記候補')
for k, v in hot:
    print(f'  {v:5d} {k}')
out = f'{ROOT}/docs/production-diagnostics/wamei-tags-pending.tsv'
with io.open(out, 'w', encoding='utf-8') as f:
    for k, v in miss.most_common():
        f.write(f'{v}\t{k}\n')
print(f'全量 → {out}')
