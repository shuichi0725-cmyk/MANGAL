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
L={
'プロジェクト':'project','モンスター':'monster','ドラゴン':'dragon','エンジェル':'angel','プリンセス':'princess',
'マイ':'my','ボール':'ball','ポケット':'pocket','ハート':'heart','ラブ':'love','スター':'star','ワールド':'world',
'キング':'king','クイーン':'queen','ナイト':'knight','ソード':'sword','マスター':'master','ヒーロー':'hero',
'ファイト':'fight','ファイター':'fighter','バトル':'battle','ウォーズ':'wars','ウォー':'war','ゲーム':'game',
'スクール':'school','クラス':'class','ガール':'girl','ガールズ':'girls','ボーイ':'boy','ボーイズ':'boys',
'ベイビー':'baby','ベビー':'baby','エンジン':'engine','カー':'car','レース':'race','スピード':'speed',
'パワー':'power','ファイヤー':'fire','ファイア':'fire','アイス':'ice','ウォーター':'water','ウインド':'wind',
'ライト':'light','ダーク':'dark','ブラック':'black','ホワイト':'white','レッド':'red','ブルー':'blue','グリーン':'green',
'シティ':'city','タウン':'town','ロード':'road','ストリート':'street','ハウス':'house','ホーム':'home',
'スクエア':'square','パーク':'park','スカイ':'sky','ムーン':'moon','サン':'sun','ナイトメア':'nightmare',
'ドリーム':'dream','メモリー':'memory','ストーリー':'story','レジェンド':'legend','ヒストリー':'history',
'ライフ':'life','デス':'death','ソウル':'soul','スピリット':'spirit','エンド':'end','スタート':'start',
'ファースト':'first','ラスト':'last','ネクスト':'next','ニュー':'new','オールド':'old','ビッグ':'big','スモール':'small',
'ハイ':'high','ロー':'low','スーパー':'super','ウルトラ':'ultra','メガ':'mega','ハイパー':'hyper','マックス':'max',
'チーム':'team','クラブ':'club','リーグ':'league','カップ':'cup','チャンピオン':'champion','ウィナー':'winner',
'スポーツ':'sports','ゴール':'goal','シュート':'shoot','パス':'pass','キック':'kick','ラン':'run',
'マジック':'magic','マジカル':'magical','ファンタジー':'fantasy','アドベンチャー':'adventure','ミステリー':'mystery',
'ホラー':'horror','コメディ':'comedy','ロマンス':'romance','アクション':'action','サスペンス':'suspense',
'エンジェルス':'angels','デビル':'devil','デーモン':'demon','ゴッド':'god','ゴースト':'ghost','ヴァンパイア':'vampire',
'ロボット':'robot','マシン':'machine','サイボーグ':'cyborg','アンドロイド':'android','スペース':'space','ギャラクシー':'galaxy',
'プラネット':'planet','アース':'earth','ユニバース':'universe','コスモス':'cosmos','ステーション':'station',
'カラー':'color','カラーズ':'colors','レインボー':'rainbow','シャイニー':'shiny','クリスタル':'crystal','ダイヤモンド':'diamond',
'ゴールド':'gold','シルバー':'silver','プラチナ':'platinum','メタル':'metal','スチール':'steel','アイアン':'iron',
'ドクター':'doctor','ナース':'nurse','ティーチャー':'teacher','ポリス':'police','デカ':'','スパイ':'spy','エージェント':'agent',
'シークレット':'secret','ミッション':'mission','コード':'code','ナンバー':'number','カウント':'count',
'ハッピー':'happy','スマイル':'smile','テラー':'terror','クライ':'cry','ティアー':'tear','エモーション':'emotion',
'キス':'kiss','ハグ':'hug','ウェディング':'wedding','ハネムーン':'honeymoon','カップル':'couple','ペア':'pair',
'リバース':'rebirth','チェンジ':'change','リライト':'rewrite','リセット':'reset','リターン':'return','カムバック':'comeback',
}
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
