"""種3 フリガナ 全件見直し 第1層: 全ソース突合 → 自動確定/食い違い 分離。

各 種3 entry を 分類:
  L1_確定        = 種3 = MADB単一読み (= 当て字なし作品で 一致)
  L2_当て字検証  = MADB が 2読み (= 当て字あり) → 種a/Wikipedia 検証が必要
  L3_カナ化漏れ  = 種3 title_kana に アルファベット残存
  食い違い        = MADB単一読み だが 種3 と不一致 (= 種3独自/崩れ)
  種aのみ        = MADB照合なし だが 種a あり
  ソースなし      = MADB照合なし + 種a なし

出力: tier別件数 + Wikipedia検証対象 (L2 + 食い違い) を CSV。
"""
import json, sys, re, gzip, yaml
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict

PAREN = [r'〜[^〜]*〜', r'～[^～]*～', r'\([^)]*\)', r'（[^）]*）', r'\[[^\]]*\]', r'【[^】]*】']
SEP = ['・','·','·','⋅','•','∙']
def title_norm(s):
    if not s: return ''
    for p in PAREN: s = re.sub(p, '', s)
    s = re.sub(r'[:：].*$', '', s)
    for sep in SEP: s = s.replace(sep, '')
    return re.sub(r'[\s　]+', '', s).strip().lower()

def base_label(label):
    s = re.sub(r'\s*no\.?\s*\d+.*$', '', label, flags=re.I)
    s = re.sub(r'\s*第?\s*\d+\s*巻.*$', '', s)
    s = re.sub(r'\s*\(\d+\).*$', '', s)
    s = re.sub(r'\s+\d+\s*$', '', s)
    return s.strip() or label

def norm_reading(s):
    if not s: return ''
    s = ''.join(chr(ord(c)+0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)
    s = re.sub(r'[\s　・·ー\-ｰ]', '', s)
    return s.lower()

def main():
    # ===== MADB: title_norm → 読み集合 (正規化後ユニーク) + 生読み =====
    print('loading MADB (全作品)...', flush=True)
    d = json.load(open('.cache/madb/metadata101.json', encoding='utf-8'))
    madb = defaultdict(set)       # title_norm → {norm_reading}
    madb_raw = defaultdict(list)  # title_norm → [生読み] (代表表示用)
    for r in d['@graph']:
        label = r.get('rdfs:label', '')
        name = r.get('schema:name')
        if not isinstance(label, str): continue
        if isinstance(name, list):
            hrkt = [x['@value'] for x in name if isinstance(x, dict) and x.get('@language') == 'ja-hrkt']
            disp = name[0] if name and isinstance(name[0], str) else label
        else:
            hrkt = []; disp = label
        if not hrkt: continue
        bt = title_norm(base_label(disp))
        if not bt: continue
        for h in hrkt:
            nr = norm_reading(h)
            if nr and nr not in madb[bt]:
                madb[bt].add(nr)
                madb_raw[bt].append(h)
    print(f'  MADB ユニーク作品(title_norm): {len(madb):,}', flush=True)

    # ===== 種a =====
    print('loading 種a...', flush=True)
    shua = {}
    with gzip.open('.cache/anilist-manga-dump.jsonl.gz', 'rt', encoding='utf-8') as f:
        for line in f:
            try: e = json.loads(line)
            except: continue
            t = e.get('title') or {}
            tn = title_norm(t.get('native') or '')
            if tn and tn not in shua: shua[tn] = t.get('romaji') or ''

    # ===== 種3 全件 分類 =====
    print('loading 種3 + 分類...', flush=True)
    v2 = yaml.safe_load(open('data/seeds/series-supplement-v2.yml', encoding='utf-8'))
    cnt = defaultdict(int)
    wiki_targets = []  # L2 + 食い違い (= Wikipedia検証対象)
    for e in v2['series']:
        names = [p[5:] for p in e['key'].split('|') if p.startswith('name:')]
        if not names: continue
        title = names[-1]
        kana = e.get('title_kana') or ''
        tn = title_norm(title)
        has_alpha = bool(re.search(r'[A-Za-z]', kana))
        readings = madb.get(tn)
        sa = shua.get(tn, '')

        if has_alpha:
            tier = 'L3_カナ化漏れ'
        elif readings:
            if len(readings) >= 2:
                tier = 'L2_当て字検証'
            elif norm_reading(kana) in readings:
                tier = 'L1_確定(MADB一致)'
            else:
                tier = '食い違い(MADB単一≠種3)'
        elif sa:
            tier = '種aのみ(MADB照合なし)'
        else:
            tier = 'ソースなし'
        cnt[tier] += 1
        if tier in ('L2_当て字検証', '食い違い(MADB単一≠種3)', 'L3_カナ化漏れ'):
            raws = madb_raw.get(tn, [])
            wiki_targets.append({
                'tier': tier, 'title': title, '種3フリガナ': kana,
                'MADB読み': ' | '.join(raws[:3]), '種a': sa,
                'Wiki要': '要' if tier != 'L3_カナ化漏れ' else '',
            })

    total = sum(cnt.values())
    print()
    print(f'=== 種3 フリガナ 第1層 分類 ({total:,} 件) ===')
    order = ['L1_確定(MADB一致)', 'L2_当て字検証', '食い違い(MADB単一≠種3)',
             'L3_カナ化漏れ', '種aのみ(MADB照合なし)', 'ソースなし']
    for k in order:
        print(f'  {k:26s}: {cnt[k]:7,} ({cnt[k]*100/total:.1f}%)')
    print()
    auto = cnt['L1_確定(MADB一致)']
    wiki_n = cnt['L2_当て字検証'] + cnt['食い違い(MADB単一≠種3)']
    print(f'  → 自動確定 (検証不要)        : {auto:,} ({auto*100/total:.0f}%)')
    print(f'  → Wikipedia検証 対象        : {wiki_n:,} (L2 + 食い違い)')
    print(f'  → 機械カナ化 (L3)           : {cnt["L3_カナ化漏れ"]:,}')
    print(f'  → ソース乏しい (種aのみ+なし): {cnt["種aのみ(MADB照合なし)"] + cnt["ソースなし"]:,}')

    OUT = '.cache/furigana-tier1-targets.csv'
    import csv
    with open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['tier','title','種3フリガナ','MADB読み','種a','Wiki要'])
        w.writeheader(); w.writerows(wiki_targets)
    print(f'\n  検証対象CSV: {OUT} ({len(wiki_targets):,} 件)')

if __name__ == '__main__':
    main()
