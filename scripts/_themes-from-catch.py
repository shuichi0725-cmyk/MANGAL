# -*- coding: utf-8 -*-
"""キャッチ文から要素(themes)を付ける(2026-10-01 ユーザ指示②)。
  measure : 要素付き作品を正解データに、キーワード一致の精度を要素ごとに測る
  stage1  : 精度>=閾値かつ支持数>=下限の要素だけ、要素0の作品に付与候補(.cache/themes-from-catch/stage1.json)
  apply   : stage1.json を tags-enrich-2425.json へ純粋追加 + 変更履歴jsonl
語彙= data/enrich-out-2026-07/theme-vocab-ja.json / 書込先= tags-enrich-2425.json(英語タグ名)
"""
import json, os, re, sys, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, *p)
VOCAB = json.load(open(D('data/enrich-out-2026-07/theme-vocab-ja.json'), encoding='utf-8'))
OUT = D('.cache/themes-from-catch')
LOG = D('docs/production-diagnostics/themes-from-catch-changelog.jsonl')
PREC_MIN, SUP_MIN = 0.70, 15

KW = {
 'バンド': r'バンド|ライブハウス|軽音|ギタリスト|ボーカル',
 '料理': r'料理|シェフ|レストラン|厨房|調理|食堂|ごはん|弁当|居酒屋|パティシエ',
 '百合': r'百合|女の子同士|少女同士',
 '年の差': r'年の差|歳の差|年上の|年下の|親子ほど',
 'ヤクザ': r'ヤクザ|極道|組長|若頭|任侠|暴力団',
 '魔法': r'魔法|魔術|魔女|魔導',
 '格闘技': r'格闘|ボクシング|空手|柔道|プロレス|ボクサー|拳法|武術|レスラー|ファイター',
 '復讐': r'復讐|仇討|報復|リベンジ',
 '三角関係': r'三角関係|恋のライバル',
 '動物': r'犬|猫|動物|ネコ|イヌ|ペット|うさぎ|ウサギ|パンダ',
 '結婚': r'結婚|花嫁|新婚|プロポーズ',
 '同棲': r'同棲|ルームシェア|居候',
 '演劇': r'演劇|舞台|劇団|俳優|女優|役者',
 '片思い': r'片思い|片想い|想いを寄せ',
 '異世界': r'異世界',
 '転生': r'転生',
 '悪役令嬢': r'悪役令嬢',
 '令嬢': r'令嬢',
 'ボーイズラブ': r'ボーイズラブ|BL',
 'ハーレム': r'ハーレム',
 'ゲーム': r'ゲーム|ゲーマー',
 'デスゲーム': r'デスゲーム|殺人ゲーム|命懸けのゲーム|命がけのゲーム',
 'サバイバル': r'サバイバル|生き残|生存',
 'いじめ': r'いじめ|イジメ',
 '警察': r'警察|刑事|警視|巡査|交番|捜査官',
 '犯罪': r'犯罪|犯人|殺人|強盗|誘拐',
 '医療': r'医師|医者|病院|外科|看護|ドクター|医療',
 '麻雀': r'麻雀|雀士|雀荘',
 'ギャンブル': r'ギャンブル|賭博|賭け|カジノ|博打',
 '将棋': r'将棋|棋士',
 '野球': r'野球|甲子園|球児',
 'アイドル': r'アイドル',
 '怪獣': r'怪獣',
 '宇宙的恐怖': r'クトゥルフ|邪神',
 'スパイ': r'スパイ|諜報',
 'マフィア': r'マフィア',
 '暗殺者': r'暗殺|殺し屋',
 '不良・暴走族': r'不良|ヤンキー|暴走族|ケンカ|喧嘩',
 'ミリタリー': r'軍隊|自衛隊|戦場|兵士|軍人|傭兵',
 'ファッション': r'ファッション|モデル|服飾|デザイナー',
 'ダンス': r'ダンス|踊り|バレエ',
 '旅': r'旅',
 '車': r'レーサー|ドライバー|峠|チューン|カーレース',
 'バイク': r'バイク|ライダー',
 '鉄道': r'鉄道|電車|列車',
 '航空': r'パイロット|飛行機|航空|戦闘機',
 '農業': r'農業|農家|農場',
 '呪い': r'呪い|呪術|呪わ',
 '除霊': r'除霊|霊能|祓',
 '錬金術': r'錬金術',
 'スチームパンク': r'スチームパンク',
 'サイバーパンク': r'サイバーパンク',
 'スペースオペラ': r'宇宙艦|銀河帝国|宇宙戦艦|スペースオペラ',
 '妊娠': r'妊娠|身ごもっ|出産',
 '子育て': r'子育て|育児|シングルファーザー|シングルマザー',
 '養子': r'養子|引き取',
 '宗教': r'宗教|教団|神父|シスター|教会',
 'カルト': r'カルト|新興宗教',
 '政治': r'政治|政界|総理|議員|大統領',
 '経済': r'経済|株|投資|金融|マネー',
 '宮廷': r'宮廷|後宮|皇帝|王宮',
 '政略結婚': r'政略結婚',
 '契約結婚': r'契約結婚|契約婚',
 '婚約破棄': r'婚約破棄',
 '聖女': r'聖女',
 '勇者': r'勇者',
 'ダンジョン': r'ダンジョン|迷宮',
 '追放': r'追放',
 'スローライフ': r'スローライフ',
 '成り上がり': r'成り上が',
 '時間操作': r'時間を止|時を止|時間停止',
 'タイムループ': r'タイムループ|ループ',
 '入れ替わり': r'入れ替わ|入れかわ',
 '性別変化': r'性転換|女体化|男の娘|性別が|女になっ|男になっ',
 '超能力': r'超能力|エスパー|サイキック',
 'ヒーロー': r'ヒーロー',
 '変身': r'変身',
 '特撮': r'特撮|戦隊',
 '絵・漫画': r'漫画家|マンガ家|画家|イラストレーター',
 '写真': r'写真|カメラマン|カメラ',
 '執筆': r'小説家|作家|ライター',
 'パロディ': r'パロディ',
 'シュール': r'シュール',
 'ドタバタ': r'ドタバタ',
 '癒し系': r'癒し|ほっこり|のんびり',
 '美少女日常': r'女子高生たちの日常|日常系|ゆるい日常',
 '学園': r'高校|学園|中学|学校|教室|クラスメイト',
 '青春': r'青春',
 '家族': r'家族|兄弟|姉妹|母親|父親|きょうだい',
 '疑似家族': r'疑似家族|擬似家族|血のつながらない',
 '成長物語': r'成長',
 '陰謀': r'陰謀',
 'ティーンズラブ': r'TL|ティーンズラブ',
 '溺愛': r'溺愛',
 '御曹司': r'御曹司',
 '同居': r'同居',
 '逆ハーレム': r'逆ハーレム|逆ハー',
 '伝記': r'伝記|生涯|偉人',
 '実話': r'実話|実録|実際の',
 '自伝': r'自伝|半生|自叙伝',
 '弓道': r'弓道',
 '剣劇': r'剣士|剣豪|剣術|侍|斬',
 '銃': r'銃|ガンマン|スナイパー',
 '神話': r'神話|神々',
 'おとぎ話': r'おとぎ話|童話',
 '古典文学': r'古典|源氏|平家',
 '風刺': r'風刺',
 '環境': r'環境|自然保護',
 '配信': r'配信|YouTuber|ユーチューバー|VTuber',
 'お仕事': r'仕事|会社|OL|サラリーマン|社員|新人',
 'LGBTQ+': r'LGBT|ゲイ|レズビアン|トランスジェンダー|同性愛',
 '残酷描写': r'残酷|惨殺|凄惨|グロ',
 '悲劇': r'悲劇|悲惨',
 '自殺': r'自殺',
 '逃亡': r'逃亡|逃げ',
 '更生': r'更生',
 '学習': r'受験|勉強|学習|塾|家庭教師',
 '拷問': r'拷問',
 'テロ': r'テロ',
 'パンデミック': r'パンデミック|ウイルス|感染',
 '麻薬': r'麻薬|ドラッグ|薬物',
 '奴隷': r'奴隷',
 '船': r'船|海賊|航海',
 '天文': r'天文|星空',
 'ミュージカル': r'ミュージカル',
 'カードバトル': r'カードバトル|カードゲーム|デュエル',
 'メイク': r'メイク|化粧',
 'ボディイメージ': r'ダイエット|容姿|体型',
 '偽装恋愛': r'偽装|フリをし|ふりをし|偽の恋人|偽りの恋人',
 '幼馴染': r'幼馴染|幼なじみ',
 '夫婦': r'夫婦',
 '修行・仙術': r'仙人|仙術|修仙',
 'クロスオーバー': r'クロスオーバー',
 '変身・変化': r'変身|姿が変わ',
}
KW = {k: re.compile(v) for k, v in KW.items() if k in VOCAB}


_BR = re.compile(r'「[^」]*」|『[^』]*』')


def strip_br(c):
    """括弧内(「」『』)だけの一致は除外(あだ名・作品名・セリフからの誤付与封じ)"""
    return _BR.sub('', c)


def load():
    ix = json.load(open(D('data/manga-list-index.json'), encoding='utf-8'))
    rows = [dict(zip(ix['f'], r)) for r in ix['d']]
    catch = json.load(open(D('data/manga-catch-index.json'), encoding='utf-8'))
    return [(r, catch[r['slug']]) for r in rows if r['cover'] and catch.get(r['slug'])]


def measure(pairs):
    lab = [(r, c) for r, c in pairs if r['themes']]
    res = {}
    for t, rx in KW.items():
        m = [(r, c) for r, c in lab if rx.search(strip_br(c))]
        hit = sum(1 for r, c in m if t in r['themes'])
        pos = sum(1 for r, c in lab if t in r['themes'])
        res[t] = {'n': len(m), 'hit': hit, 'prec': (hit / len(m) if m else 0), 'pos': pos,
                  'recall': (hit / pos if pos else 0)}
    return res


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else 'measure'
    pairs = load()
    zero = [(r, c) for r, c in pairs if not r['themes']]
    res = measure(pairs)
    if mode == 'measure':
        print(f'書影+キャッチ {len(pairs)} / 要素0 {len(zero)} / 要素あり {len(pairs)-len(zero)}')
        for t, v in sorted(res.items(), key=lambda x: -x[1]['prec']):
            ok = '*' if v['prec'] >= PREC_MIN and v['n'] >= SUP_MIN else ' '
            print(f"{ok}{t}\tprec={v['prec']:.0%}\tn={v['n']}\thit={v['hit']}\tpos={v['pos']}\trecall={v['recall']:.0%}")
    elif mode == 'stage1':
        adopt = {t for t, v in res.items() if v['prec'] >= PREC_MIN and v['n'] >= SUP_MIN}
        st = {}
        for r, c in zero:
            ts = [t for t in adopt if KW[t].search(strip_br(c))]
            if ts:
                st[r['slug']] = {'themes': ts, 'kw': {t: KW[t].search(strip_br(c)).group(0) for t in ts}}
        json.dump({'adopt': sorted(adopt), 'items': st}, open(os.path.join(OUT, 'stage1.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        cnt = {}
        for v in st.values():
            for t in v['themes']:
                cnt[t] = cnt.get(t, 0) + 1
        print('採用要素', len(adopt), '/ 付与作品', len(st), '/ 付与のべ', sum(cnt.values()))
        print(sorted(cnt.items(), key=lambda x: -x[1]))

    elif mode == 'apply':
        # 使い方: apply <stage1|stage2|genre|gray-rescue> [--go] [--model=...]  (--goなし=dry-run)
        import shutil, yaml
        src = sys.argv[2]; go = '--go' in sys.argv
        model = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--model=')), 'sonnet-5.5')
        items = json.load(open(os.path.join(OUT, src + '.json'), encoding='utf-8'))['items']
        ov = (yaml.safe_load(open(D('data/seeds/slug-overrides.yml'), encoding='utf-8')) or {}).get('overrides', {})
        pub2src = {(v or {}).get('slug'): k for k, v in ov.items() if isinstance(v, dict) and v.get('slug')}
        tp = D('data/seeds/tags-enrich-2425.json')
        tags = json.load(open(tp, encoding='utf-8'))
        now = datetime.datetime.now().isoformat(timespec='seconds')
        changed, logs = [], []
        for s, v in items.items():
            k = pub2src.get(s, s)            # 要素seedのキー = SRC slug(promoteの`slug`)
            if not os.path.exists(D('data/manga.v2', k + '.yml')):
                print('NOFILE', s, k); continue
            add = [VOCAB[t] for t in v['themes'] if t in VOCAB]
            add = [t for t in dict.fromkeys(add) if t not in tags.get(k, [])]
            if not add: continue
            tags[k] = list(tags.get(k, [])) + add
            changed.append(k)
            logs.append({'slug': s, 'src': k, 'themes_add': [t for t in v['themes'] if VOCAB[t] in add],
                         'basis': v.get('kw') or 'ai', 'stage': src, 'model': model, 'at': now})
        print(f'{src}: 付与 {len(changed)} 作 / のべ {sum(len(l["themes_add"]) for l in logs)}')
        if go:
            shutil.copy2(tp, D('.cache', 'tags-enrich-2425.json.bak-themes-' + now.replace(':', '')))
            json.dump(tags, open(tp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
            with open(LOG, 'a', encoding='utf-8') as f:
                for l in logs: f.write(json.dumps(l, ensure_ascii=False) + '\n')
            open(os.path.join(OUT, src + '-changed.txt'), 'w', encoding='utf-8').write(','.join(changed))
            print('applied; changed slug list ->', src + '-changed.txt')
