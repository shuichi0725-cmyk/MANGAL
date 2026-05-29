"""第2層: 検証対象 (L2 + 食い違い) を 種a で 突合 → 真の Wikipedia 必要数 を 確定。

tier1-targets.csv の 各行について:
  種a romaji を カナ→ローマ字化した 種3フリガナ と 突合
  - 種a と一致 → 確定 (= Wikipedia不要)
  - 種a と食い違い / 種a なし → Wikipedia対象
これで Web アクセスすべき 件数を 最小化。
"""
import sys, csv, re, difflib
sys.stdout.reconfigure(encoding='utf-8')

# カタカナ→ローマ字 (= ateji-autojudge と同じ簡易テーブル)
KATA2 = {'キャ':'kya','キュ':'kyu','キョ':'kyo','ギャ':'gya','ギュ':'gyu','ギョ':'gyo','シャ':'sha','シュ':'shu','ショ':'sho','ジャ':'ja','ジュ':'ju','ジョ':'jo','チャ':'cha','チュ':'chu','チョ':'cho','ニャ':'nya','ニュ':'nyu','ニョ':'nyo','ヒャ':'hya','ヒュ':'hyu','ヒョ':'hyo','ビャ':'bya','ビュ':'byu','ビョ':'byo','ピャ':'pya','ピュ':'pyu','ピョ':'pyo','ミャ':'mya','ミュ':'myu','ミョ':'myo','リャ':'rya','リュ':'ryu','リョ':'ryo','ヴァ':'va','ヴィ':'vi','ヴェ':'ve','ヴォ':'vo','ファ':'fa','フィ':'fi','フェ':'fe','フォ':'fo','ティ':'ti','ディ':'di','ウィ':'wi','ウェ':'we','ウォ':'wo','シェ':'she','ジェ':'je','チェ':'che','トゥ':'tu','ドゥ':'du'}
KATA1 = {'ア':'a','イ':'i','ウ':'u','エ':'e','オ':'o','カ':'ka','キ':'ki','ク':'ku','ケ':'ke','コ':'ko','ガ':'ga','ギ':'gi','グ':'gu','ゲ':'ge','ゴ':'go','サ':'sa','シ':'shi','ス':'su','セ':'se','ソ':'so','ザ':'za','ジ':'ji','ズ':'zu','ゼ':'ze','ゾ':'zo','タ':'ta','チ':'chi','ツ':'tsu','テ':'te','ト':'to','ダ':'da','デ':'de','ド':'do','ナ':'na','ニ':'ni','ヌ':'nu','ネ':'ne','ノ':'no','ハ':'ha','ヒ':'hi','フ':'fu','ヘ':'he','ホ':'ho','バ':'ba','ビ':'bi','ブ':'bu','ベ':'be','ボ':'bo','パ':'pa','ピ':'pi','プ':'pu','ペ':'pe','ポ':'po','マ':'ma','ミ':'mi','ム':'mu','メ':'me','モ':'mo','ヤ':'ya','ユ':'yu','ヨ':'yo','ラ':'ra','リ':'ri','ル':'ru','レ':'re','ロ':'ro','ワ':'wa','ヲ':'o','ン':'n','ヴ':'vu'}
def kata_to_roma(s):
    if not s: return ''
    s = ''.join(chr(ord(c)+0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)
    out=[]; i=0
    while i < len(s):
        c=s[i]
        if c in ('ッ','ー','ｰ','・',' ','　'): i+=1; continue
        if i+1<len(s) and s[i:i+2] in KATA2: out.append(KATA2[s[i:i+2]]); i+=2; continue
        if c in KATA1: out.append(KATA1[c]); i+=1; continue
        if c.isalnum(): out.append(c.lower())
        i+=1
    return ''.join(out)
def rn(s): return re.sub(r'[^a-z0-9]','',(s or '').lower())
def sim(a,b):
    if not a or not b: return 0.0
    return difflib.SequenceMatcher(None,a,b).ratio()

def main():
    rows = list(csv.DictReader(open('.cache/furigana-tier1-targets.csv', encoding='utf-8-sig')))
    cnt = {'種a一致(確定)':0, '種a食い違い(要Wiki)':0, '種aなし(要Wiki/MADB)':0, 'L3カナ化漏れ':0}
    wiki_rows = []
    for r in rows:
        tier = r['tier']; title = r['title']; kana = r['種3フリガナ']; sa = r['種a']; madb = r['MADB読み']
        if tier == 'L3_カナ化漏れ':
            cnt['L3カナ化漏れ'] += 1; continue
        if sa:
            s3r = rn(kata_to_roma(kana)); sar = rn(sa)
            if sim(s3r, sar) >= 0.8:
                cnt['種a一致(確定)'] += 1
            else:
                cnt['種a食い違い(要Wiki)'] += 1
                wiki_rows.append({'tier':tier,'title':title,'種3フリガナ':kana,'MADB読み':madb,'種a':sa})
        else:
            cnt['種aなし(要Wiki/MADB)'] += 1
            wiki_rows.append({'tier':tier,'title':title,'種3フリガナ':kana,'MADB読み':madb,'種a':''})

    print('=== 第2層: 種a突合で Wikipedia対象を絞り込み ===')
    for k,v in cnt.items():
        print(f'  {k:24s}: {v:,}')
    print()
    wiki_n = cnt['種a食い違い(要Wiki)'] + cnt['種aなし(要Wiki/MADB)']
    print(f'  → 種aで確定 (Wiki不要): {cnt["種a一致(確定)"]:,}')
    print(f'  → 真の Wikipedia 対象 : {wiki_n:,}')
    est_min = wiki_n * 0.35 / 60
    print(f'     (= 全件Wiki なら 約{est_min:.0f}分。 ただし記事あり率 ~40% で 実効はさらに減)')
    print()
    # MADB当て字側で 暫定埋めできる分 (= 種aなしだが MADBに当て字読みあり)
    OUT = '.cache/furigana-wiki-targets.csv'
    with open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['tier','title','種3フリガナ','MADB読み','種a'])
        w.writeheader(); w.writerows(wiki_rows)
    print(f'  Wikipedia対象CSV: {OUT} ({len(wiki_rows):,} 件)')

if __name__ == '__main__':
    main()
