"""KEEP 判定の 種3 から 「漏れ疑い」 (= 劇場版コミカライズ/抜粋本/アニメ版) を炙り出す。

機械フィルタ (title prefix / imprint) を 素通りした が 内容的に 漫画本編で
ない 疑いの entry を flag。 種3 は 削らない (= 疑いリスト TSV 出力、 個別 mark 用)。

flag (= 複数該当で 疑い度↑):
  SUB        = key に sub: あり (= 副題付き = 本編でなく 派生/劇場版/番外の可能性)
  FEW_VOL    = keep standard 最大巻数 <= 2 (= 劇場版コミカライズ/上下巻 の典型)
  ANIME_IMP  = keep edition imprint に アニメ/フィルム/劇場/シアター 含む (= pattern未登録漏れ)
  COLL_WORD  = title/sub に セレクション/総集編/作品集/コレクション/選集/名作選/短編 等
"""
import sys, re, sqlite3, yaml, importlib.util
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict, Counter

spec = importlib.util.spec_from_file_location('promote', 'scripts/_promote-bulk-v2.py')
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)

ANIME_IMP_WORDS = ['アニメ', 'フィルム', '劇場', 'シアター', 'ムービー', 'Animation', 'anime']
COLL_WORDS = ['セレクション', 'コレクション', '総集編', '作品集', '選集', '名作選',
              '名作集', 'ラブセレクション', 'ベスト', '短編集', '短篇集']

def main():
    db = sqlite3.connect('.cache/db-v2.sqlite')
    db.text_factory = lambda b: b.decode('utf-8', errors='replace')
    ed_vol = {}
    for eid, n in db.execute('SELECT edition_id, COUNT(*) FROM volumes GROUP BY edition_id'):
        ed_vol[eid] = n
    # series_key → [(type, imprint, nvol, max_num)]
    sk_eds = defaultdict(list)
    ed_maxnum = {}
    for eid, mx in db.execute('SELECT edition_id, MAX(number) FROM volumes GROUP BY edition_id'):
        ed_maxnum[eid] = mx or 0
    for sk, eid, typ, imp in db.execute('''
        SELECT s.series_key, e.id, e.type, e.imprint
        FROM series s JOIN editions e ON e.series_id = s.id
    '''):
        sk_eds[sk].append((eid, typ, imp or '', ed_vol.get(eid, 0), ed_maxnum.get(eid, 0)))
    db.close()

    with open('data/seeds/series-supplement-v2.yml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    suspects = []
    flag_cnt = Counter()
    for e in data['series']:
        key = e.get('key', '')
        names = [p[5:] for p in key.split('|') if p.startswith('name:')]
        if not names: continue
        title = names[-1]
        sub = next((p[4:] for p in key.split('|') if p.startswith('sub:')), '')
        # title-level で既に drop されるものは 対象外 (= 既に弾けてる)
        if any(title.startswith(p) for p in P.DROP_TITLE_PREFIX_PATTERNS): continue
        if any(p in title for p in P.DROP_TITLE_CONTAINS_PATTERNS): continue
        eds = sk_eds.get(key, [])
        keep_eds = [(typ, imp, nv, mx) for eid, typ, imp, nv, mx in eds
                    if nv > 0 and P.edition_passes_filter({'type': typ, 'imprint': imp})]
        if not keep_eds: continue  # KEEP のみ対象

        flags = []
        if sub: flags.append('SUB')
        std_max = max([mx for typ, imp, nv, mx in keep_eds if typ == 'standard'] or [0])
        all_max = max(mx for typ, imp, nv, mx in keep_eds)
        if all_max <= 2: flags.append('FEW_VOL')
        if any(w in imp for typ, imp, nv, mx in keep_eds for w in ANIME_IMP_WORDS):
            flags.append('ANIME_IMP')
        if any(w in title or w in sub for w in COLL_WORDS):
            flags.append('COLL_WORD')
        if not flags: continue
        for fl in flags: flag_cnt[fl] += 1
        suspects.append((len(flags), '+'.join(flags), title, sub, all_max,
                         '|'.join(f'{t}/{im}({mx})' for t, im, nv, mx in keep_eds)))

    suspects.sort(key=lambda x: -x[0])
    print(f'=== KEEP 内 漏れ疑い: {len(suspects):,} 件 ===')
    print(f'flag 別 (複数該当あり):')
    for fl, c in flag_cnt.most_common():
        print(f'  {fl:12s}: {c:,}')
    print()
    print('=== 複数 flag 該当 (= 疑い度高) sample top 40 ===')
    for nf, fls, title, sub, mx, eds in suspects[:40]:
        s = f' sub={sub!r}' if sub else ''
        print(f'  [{fls}] {title!r}{s} max_vol={mx}')
    print()
    # うる星 抜粋
    print('=== うる星やつら 関連の 漏れ疑い ===')
    for nf, fls, title, sub, mx, eds in suspects:
        if 'うる星' in title:
            print(f'  [{fls}] {title!r} sub={sub!r} max_vol={mx}  eds={eds}')

    # TSV 出力 (= 個別 mark 用)
    OUT = '.cache/shu3-leak-suspects.tsv'
    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        f.write('n_flags\tflags\ttitle\tsub\tmax_vol\tkeep_editions\n')
        for nf, fls, title, sub, mx, eds in suspects:
            f.write(f'{nf}\t{fls}\t{title}\t{sub}\t{mx}\t{eds}\n')
    print(f'\nTSV: {OUT} ({len(suspects):,} 件)')

if __name__ == '__main__':
    main()
