"""当て字フリガナの 3ソース突合 (= MADB / 種3 / 種a) 調査。

目的: MADB が 複数 ja-hrkt (= 普通読み + 当て字読み) を持つ作品で、
      種3 が どちらを採用しているか、 種a romaji で どちらが公式か 裏取り。
      → 種3 フリガナの 当て字崩れ を 炙り出す (= 修正はしない、 調査のみ)。

手順:
  1. MADB metadata: schema:name の ja-hrkt が 2つ + 正規化後も不一致 = 真の当て字
     (= 空白/長音/大小 だけの 表記揺れは 除外)
  2. 種3: title_norm → title_kana
  3. 種a: title_norm(native) → romaji
  4. title_norm で 3ソース結合 → TSV 出力
"""
import json, sys, re, gzip, yaml
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict

# ---- title 正規化 (= 3ソース結合キー) ----
PAREN = [r'〜[^〜]*〜', r'～[^～]*～', r'\([^)]*\)', r'（[^）]*）', r'\[[^\]]*\]', r'【[^】]*】']
SEP = ['・','·','·','⋅','•','∙']
def title_norm(s):
    if not s: return ''
    for p in PAREN: s = re.sub(p, '', s)
    s = re.sub(r'[:：].*$', '', s)
    for sep in SEP: s = s.replace(sep, '')
    return re.sub(r'[\s　]+', '', s).strip().lower()

def base_label(label):
    # 巻番号 (no.N / 第N巻 / (N) / 末尾数字) を 除去
    s = re.sub(r'\s*no\.?\s*\d+.*$', '', label, flags=re.I)
    s = re.sub(r'\s*第?\s*\d+\s*巻.*$', '', s)
    s = re.sub(r'\s*\(\d+\).*$', '', s)
    s = re.sub(r'\s+\d+\s*$', '', s)
    return s.strip() or label

# ---- 読み 正規化 (= 表記揺れ判定: 空白/中黒/長音/大小 除去 + ひら→カタ) ----
def norm_reading(s):
    if not s: return ''
    s = ''.join(chr(ord(c)+0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)  # ひら→カタ
    s = re.sub(r'[\s　・·ー\-ｰ]', '', s)
    return s.lower()

def main():
    # ===== 1. MADB 当て字抽出 =====
    print('loading MADB metadata...', flush=True)
    d = json.load(open('.cache/madb/metadata101.json', encoding='utf-8'))
    madb = {}  # title_norm → (display_title, reading_a, reading_b)
    for r in d['@graph']:
        label = r.get('rdfs:label', '')
        name = r.get('schema:name')
        if not isinstance(name, list) or not isinstance(label, str): continue
        hrkt = [x['@value'] for x in name if isinstance(x, dict) and x.get('@language') == 'ja-hrkt']
        if len(hrkt) < 2: continue
        # 正規化後 不一致 = 真の当て字 (表記揺れ除外)
        if norm_reading(hrkt[0]) == norm_reading(hrkt[1]): continue
        disp = name[0] if isinstance(name[0], str) else label
        bt = title_norm(base_label(disp))
        if bt and bt not in madb:
            madb[bt] = (base_label(disp), hrkt[0], hrkt[1])
    print(f'  MADB 真の当て字 作品 (概算): {len(madb):,}', flush=True)

    # ===== 2. 種3 =====
    print('loading 種3...', flush=True)
    v2 = yaml.safe_load(open('data/seeds/series-supplement-v2.yml', encoding='utf-8'))
    shu3 = {}  # title_norm → (title, title_kana)
    for e in v2['series']:
        names = [p[5:] for p in e['key'].split('|') if p.startswith('name:')]
        if not names: continue
        tn = title_norm(names[-1])
        if tn and tn not in shu3:
            shu3[tn] = (names[-1], e.get('title_kana') or '')

    # ===== 3. 種a =====
    print('loading 種a...', flush=True)
    shua = {}  # title_norm → romaji
    with gzip.open('.cache/anilist-manga-dump.jsonl.gz', 'rt', encoding='utf-8') as f:
        for line in f:
            try: e = json.loads(line)
            except: continue
            t = e.get('title') or {}
            nat = t.get('native') or ''
            tn = title_norm(nat)
            if tn and tn not in shua:
                shua[tn] = t.get('romaji') or ''

    # ===== 4. 突合 =====
    print('突合 + TSV出力...', flush=True)
    OUT = '.cache/ateji-3source.tsv'
    n_s3 = n_sa = n_both = 0
    rows = []
    for bt, (disp, ra, rb) in madb.items():
        s3 = shu3.get(bt)
        sa = shua.get(bt)
        if s3: n_s3 += 1
        if sa: n_sa += 1
        if s3 and sa: n_both += 1
        # 種3 フリガナが MADB の どちらの読みに 近いか
        s3kana = s3[1] if s3 else ''
        match = ''
        if s3kana:
            nk = norm_reading(s3kana)
            if nk == norm_reading(ra): match = 'A'
            elif nk == norm_reading(rb): match = 'B'
            else: match = '?'  # どちらとも違う
        rows.append((disp, ra, rb, s3kana, match, sa or ''))

    # 種3 にあって どちらの読みとも違う / または 種a がある = 注目
    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        f.write('title\tMADB読みA\tMADB読みB\t種3フリガナ\t種3はどちら(A/B/?)\t種a_romaji\n')
        for disp, ra, rb, s3kana, match, sa in rows:
            def c(x): return str(x).replace('\t',' ').replace('\n',' ')
            f.write('\t'.join(c(x) for x in [disp, ra, rb, s3kana, match, sa]) + '\n')

    print()
    print(f'=== 当て字 3ソース突合 結果 ===')
    print(f'  MADB 真の当て字作品: {len(madb):,}')
    print(f'  ├ 種3 と title一致: {n_s3:,}')
    print(f'  ├ 種a と title一致: {n_sa:,}')
    print(f'  └ 3ソース揃い      : {n_both:,}')
    print(f'  TSV: {OUT}')
    # 種3フリガナが MADB どちらとも違う (= 崩れ/独自) サンプル
    print()
    print('=== 種3フリガナが MADB両読みと不一致 (= 要注目) sample ===')
    cnt=0
    for disp, ra, rb, s3kana, match, sa in rows:
        if match == '?' and cnt < 20:
            print(f'  {disp!r}')
            print(f'    MADB-A={ra!r} / MADB-B={rb!r}')
            print(f'    種3   ={s3kana!r}  種a={sa!r}')
            cnt+=1

if __name__ == '__main__':
    main()
