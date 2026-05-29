"""抜粋本系 語を 「一語ずつ」 棚卸し (= title + sub 両方で 検出)。

目的: どの語が 確実に drop (= 既刊抜粋本) で、 どの語が keep すべき
(= 描き下ろし短編集) か を 語別件数 + サンプルで 見極める。

既存 DROP_TITLE_CONTAINS (= title のみ判定) で既に弾ける語と、
sub に隠れて漏れる分を 区別。
"""
import sys, sqlite3, yaml, importlib.util
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict

spec = importlib.util.spec_from_file_location('promote', 'scripts/_promote-bulk-v2.py')
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)

# 検討する 抜粋本系 語 (= 一語ずつ 見極める)
WORDS = ['傑作集', '傑作選', 'ベストセレクション', '名作集', '名作選',
         'セレクション', 'ベスト', '自選', '総集編', 'コレクション',
         '短編集', '短篇集', '作品集', '初期作品集']

def main():
    db = sqlite3.connect('.cache/db-v2.sqlite')
    db.text_factory = lambda b: b.decode('utf-8', errors='replace')
    # series_key → standard 最大巻数
    sk_stdmax = {}
    for sk, mx in db.execute('''
        SELECT s.series_key, MAX(v.number)
        FROM series s JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
        WHERE e.type='standard' GROUP BY s.series_key
    '''):
        sk_stdmax[sk] = mx or 0
    db.close()

    with open('data/seeds/series-supplement-v2.yml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # word → {'title': [], 'sub': []} (= どこでヒットしたか)
    word_hits = {w: {'title': [], 'sub': []} for w in WORDS}
    for e in data['series']:
        key = e.get('key', '')
        names = [p[5:] for p in key.split('|') if p.startswith('name:')]
        if not names: continue
        title = names[-1]
        sub = next((p[4:] for p in key.split('|') if p.startswith('sub:')), '')
        stdmax = sk_stdmax.get(key, 0)
        for w in WORDS:
            if w in title:
                word_hits[w]['title'].append((title, sub, stdmax))
            elif w in sub:  # title で 当たらず sub で当たる = 漏れ分
                word_hits[w]['sub'].append((title, sub, stdmax))

    # 既存 DROP_TITLE_CONTAINS に 含まれる語か
    existing = set(P.DROP_TITLE_CONTAINS_PATTERNS)

    print('=== 抜粋本系 語別 棚卸し (title hit / sub hit) ===')
    print(f'{"語":16s} {"既存登録":8s} {"title":>7s} {"sub漏れ":>7s}')
    for w in WORDS:
        reg = '○' if w in existing else '-'
        nt = len(word_hits[w]['title'])
        ns = len(word_hits[w]['sub'])
        print(f'  {w:14s} {reg:^8s} {nt:7,} {ns:7,}')
    print()
    for w in WORDS:
        nt = len(word_hits[w]['title']); ns = len(word_hits[w]['sub'])
        if nt + ns == 0: continue
        reg = '(既存登録済)' if w in existing else '(未登録)'
        print(f'=== 「{w}」 {reg}  title={nt} sub漏れ={ns} ===')
        # sub 漏れ サンプル (= title 判定を 素通りした分)
        if ns:
            print(f'  --- sub に隠れて漏れている分 (= 要対応) ---')
            for title, sub, mx in word_hits[w]['sub'][:8]:
                print(f'    title={title!r} sub={sub!r} std最大巻={mx}')
        # title hit サンプル
        if nt:
            print(f'  --- title hit 分 ---')
            for title, sub, mx in word_hits[w]['title'][:6]:
                print(f'    title={title!r} std最大巻={mx}')
        print()

if __name__ == '__main__':
    main()
