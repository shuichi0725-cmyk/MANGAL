"""種3 全件に 既存 promote フィルタを 適用した 棚卸し (= 不要物 選定の 現状把握)。

種3 を 削らない (= 月次蒸留 protocol で 種3 不変)。 あくまで
「全種3 を 本番化したら 何が drop / keep されるか」 の 可視化。

分類:
  DROP_TITLE       = title が DROP_TITLE_PREFIX/CONTAINS にヒット (= 画集/ガイド/アニメ版 等)
  NO_KEEP_EDITION  = 全 edition が filter 落ち (= フィルムコミック/コンビニ/novel のみ等)
  NO_EDITION_DATA  = 種2 に edition/volume が無い (= データ欠)
  KEEP             = 本番候補 (= keep edition が 1つ以上)

DROP の どの pattern / imprint で 落ちたか も 集計。
"""
import sys, re, sqlite3, yaml, importlib.util
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict, Counter

# promote script の フィルタ定数/関数 を 流用
spec = importlib.util.spec_from_file_location('promote', 'scripts/_promote-bulk-v2.py')
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

def main():
    print('loading 種2 editions...', flush=True)
    db = sqlite3.connect('.cache/db-v2.sqlite')
    db.text_factory = lambda b: b.decode('utf-8', errors='replace')
    # series_key → [(type, imprint, has_volumes)]
    sk_eds = defaultdict(list)
    ed_vol_count = {}
    for eid, n in db.execute('SELECT edition_id, COUNT(*) FROM volumes GROUP BY edition_id'):
        ed_vol_count[eid] = n
    for sk, eid, typ, imp in db.execute('''
        SELECT s.series_key, e.id, e.type, e.imprint
        FROM series s JOIN editions e ON e.series_id = s.id
    '''):
        sk_eds[sk].append((eid, typ, imp or '', ed_vol_count.get(eid, 0)))
    db.close()
    print(f'  種2 series with editions: {len(sk_eds):,}', flush=True)

    print('loading 種3...', flush=True)
    with open('data/seeds/series-supplement-v2.yml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    cnt = Counter()
    drop_title_pat = Counter()
    no_keep_imprint = Counter()
    samples = defaultdict(list)

    for e in data['series']:
        key = e.get('key', '')
        names = [p[5:] for p in key.split('|') if p.startswith('name:')]
        if not names: continue
        title = names[-1]

        # --- title-level filter ---
        hit_prefix = next((p for p in P.DROP_TITLE_PREFIX_PATTERNS if title.startswith(p)), None)
        hit_contains = next((p for p in P.DROP_TITLE_CONTAINS_PATTERNS if p in title), None)
        if hit_prefix or hit_contains:
            cnt['DROP_TITLE'] += 1
            drop_title_pat[hit_prefix or hit_contains] += 1
            if len(samples['DROP_TITLE']) < 25:
                samples['DROP_TITLE'].append((title, hit_prefix or hit_contains))
            continue

        # --- edition-level filter ---
        eds = sk_eds.get(key, [])
        if not eds:
            cnt['NO_EDITION_DATA'] += 1
            if len(samples['NO_EDITION_DATA']) < 15:
                samples['NO_EDITION_DATA'].append((title, ''))
            continue
        keep_eds = []
        for eid, typ, imp, nvol in eds:
            if nvol == 0: continue
            if P.edition_passes_filter({'type': typ, 'imprint': imp}):
                keep_eds.append((typ, imp))
        if not keep_eds:
            cnt['NO_KEEP_EDITION'] += 1
            # 落ちた理由 imprint 集計
            for eid, typ, imp, nvol in eds:
                if nvol == 0: continue
                if typ not in P.KEEP_EDITION_TYPES:
                    no_keep_imprint[f'type={typ}'] += 1
                else:
                    matched = next((pat for pat in P.DROP_IMPRINT_PATTERNS if pat in imp), None)
                    if not matched:
                        il = imp.lower()
                        matched = next((pat for pat in P.DROP_IMPRINT_LOWER_PATTERNS if pat in il), None)
                    no_keep_imprint[matched or f'imprint={imp[:20]}'] += 1
            if len(samples['NO_KEEP_EDITION']) < 25:
                imps = list({imp for _,_,imp,nv in eds if nv})
                samples['NO_KEEP_EDITION'].append((title, '|'.join(imps)[:60]))
            continue
        cnt['KEEP'] += 1

    total = sum(cnt.values())
    print()
    print(f'=== 種3 棚卸し (= 全種3 に promote フィルタ適用、 {total:,} 件) ===')
    for k in ['KEEP','DROP_TITLE','NO_KEEP_EDITION','NO_EDITION_DATA']:
        print(f'  {k:18s}: {cnt[k]:,} ({cnt[k]*100/total:.1f}%)')
    print()
    print('=== DROP_TITLE: ヒット pattern 別 top 25 ===')
    for pat, c in drop_title_pat.most_common(25):
        print(f'  {c:5,}  {pat}')
    print()
    print('=== NO_KEEP_EDITION: 落ちた理由 (= imprint/type) top 25 ===')
    for pat, c in no_keep_imprint.most_common(25):
        print(f'  {c:5,}  {pat}')
    print()
    print('=== DROP_TITLE sample ===')
    for t, p in samples['DROP_TITLE'][:20]:
        print(f'  [{p}] {t!r}')
    print()
    print('=== NO_KEEP_EDITION sample (= フィルムコミック/コンビニ等のみ) ===')
    for t, imps in samples['NO_KEEP_EDITION'][:20]:
        print(f'  {t!r}  imprints={imps}')
    print()
    print('=== NO_EDITION_DATA sample (= 種2にvolume無し) ===')
    for t, _ in samples['NO_EDITION_DATA'][:10]:
        print(f'  {t!r}')

if __name__ == '__main__':
    main()
