#!/usr/bin/env python3
"""両slug蒸留スクリプトの L 辞書を包括版に差し替え(曖昧語ナイト/リバースは除外)。"""
import re
D={
'love':'ラブ','heart':'ハート','kiss':'キス','angel':'エンジェル','devil':'デビル','demon':'デーモン','god':'ゴッド','ghost':'ゴースト',
'vampire':'ヴァンパイア','witch':'ウィッチ','wizard':'ウィザード','fairy':'フェアリー','mermaid':'マーメイド','elf':'エルフ',
'dragon':'ドラゴン','monster':'モンスター','beast':'ビースト','wolf':'ウルフ','tiger':'タイガー','lion':'ライオン','bear':'ベアー',
'eagle':'イーグル','shark':'シャーク','snake':'スネーク','cat':'キャット','dog':'ドッグ','bird':'バード','fish':'フィッシュ',
'rose':'ローズ','flower':'フラワー','tree':'ツリー','forest':'フォレスト','garden':'ガーデン','star':'スター','moon':'ムーン',
'sun':'サン','sky':'スカイ','ocean':'オーシャン','river':'リバー','mountain':'マウンテン','island':'アイランド',
'world':'ワールド','earth':'アース','space':'スペース','galaxy':'ギャラクシー','planet':'プラネット','universe':'ユニバース','cosmos':'コスモス',
'king':'キング','queen':'クイーン','prince':'プリンス','princess':'プリンセス','lord':'ロード','lady':'レディ','master':'マスター',
'hero':'ヒーロー','heroine':'ヒロイン','fighter':'ファイター','warrior':'ウォリアー','soldier':'ソルジャー','captain':'キャプテン',
'doctor':'ドクター','nurse':'ナース','police':'ポリス','spy':'スパイ','agent':'エージェント',
'killer':'キラー','hunter':'ハンター','slayer':'スレイヤー','guardian':'ガーディアン','saber':'セイバー','sword':'ソード',
'magic':'マジック','magical':'マジカル','fantasy':'ファンタジー','adventure':'アドベンチャー','mystery':'ミステリー','horror':'ホラー',
'comedy':'コメディ','romance':'ロマンス','action':'アクション','suspense':'サスペンス','story':'ストーリー','legend':'レジェンド',
'history':'ヒストリー','memory':'メモリー','dream':'ドリーム','soul':'ソウル','spirit':'スピリット','life':'ライフ','death':'デス',
'blood':'ブラッド','bone':'ボーン','skull':'スカル','fire':'ファイヤー','ice':'アイス','water':'ウォーター','wind':'ウインド','thunder':'サンダー',
'light':'ライト','dark':'ダーク','shadow':'シャドウ','mirror':'ミラー','crystal':'クリスタル','diamond':'ダイヤモンド','gold':'ゴールド','silver':'シルバー',
'metal':'メタル','iron':'アイアン','steel':'スチール','rainbow':'レインボー','color':'カラー','colors':'カラーズ','white':'ホワイト','black':'ブラック',
'red':'レッド','blue':'ブルー','green':'グリーン','yellow':'イエロー','purple':'パープル','pink':'ピンク','orange':'オレンジ',
'school':'スクール','class':'クラス','club':'クラブ','team':'チーム','league':'リーグ','game':'ゲーム','sports':'スポーツ','ball':'ボール','goal':'ゴール',
'race':'レース','speed':'スピード','power':'パワー','super':'スーパー','ultra':'ウルトラ','mega':'メガ','hyper':'ハイパー',
'baby':'ベイビー','girl':'ガール','girls':'ガールズ','boy':'ボーイ','boys':'ボーイズ','man':'マン','woman':'ウーマン','sister':'シスター','brother':'ブラザー',
'mother':'マザー','father':'ファーザー','family':'ファミリー','children':'チルドレン','twins':'ツインズ','friend':'フレンド','friends':'フレンズ',
'partner':'パートナー','rival':'ライバル','enemy':'エネミー','lovers':'ラヴァーズ','couple':'カップル','wedding':'ウェディング','honeymoon':'ハネムーン',
'project':'プロジェクト','mission':'ミッション','code':'コード','number':'ナンバー','secret':'シークレット','danger':'デンジャー','trouble':'トラブル',
'crisis':'クライシス','chance':'チャンス','miracle':'ミラクル','wonder':'ワンダー','paradise':'パラダイス','heaven':'ヘブン','hell':'ヘル',
'city':'シティ','town':'タウン','road':'ロード','street':'ストリート','house':'ハウス','home':'ホーム','hotel':'ホテル','cafe':'カフェ',
'restaurant':'レストラン','shop':'ショップ','market':'マーケット','bank':'バンク','office':'オフィス','factory':'ファクトリー','company':'カンパニー',
'tower':'タワー','castle':'キャッスル','palace':'パレス','temple':'テンプル','church':'チャーチ','bridge':'ブリッジ','station':'ステーション','square':'スクエア','park':'パーク',
'robot':'ロボット','machine':'マシン','cyborg':'サイボーグ','android':'アンドロイド','engine':'エンジン','rider':'ライダー','runner':'ランナー',
'wing':'ウイング','claw':'クロー','fang':'ファング','eye':'アイ','face':'フェイス','body':'ボディ','mind':'マインド','brain':'ブレイン',
'happy':'ハッピー','smile':'スマイル','crazy':'クレイジー','wild':'ワイルド','cool':'クール','sweet':'スイート','ranking':'ランキング',
'pocket':'ポケット','champion':'チャンピオン','winner':'ウィナー','wars':'ウォーズ','battle':'バトル','and':'アンド','nightmare':'ナイトメア',
'fireman':'ファイアーマン','beauty':'ビューティ',
}
L={v:k for k,v in D.items()}
L['ファイアー']='fire'; L['ファイア']='fire'; L['ファイヤー']='fire'; L['ファイアーマン']='fireman'
lit=',\n'.join("'"+k+"':'"+v+"'" for k,v in L.items())
newL='L={'+lit+'}'
for p in ('scripts/_slug_loanword_investigate.py','scripts/_slug_loanword_apply.py'):
    s=open(p,encoding='utf-8').read()
    s2=re.sub(r'\nL=\{[^}]*\}', '\n'+newL, s, count=1)
    open(p,'w',encoding='utf-8').write(s2)
    print(p, 'replaced' if s2!=s else 'NOCHANGE', '辞書語数', len(L))
