"""Phase A: 種3 フリガナ 崩れ 328件 を 直接書き換え (= 高信頼分のみ)。

対象:
  - 崩れ確定276 (= furigana-fix-candidates.csv の 「MADB一致(種3崩れ)」)
    → 採用 = MADB読み (Wiki一致する分かち書き)
  - 当て字確定52 (= wikipedia-yomi-verify.csv の 「種a正(崩れ確定)」)
    → 採用 = 種a推奨 (= MADB分かち書き)

安全策: backup → 該当行のみテキスト置換 (形式保持) → yaml再パース検証。
key特定 = 種3 の (title, 現title_kana) で 一意照合 (= 同名でもフリガナ違えば区別)。
"""
import sys, csv, re, yaml, shutil, datetime
sys.stdout.reconfigure(encoding='utf-8')

V2 = 'data/seeds/series-supplement-v2.yml'

def hira2kata(s):
    return ''.join(chr(ord(c)+0x60) if 'ぁ' <= c <= 'ゖ' else c for c in (s or ''))
def norm(s):
    return re.sub(r'[\s　・ー]', '', hira2kata(s or '')).lower()

def main():
    # 1. 種3 load → (title, title_kana) → key
    v2 = yaml.safe_load(open(V2, encoding='utf-8'))
    tk2key = {}
    dup_tk = set()
    for e in v2['series']:
        names = [p[5:] for p in e['key'].split('|') if p.startswith('name:')]
        if not names: continue
        t = (names[-1], e.get('title_kana') or '')
        if t in tk2key: dup_tk.add(t)
        tk2key[t] = e['key']

    fixes = {}  # key → (new_kana, new_seg, source)

    # 2a. 崩れ確定276
    for r in csv.DictReader(open('.cache/furigana-fix-candidates.csv', encoding='utf-8-sig')):
        if r['判定'] != 'MADB一致(種3崩れ)': continue
        t = (r['title'], r['種3現'])
        if t in dup_tk: continue  # 曖昧はskip
        key = tk2key.get(t)
        if not key: continue
        wiki = r['Wikipediaよみ']
        seg = None
        for m in r['MADB読み'].split('|'):
            if norm(m.strip()) == norm(wiki):
                seg = m.strip(); break
        if not seg: seg = hira2kata(wiki)
        seg = hira2kata(seg)
        kana = re.sub(r'[\s　]', '', seg)
        fixes[key] = (kana, seg, 'wiki-madb')

    # 2b. 当て字確定52
    for r in csv.DictReader(open('.cache/wikipedia-yomi-verify.csv', encoding='utf-8-sig')):
        if r['判定'] != '種a正(崩れ確定)': continue
        t = (r['title'], r['種3現'])
        if t in dup_tk: continue
        key = tk2key.get(t)
        if not key: continue
        seg = hira2kata(r['種a推奨'])
        kana = re.sub(r'[\s　]', '', seg)
        fixes[key] = (kana, seg, 'ateji-wiki')

    print(f'修正対象 key: {len(fixes)} (崩れ + 当て字、 曖昧title除外後)', flush=True)
    if not fixes:
        print('対象なし、 中断'); return

    # 3. backup
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bak = f'.cache/series-supplement-v2.yml.bak-{ts}'
    shutil.copy(V2, bak)
    print(f'backup: {bak}', flush=True)

    # 4. 該当行のみ テキスト置換
    lines = open(V2, encoding='utf-8').read().split('\n')
    out = []
    cur_key = None
    n_kana = n_seg = 0
    samples = []
    for line in lines:
        m = re.match(r'  - key: (.+)$', line)
        if m: cur_key = m.group(1)
        if cur_key in fixes:
            nk, ns, src = fixes[cur_key]
            if line.startswith('    title_kana: '):
                old = line.split(': ', 1)[1]
                if old != nk and len(samples) < 15:
                    samples.append((cur_key.split('|')[-1].replace('name:', ''), old, nk))
                line = f'    title_kana: {nk}'
                n_kana += 1
            elif line.startswith('    title_kana_segmented: '):
                line = f'    title_kana_segmented: {ns}'
                n_seg += 1
        out.append(line)
    new_text = '\n'.join(out)

    # 5. yaml 再パース検証 (= 壊れてないか)
    try:
        yaml.safe_load(new_text)
    except Exception as ex:
        print(f'❌ yaml パース失敗、 書き込み中止: {ex}')
        return
    open(V2, 'w', encoding='utf-8').write(new_text)
    print(f'✓ 書き換え完了: title_kana {n_kana}行 / segmented {n_seg}行', flush=True)
    print()
    print('=== サンプル (種3崩れ → 修正後) ===')
    for title, o, n in samples:
        print(f'  {title!r}: {o!r} → {n!r}')

if __name__ == '__main__':
    main()
