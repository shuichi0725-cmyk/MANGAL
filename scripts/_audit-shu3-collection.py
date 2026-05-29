"""コレクション/セレクション/ベスト の 抜粋本 vs 作品名 を 判別できるか検証。

仮説: 「同作者(qid)に 本編(別series, より多巻)が存在 + 自身は巻数僅少」 なら
      派生抜粋本。 独立作品(モンスター・コレクション等)は 本編なし。

各 entry に 判別 signal を 付けて 出力:
  - 自身の standard 最大巻
  - 同 qid(作者)配下の 他 series 最大巻 (= 本編候補の規模)
  - title が カタカナ/ASCII のみ (= 外来語複合 = 作品名の疑い)
"""
import sys, sqlite3, yaml, re
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict

WORDS = ['コレクション', 'セレクション', 'ベスト']

def is_katakana_ascii_only(s):
    """漢字/ひらがな を含まない (= カタカナ+ASCII のみ = 外来語複合 作品名の疑い)"""
    return not bool(re.search(r'[一-龯ぁ-ん]', s))

def main():
    db = sqlite3.connect('.cache/db-v2.sqlite')
    db.text_factory = lambda b: b.decode('utf-8', errors='replace')
    # series_key → (qid, standard最大巻)
    sk_qid = {}; sk_stdmax = defaultdict(int)
    for sk, qid in db.execute('SELECT series_key, qid FROM series'):
        sk_qid[sk] = qid
    for sk, mx in db.execute('''
        SELECT s.series_key, MAX(v.number) FROM series s
        JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
        WHERE e.type='standard' GROUP BY s.series_key
    '''):
        sk_stdmax[sk] = mx or 0
    # qid → 配下 series の 最大 standard 巻 (= 本編規模)
    qid_maxvol = defaultdict(int)
    qid_nseries = defaultdict(int)
    for sk, qid in sk_qid.items():
        if qid:
            qid_nseries[qid] += 1
            qid_maxvol[qid] = max(qid_maxvol[qid], sk_stdmax.get(sk, 0))
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
        hit = next((w for w in WORDS if w in title or w in sub), None)
        if not hit: continue
        qid = sk_qid.get(key)
        my_max = sk_stdmax.get(key, 0)
        other_max = 0
        if qid:
            # 同 qid 内 他 series の 最大巻 (= 自分以外)
            other_max = qid_maxvol.get(qid, 0)  # 近似 (自分含むが 本編規模 把握には十分)
        kana_ascii = is_katakana_ascii_only(title)
        rows.append((hit, title, sub, qid, my_max, other_max, qid_nseries.get(qid, 0) if qid else 0, kana_ascii))

    # 判別 試行: 抜粋疑い = 同qidに本編あり(other_max>=5 かつ 自身<=3) かつ not(カナ/ASCII単独作品名)
    print(f'=== コレクション/セレクション/ベスト 含む entry: {len(rows):,} ===')
    print()
    by_word = defaultdict(lambda: {'excerpt': 0, 'work': 0})
    excerpt_samples = []
    work_samples = []
    for hit, title, sub, qid, mymax, omax, ns, ka in rows:
        # 判別 rule (= 検証用):
        #   抜粋疑い: qid本編が大規模(>=5巻) かつ 自身 僅少(<=3) かつ カナ/ASCII単独でない
        is_excerpt = (qid and omax >= 5 and mymax <= 3 and not ka)
        if is_excerpt:
            by_word[hit]['excerpt'] += 1
            if len(excerpt_samples) < 30:
                excerpt_samples.append((hit, title, sub, mymax, omax, ns))
        else:
            by_word[hit]['work'] += 1
            if len(work_samples) < 25:
                work_samples.append((hit, title, sub, mymax, omax, ns, ka))

    print('=== 語別 判別結果 (rule: 同qid本編>=5巻 & 自身<=3巻 & not カナ/ASCII単独) ===')
    for w in WORDS:
        d = by_word[w]
        print(f'  {w}: 抜粋疑い={d["excerpt"]:,}  作品名/判断保留={d["work"]:,}')
    print()
    print('=== 抜粋疑い sample (= drop 候補) ===')
    for hit, title, sub, mymax, omax, ns in excerpt_samples[:25]:
        s = f' sub={sub!r}' if sub else ''
        print(f'  [{hit}] {title!r}{s} 自身{mymax}巻 / 同作者最大{omax}巻 (作者作品数{ns})')
    print()
    print('=== 作品名/保留 sample (= keep 側) ===')
    for hit, title, sub, mymax, omax, ns, ka in work_samples[:25]:
        s = f' sub={sub!r}' if sub else ''
        tag = 'カナ/ASCII' if ka else ''
        print(f'  [{hit}] {title!r}{s} 自身{mymax}巻 / 同作者最大{omax}巻 {tag}')

if __name__ == '__main__':
    main()
