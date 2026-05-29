"""当て字フリガナの 自動判定 (= 目視せず 種3崩れ を 信頼度付きで抽出)。

入力: .cache/ateji-3source.tsv (= MADB-A/B + 種3 + 種a_romaji)
ロジック:
  1. 種a romaji を 真値 (= 公式読み) とする
  2. MADB-A/B と 種3 を ローマ字化 (= カナ→ヘボン)
  3. 種a romaji と MADB-A/B の 類似度 (difflib) → 高い方が「公式読み」
  4. 種3 が 公式読みと 食い違う = 崩れ。 正しい読み(=公式)も提示
  5. 信頼度 = (公式との類似) - (もう片方との類似)。 差が大きいほど確実

種a が無い entry は 判定不能 (= 別途)。
出力: 崩れ候補を 信頼度順に CSV。
"""
import sys, csv, re, difflib
sys.stdout.reconfigure(encoding='utf-8')

# ---- カタカナ → ローマ字 (簡易、 類似度比較用なので 完璧でなくてよい) ----
KATA2 = {
 'キャ':'kya','キュ':'kyu','キョ':'kyo','ギャ':'gya','ギュ':'gyu','ギョ':'gyo',
 'シャ':'sha','シュ':'shu','ショ':'sho','ジャ':'ja','ジュ':'ju','ジョ':'jo',
 'チャ':'cha','チュ':'chu','チョ':'cho','ニャ':'nya','ニュ':'nyu','ニョ':'nyo',
 'ヒャ':'hya','ヒュ':'hyu','ヒョ':'hyo','ビャ':'bya','ビュ':'byu','ビョ':'byo',
 'ピャ':'pya','ピュ':'pyu','ピョ':'pyo','ミャ':'mya','ミュ':'myu','ミョ':'myo',
 'リャ':'rya','リュ':'ryu','リョ':'ryo','ヴァ':'va','ヴィ':'vi','ヴェ':'ve','ヴォ':'vo',
 'ファ':'fa','フィ':'fi','フェ':'fe','フォ':'fo','ティ':'ti','ディ':'di',
 'ウィ':'wi','ウェ':'we','ウォ':'wo','シェ':'she','ジェ':'je','チェ':'che',
 'ツァ':'tsa','ツェ':'tse','ツォ':'tso','ドゥ':'du','トゥ':'tu',
}
KATA1 = {
 'ア':'a','イ':'i','ウ':'u','エ':'e','オ':'o',
 'カ':'ka','キ':'ki','ク':'ku','ケ':'ke','コ':'ko','ガ':'ga','ギ':'gi','グ':'gu','ゲ':'ge','ゴ':'go',
 'サ':'sa','シ':'shi','ス':'su','セ':'se','ソ':'so','ザ':'za','ジ':'ji','ズ':'zu','ゼ':'ze','ゾ':'zo',
 'タ':'ta','チ':'chi','ツ':'tsu','テ':'te','ト':'to','ダ':'da','ヂ':'ji','ヅ':'zu','デ':'de','ド':'do',
 'ナ':'na','ニ':'ni','ヌ':'nu','ネ':'ne','ノ':'no','ハ':'ha','ヒ':'hi','フ':'fu','ヘ':'he','ホ':'ho',
 'バ':'ba','ビ':'bi','ブ':'bu','ベ':'be','ボ':'bo','パ':'pa','ピ':'pi','プ':'pu','ペ':'pe','ポ':'po',
 'マ':'ma','ミ':'mi','ム':'mu','メ':'me','モ':'mo','ヤ':'ya','ユ':'yu','ヨ':'yo',
 'ラ':'ra','リ':'ri','ル':'ru','レ':'re','ロ':'ro','ワ':'wa','ヲ':'o','ン':'n','ヴ':'vu',
}
def kata_to_roma(s):
    if not s: return ''
    # ひら→カタ
    s = ''.join(chr(ord(c)+0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)
    out = []; i = 0
    while i < len(s):
        c = s[i]
        if c == 'ッ':  # 促音 → 次子音重複 (簡易: skip)
            i += 1; continue
        if c in ('ー', 'ｰ', '・', ' ', '　'):
            i += 1; continue
        if i+1 < len(s) and s[i:i+2] in KATA2:
            out.append(KATA2[s[i:i+2]]); i += 2; continue
        if c in KATA1:
            out.append(KATA1[c]); i += 1; continue
        # 英数字/記号 はそのまま (小文字)
        if c.isalnum():
            out.append(c.lower())
        i += 1
    return ''.join(out)

def roma_norm(s):
    """ローマ字正規化: 英数字のみ 小文字"""
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())

def sim(a, b):
    if not a or not b: return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()

def is_kana_main(s):
    """カナ主体か (= フリガナとして妥当。 英数字主体 'LOVE'/'Z'/'017' は不適)"""
    body = re.sub(r'[\s　・ー]', '', s or '')
    if not body: return False
    kana = sum(1 for c in body if 'ァ' <= c <= 'ヶ' or 'ぁ' <= c <= 'ゖ')
    return kana >= len(body) * 0.5

def main():
    rows = list(csv.reader(open('.cache/ateji-3source.tsv', encoding='utf-8'), delimiter='\t'))
    header = rows[0]; rows = rows[1:]
    judged = []      # 判定できた (種a + 種3 + 種3崩れ)
    ok = 0           # 種3 が 公式と一致
    no_basis = 0     # 種a なし で 判定不能
    no_s3 = 0
    no_kana_cand = 0 # MADB に カナ読み候補なし (= 両方 英数字、 フリガナ不能)
    for r in rows:
        if len(r) < 6: continue
        title, ra, rb, s3kana, match, sa_romaji = r[:6]
        if not s3kana:
            no_s3 += 1; continue
        if not sa_romaji:
            no_basis += 1; continue
        # ローマ字化
        sa = roma_norm(sa_romaji)
        s3r = roma_norm(kata_to_roma(s3kana))
        # MADB-A/B から カナ主体の読み だけ 推奨候補に (= 英数字読みは フリガナ不適)
        cands = [r for r in (ra, rb) if is_kana_main(r)]
        if not cands:
            no_kana_cand += 1; continue
        if len(cands) == 2:
            official_kana = max(cands, key=lambda r: sim(sa, roma_norm(kata_to_roma(r))))
        else:
            official_kana = cands[0]
        official_roma = roma_norm(kata_to_roma(official_kana))
        others = [r for r in (ra, rb) if r != official_kana]
        other_roma = roma_norm(kata_to_roma(others[0])) if others else ''
        conf = round(sim(sa, official_roma) - sim(sa, other_roma), 3) if other_roma else 1.0
        # 種3 が 公式読みと 一致するか
        s3_vs_official = sim(s3r, official_roma)
        if s3_vs_official >= 0.85:
            ok += 1
        else:
            # 崩れ候補。 種3 が 公式と違う
            judged.append({
                'title': title, '種3現フリガナ': s3kana, '推奨読み(公式)': official_kana,
                '種a根拠': sa_romaji, '信頼度': conf,
                '種3vs公式類似': round(s3_vs_official, 2),
                'MADB-A': ra, 'MADB-B': rb,
            })
    # 信頼度順 (= 公式が明確なものを上に)
    judged.sort(key=lambda x: -x['信頼度'])

    OUT = '.cache/ateji-autojudge.csv'
    cols = ['信頼度','種3vs公式類似','title','種3現フリガナ','推奨読み(公式)','種a根拠','MADB-A','MADB-B']
    with open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for j in judged:
            w.writerow({k: j[k] for k in cols})

    total_judgeable = ok + len(judged)
    print(f'=== 当て字 自動判定 結果 ===')
    print(f'  判定可能 (種3+種a あり): {total_judgeable:,}')
    print(f'    種3 = 公式読みと一致 (OK): {ok:,}')
    print(f'    種3 崩れ候補 (公式と不一致): {len(judged):,}')
    print(f'  判定不能 (種a なし): {no_basis:,}')
    print(f'  カナ読み候補なし (MADB両方英数字): {no_kana_cand:,}')
    print(f'  種3 未収録: {no_s3:,}')
    print(f'  CSV: {OUT}')
    print()
    # 高信頼 (conf>=0.3) の崩れ
    hi = [j for j in judged if j['信頼度'] >= 0.3]
    print(f'=== 高信頼 崩れ (信頼度>=0.3): {len(hi):,} 件 ===')
    for j in hi[:25]:
        c = j['信頼度']; t = j['title']; cur = j['種3現フリガナ']
        rec = j['推奨読み(公式)']; src = j['種a根拠']
        print(f'  [conf={c}] {t!r}')
        print(f'    種3={cur!r} → 推奨={rec!r} (種a={src!r})')

if __name__ == '__main__':
    main()
