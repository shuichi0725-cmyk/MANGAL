"""=併記 19件 の フリガナ修正 (= ユーザ確認済、 ZERO は保留)。

key → (title_kana 連結, title_kana_segmented 分かち書き) を 直書き。
種3 backup → 該当行のみテキスト置換 → yaml再パース検証。
"""
import sys, re, yaml, shutil, datetime
sys.stdout.reconfigure(encoding='utf-8')

V2 = 'data/seeds/series-supplement-v2.yml'

# key → (kana, segmented)  ※ ユーザ確認済
FIX = {
    'name:CLAMP|name:xxxHOLiC': ('ホリック', 'ホリック'),
    'name:Mecha-roots|name:Nyaight of the living cat': ('ニャイトオブザリビングキャット', 'ニャイト オブ ザ リビング キャット'),
    'name:Moriyo|name:Shiroi asa ni': ('シロイアサニ', 'シロイ アサ ニ'),
    'name:Satoshi Yamamoto|name:Pocket monsters special': ('ポケットモンスタースペシャル', 'ポケット モンスター スペシャル'),
    'name:かわもとまい|name:アンリの靴': ('アンリノクツ', 'アンリ ノ クツ'),
    'name:岩見樹代子|name:ルミナス': ('ルミナスブルー', 'ルミナス ブルー'),
    'name:京極夏彦|name:ルー=ガルー': ('ルーガルー', 'ルーガルー'),
    'name:中尾礼|name:花屋=式': ('ハナヤシキ', 'ハナヤ シキ'),
    'name:麻乃真純|name:5+わん=ロク': ('ゴワンロク', 'ゴワン ロク'),
    'qid:Q11227458|name:ふかふかダンジョン攻略記': ('フカフカダンジョンコウリャクキ', 'フカフカ ダンジョン コウリャクキ'),
    'qid:Q11263734|name:旅×女=OB': ('タビオンナオービー', 'タビ オンナ オービー'),
    'qid:Q11264757|name:Kurofunemaru de Rio': ('ヒオノクロフネマル', 'ヒオ ノ クロフネマル'),
    'qid:Q11359320|name:1+2=パラダイス': ('1タス2ハパラダイス', '1 タス 2 ハ パラダイス'),
    'qid:Q11436413|name:シルシア': ('シルシアコード', 'シルシア コード'),
    'qid:Q11645305|name:Yamatai': ('ヤマタイ', 'ヤマタイ'),
    'qid:Q1319777|name:九龍で会いましょう': ('カオルーンデアイマショウ', 'カオルーン デ アイマショウ'),
    'qid:Q1388268|name:天國': ('パライゾ', 'パライゾ'),
    'qid:Q17224076|name:ルー=ガルー': ('ルーガルー', 'ルーガルー'),
    'qid:Q18818317|name:Wixoss diva (A) live try!!!': ('ウィクロスディーヴァアライブトライ', 'ウィクロス ディーヴァ アライブ トライ'),
}

def main():
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    shutil.copy(V2, f'.cache/series-supplement-v2.yml.bak-{ts}')
    print(f'backup: .cache/series-supplement-v2.yml.bak-{ts}')

    lines = open(V2, encoding='utf-8').read().split('\n')
    out = []
    cur = None
    nk = ns = 0
    seen = set()
    for line in lines:
        m = re.match(r'  - key: (.+)$', line)
        if m: cur = m.group(1)
        if cur in FIX:
            kana, seg = FIX[cur]
            if line.startswith('    title_kana: '):
                line = f'    title_kana: {kana}'; nk += 1; seen.add(cur)
            elif line.startswith('    title_kana_segmented: '):
                line = f'    title_kana_segmented: {seg}'; ns += 1
        out.append(line)
    text = '\n'.join(out)
    try:
        yaml.safe_load(text)
    except Exception as ex:
        print(f'❌ yaml失敗、中止: {ex}'); return
    open(V2, 'w', encoding='utf-8').write(text)
    print(f'✓ title_kana {nk}行 / segmented {ns}行 書換')
    missing = set(FIX) - seen
    if missing:
        print(f'⚠ key見つからず: {missing}')

if __name__ == '__main__':
    main()
