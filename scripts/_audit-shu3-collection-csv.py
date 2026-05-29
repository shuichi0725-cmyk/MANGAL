"""コレクション/ベスト を含む 種3 entry を 目視用 CSV に出力。"""
import sys, csv, re, sqlite3, yaml, importlib.util
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict

spec = importlib.util.spec_from_file_location('promote', 'scripts/_promote-bulk-v2.py')
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)

def is_kana_ascii(s):
    return not bool(re.search(r'[一-龯ぁ-ん]', s))

def main():
    db = sqlite3.connect('.cache/db-v2.sqlite')
    db.text_factory = lambda b: b.decode('utf-8', errors='replace')
    sk_qid = {}
    for sk, qid in db.execute('SELECT series_key, qid FROM series'): sk_qid[sk] = qid
    sk_stdmax = defaultdict(int)
    for sk, mx in db.execute('''SELECT s.series_key, MAX(v.number) FROM series s
        JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
        WHERE e.type='standard' GROUP BY s.series_key'''):
        sk_stdmax[sk] = mx or 0
    qid_maxvol = defaultdict(int); qid_n = defaultdict(int)
    for sk, qid in sk_qid.items():
        if qid:
            qid_n[qid] += 1
            qid_maxvol[qid] = max(qid_maxvol[qid], sk_stdmax.get(sk, 0))
    # series_key → 作者
    sk_auth = defaultdict(list)
    for sk, name in db.execute('''SELECT s.series_key, m.name FROM series s
        JOIN series_authors sa ON sa.series_id=s.id JOIN mangaka m ON m.id=sa.mangaka_id'''):
        sk_auth[sk].append(name)
    # series_key → keep edition imprints
    ed_vol = {}
    for eid, n in db.execute('SELECT edition_id, COUNT(*) FROM volumes GROUP BY edition_id'): ed_vol[eid]=n
    sk_keepimp = defaultdict(list)
    for sk, typ, imp in db.execute('''SELECT s.series_key, e.type, e.imprint, e.id
        FROM series s JOIN editions e ON e.series_id=s.id''' if False else '''
        SELECT s.series_key, e.type, e.imprint FROM series s JOIN editions e ON e.series_id=s.id'''):
        if P.edition_passes_filter({'type': typ, 'imprint': imp or ''}):
            sk_keepimp[sk].append(f'{typ}/{imp or ""}')
    db.close()

    with open('data/seeds/series-supplement-v2.yml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    rows = []
    for e in data['series']:
        key = e.get('key', '')
        names = [p[5:] for p in key.split('|') if p.startswith('name:')]
        if not names: continue
        title = names[-1]
        sub = next((p[4:] for p in key.split('|') if p.startswith('sub:')), '')
        blob = title + ' ' + sub
        c = 'コレクション' in blob; b = 'ベスト' in blob
        if not (c or b): continue
        word = 'コレクション+ベスト' if (c and b) else ('コレクション' if c else 'ベスト')
        qid = sk_qid.get(key)
        # 作者: 種2 優先、 無ければ key の name:著者
        auth = sk_auth.get(key) or [p for p in names[:-1]]
        mymax = sk_stdmax.get(key, 0)
        omax = qid_maxvol.get(qid, 0) if qid else 0
        ns = qid_n.get(qid, 0) if qid else 0
        ka = is_kana_ascii(title)
        suspect = '抜粋疑い' if (qid and omax >= 5 and mymax <= 3 and not ka) else ''
        rows.append({
            '語': word, '抜粋疑い': suspect, 'title': title, 'subtitle': sub,
            '作者': '/'.join(auth), '自身std最大巻': mymax, '同作者最大巻': omax,
            '作者作品数': ns, 'カナASCII': '○' if ka else '',
            'keep版': '|'.join(sorted(set(sk_keepimp.get(key, [])))),
            'series_key': key,
        })
    # ソート: 抜粋疑い先頭 → 語 → 作者
    rows.sort(key=lambda r: (r['抜粋疑い'] == '', r['語'], r['作者']))

    OUT = '.cache/shu3-collection-best.csv'
    cols = ['語','抜粋疑い','title','subtitle','作者','自身std最大巻','同作者最大巻',
            '作者作品数','カナASCII','keep版','series_key']
    with open(OUT, 'w', encoding='utf-8-sig', newline='') as f:  # BOM = Excel 文字化け防止
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    n_susp = sum(1 for r in rows if r['抜粋疑い'])
    print(f'CSV: {OUT}  ({len(rows):,} 件、 うち 抜粋疑い {n_susp:,})')

if __name__ == '__main__':
    main()
