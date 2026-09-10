# -*- coding: utf-8 -*-
"""本番66k頁のうち、著者表示名が「その本のクレジット」と食い違い、かつ
同一人物の別名(mangaka.alt_names)としてクレジット名に一致するもの＝
_apply_book_credit が効いていれば直っていたはずの頁を数える(読み取り専用)。"""
import io, json, sqlite3, sys, collections
from pathlib import Path
import importlib.util

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.argv = ['x']
spec = importlib.util.spec_from_file_location('pb', 'scripts/_promote-bulk-v2.py')
pb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pb)
pb._load_pub_resolver()
con = sqlite3.connect('.cache/db-v2.sqlite')
alias = pb._mangaka_alias(con)
print('ISBN2CREDIT:', len(pb._ISBN2CREDIT or {}), '/ alias著者:', len(alias))

# slug -> ISBN群 (isbn-page-index の逆引き)
idx = json.load(open('.cache/isbn-page-index.json', encoding='utf-8'))
slug2isbn = collections.defaultdict(list)
for isbn, slugs in idx.items():
    for s in (slugs if isinstance(slugs, list) else [slugs]):
        slug2isbn[s].append(isbn)
print('slug→ISBN:', len(slug2isbn))

li = json.load(open('data/manga-list-index.json', encoding='utf-8'))
F = {n: i for i, n in enumerate(li['f'])}
rows = li['d']
print('頁:', len(rows))

hits = []
for r in rows:
    slug = r[F['slug']]
    auth = r[F['authors']] or []
    names = [str(a).split('\t')[0] for a in auth]
    if not names:
        continue
    # 候補 = 別名を持つ著者を含む頁だけ(それ以外は原理的に化けない)
    if not any(n in alias for n in names):
        continue
    isbns = slug2isbn.get(slug) or []
    if not isbns:
        continue
    fixed = pb._apply_book_credit([{'name': n, 'role': 'writer_artist'} for n in names], isbns, alias)
    after = [a['name'] for a in fixed]
    if after != names:
        hits.append((slug, r[F['title']], names, after))

print()
print('★食い違い頁:', len(hits))
for h in hits[:40]:
    print('  ', h[0], '|', h[1], '|', h[2], '->', h[3])
if len(hits) > 40:
    print('   ... 他', len(hits) - 40, '件')
out = Path('.cache/book-credit-drift.tsv')
with out.open('w', encoding='utf-8') as f:
    f.write('slug\ttitle\tnow\tshould_be\n')
    for s, t, a, b in hits:
        f.write(f"{s}\t{t}\t{'|'.join(a)}\t{'|'.join(b)}\n")
print('→', out)
