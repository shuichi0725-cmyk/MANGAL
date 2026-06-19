#!/usr/bin/env python3
"""
slug蒸留 調査(read-only・提案表): カタカナ外来語がヘボンslugのままの分を検出し英化提案。
方針=明白な英単語辞書で「題のカタカナ run が全部英単語に分解できる」時のみ英化提案。創作/不明はヘボン維持。
出力: data/seeds/slug-loanword-proposal.tsv(current→proposed) / slug-loanword-uncertain.tsv(英単語未分解=要AI)
"""
import sys,csv,re,unicodedata
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
# カタカナ→英(よく使う外来語。長い順にgreedy)
L={'ラブ':'love',
'ハート':'heart',
'キス':'kiss',
'エンジェル':'angel',
'デビル':'devil',
'デーモン':'demon',
'ゴッド':'god',
'ゴースト':'ghost',
'ヴァンパイア':'vampire',
'ウィッチ':'witch',
'ウィザード':'wizard',
'フェアリー':'fairy',
'マーメイド':'mermaid',
'エルフ':'elf',
'ドラゴン':'dragon',
'モンスター':'monster',
'ビースト':'beast',
'ウルフ':'wolf',
'タイガー':'tiger',
'ライオン':'lion',
'ベアー':'bear',
'イーグル':'eagle',
'シャーク':'shark',
'スネーク':'snake',
'キャット':'cat',
'ドッグ':'dog',
'バード':'bird',
'フィッシュ':'fish',
'ローズ':'rose',
'フラワー':'flower',
'ツリー':'tree',
'フォレスト':'forest',
'ガーデン':'garden',
'スター':'star',
'ムーン':'moon',

'スカイ':'sky',
'オーシャン':'ocean',
'リバー':'river',
'マウンテン':'mountain',
'アイランド':'island',
'ワールド':'world',
'アース':'earth',
'スペース':'space',
'ギャラクシー':'galaxy',
'プラネット':'planet',
'ユニバース':'universe',
'コスモス':'cosmos',
'キング':'king',
'クイーン':'queen',
'プリンス':'prince',
'プリンセス':'princess',
'ロード':'road',
'レディ':'lady',
'マスター':'master',
'ヒーロー':'hero',
'ヒロイン':'heroine',
'ファイター':'fighter',
'ウォリアー':'warrior',
'ソルジャー':'soldier',
'キャプテン':'captain',
'ドクター':'doctor',
'ナース':'nurse',
'ポリス':'police',
'スパイ':'spy',
'エージェント':'agent',
'キラー':'killer',
'ハンター':'hunter',
'スレイヤー':'slayer',
'ガーディアン':'guardian',
'セイバー':'saber',
'ソード':'sword',
'マジック':'magic',
'マジカル':'magical',
'ファンタジー':'fantasy',
'アドベンチャー':'adventure',
'ミステリー':'mystery',
'ホラー':'horror',
'コメディ':'comedy',
'ロマンス':'romance',
'アクション':'action',
'サスペンス':'suspense',
'ストーリー':'story',
'レジェンド':'legend',
'ヒストリー':'history',
'メモリー':'memory',
'ドリーム':'dream',
'ソウル':'soul',
'スピリット':'spirit',
'ライフ':'life',

'ブラッド':'blood',
'ボーン':'bone',
'スカル':'skull',
'ファイヤー':'fire',
'アイス':'ice',
'ウォーター':'water',
'ウインド':'wind',
'サンダー':'thunder',
'ライト':'light',
'ダーク':'dark',
'シャドウ':'shadow',
'ミラー':'mirror',
'クリスタル':'crystal',
'ダイヤモンド':'diamond',
'ゴールド':'gold',
'シルバー':'silver',
'メタル':'metal',
'アイアン':'iron',
'スチール':'steel',
'レインボー':'rainbow',

'カラーズ':'colors',
'ホワイト':'white',
'ブラック':'black',
'レッド':'red',
'ブルー':'blue',
'グリーン':'green',
'イエロー':'yellow',
'パープル':'purple',
'ピンク':'pink',
'オレンジ':'orange',
'スクール':'school',
'クラス':'class',
'クラブ':'club',
'チーム':'team',
'リーグ':'league',
'ゲーム':'game',
'スポーツ':'sports',
'ボール':'ball',
'ゴール':'goal',
'レース':'race',
'スピード':'speed',
'パワー':'power',
'スーパー':'super',
'ウルトラ':'ultra',
'メガ':'mega',
'ハイパー':'hyper',
'ベイビー':'baby',
'ガール':'girl',
'ガールズ':'girls',
'ボーイ':'boy',
'ボーイズ':'boys',

'ウーマン':'woman',
'シスター':'sister',
'ブラザー':'brother',
'マザー':'mother',
'ファーザー':'father',
'ファミリー':'family',
'チルドレン':'children',
'ツインズ':'twins',
'フレンド':'friend',
'フレンズ':'friends',
'パートナー':'partner',
'ライバル':'rival',
'エネミー':'enemy',
'ラヴァーズ':'lovers',
'カップル':'couple',
'ウェディング':'wedding',
'ハネムーン':'honeymoon',
'プロジェクト':'project',
'ミッション':'mission',
'コード':'code',
'ナンバー':'number',
'シークレット':'secret',
'デンジャー':'danger',
'トラブル':'trouble',
'クライシス':'crisis',
'チャンス':'chance',
'ミラクル':'miracle',
'ワンダー':'wonder',
'パラダイス':'paradise',
'ヘブン':'heaven',
'ヘル':'hell',
'シティ':'city',
'タウン':'town',
'ストリート':'street',
'ハウス':'house',
'ホーム':'home',
'ホテル':'hotel',
'カフェ':'cafe',
'レストラン':'restaurant',
'ショップ':'shop',
'マーケット':'market',
'バンク':'bank',
'オフィス':'office',
'ファクトリー':'factory',
'カンパニー':'company',
'タワー':'tower',
'キャッスル':'castle',
'パレス':'palace',
'テンプル':'temple',
'チャーチ':'church',
'ブリッジ':'bridge',
'ステーション':'station',
'スクエア':'square',
'パーク':'park',
'ロボット':'robot',
'マシン':'machine',
'サイボーグ':'cyborg',
'アンドロイド':'android',
'エンジン':'engine',
'ライダー':'rider',
'ランナー':'runner',
'ウイング':'wing',
'クロー':'claw',
'ファング':'fang',

'フェイス':'face',
'ボディ':'body',
'マインド':'mind',
'ブレイン':'brain',
'ハッピー':'happy',
'スマイル':'smile',
'クレイジー':'crazy',
'ワイルド':'wild',
'クール':'cool',
'スイート':'sweet',
'ランキング':'ranking',
'ポケット':'pocket',
'チャンピオン':'champion',
'ウィナー':'winner',
'ウォーズ':'wars',
'バトル':'battle',

'ナイトメア':'nightmare',
'ファイアーマン':'fireman',
'ビューティ':'beauty',
'ファイアー':'fire',
'ファイア':'fire'}
LK=sorted(L,key=lambda k:-len(k))
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
def seg(run):
    # カタカナrunをgreedyに辞書分解。全部分解できれば英単語list、できなければNone
    i=0; out=[]
    while i<len(run):
        for k in LK:
            if run[i:i+len(k)]==k:
                if L[k]: out.append(L[k])
                i+=len(k); break
        else:
            return None
    return out
def main():
    prop=[]; unc=[]
    rows=[x for x in csv.reader(open(ROOT/'data'/'seeds'/'slug-kana-index.tsv',encoding='utf-8-sig'),delimiter='\t') if x[0]!='slug']
    for slug,title,tk,rom,oc,flag in rows:
        t=unicodedata.normalize('NFKC',str(title))
        runs=re.findall(r'[ァ-ヶ・ー]{3,}',t)   # カタカナrun(3字以上)
        if not runs: continue
        eng_runs={}
        any_en=False; any_unc=False
        for r in runs:
            r2=r.replace('・','').replace('ー','')
            words=seg(r.replace('・',''))
            if words is not None and words:
                eng_runs[r]='-'.join(words); any_en=True
            elif len(r)>=4:
                any_unc=True
        if any_en:
            # 提案slug = title全体romaji + 英runs置換は複雑→ proposalは「英runたち」を示す
            prop.append([slug,title,'; '.join(f'{r}→{e}' for r,e in eng_runs.items())])
        elif any_unc:
            unc.append([slug,title,'/'.join(r for r in runs if len(r)>=4)])
    for name,data,hdr in (('slug-loanword-proposal',prop,['slug','title','英化候補run']),('slug-loanword-uncertain',unc,['slug','title','カタカナrun(辞書外=要AI/web)'])):
        with open(ROOT/'data'/'seeds'/f'{name}.tsv','w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f,delimiter='\t'); w.writerow(hdr)
            for r in data: w.writerow(r)
    print(f'カタカナrun含むslug → 英化候補(辞書分解可) {len(prop)} / 辞書外カタカナ(要AI) {len(unc)}')
    print('-- 英化候補 サンプル --')
    for r in prop[:25]: print(f'  {r[0][:24]:24s}「{r[1][:14]}」 {r[2][:40]}')

if __name__=='__main__': main()
