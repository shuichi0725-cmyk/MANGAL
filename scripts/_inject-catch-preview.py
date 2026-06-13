"""試し: data/seeds/catch-ja.json(slug→キャッチ) を .preview-data の該当 yml に注入。
プレビュー専用(本番 promote とは別)。 純粋追加 = 既存 catch は上書きしない。"""
import json, os, yaml

CATCH = json.load(open('data/seeds/catch-ja.json', encoding='utf-8'))
applied = skipped_exists = missing = 0
for slug, copy in CATCH.items():
    p = os.path.join('.preview-data', 'manga', slug + '.yml')
    if not os.path.exists(p):
        missing += 1
        print('  MISSING:', slug)
        continue
    d = yaml.safe_load(open(p, encoding='utf-8'))
    if d.get('catch') == copy:
        skipped_exists += 1
        continue
    d['catch'] = copy  # catch-ja.json を正本として上書き
    with open(p, 'w', encoding='utf-8') as f:
        yaml.safe_dump(d, f, allow_unicode=True, sort_keys=False, width=10000)
    applied += 1
print(f"applied(新規/更新)={applied}, 変更なし={skipped_exists}, missing={missing}")
