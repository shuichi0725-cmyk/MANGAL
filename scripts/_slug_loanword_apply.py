#!/usr/bin/env python3
"""
slug蒸留適用: カタカナ外来語のヘボンslug部分→英語に置換しrename(alias付き)。
ヘボン形(ー=母音重ね)で slug substring を検出→英語へ。曖昧語(ナイト等)はOVERRIDEで個別判定。
dry-run/--apply。 backup+changelog+alias。
"""
import sys,csv,re,time,shutil,json
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
APPLY='--apply' in sys.argv
# katakana→english(曖昧語=ナイト/リバースは除外し個別OVERRIDE)
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
VOW={'ア':'a','イ':'i','ウ':'u','エ':'e','オ':'o','カ':'a','キ':'i','ク':'u','ケ':'e','コ':'o','タ':'a','ツ':'u','テ':'e','ト':'o'}
KMAP={'シャ':'sha','シュ':'shu','ショ':'sho','チャ':'cha','チュ':'chu','チョ':'cho','ジャ':'ja','ジュ':'ju','ジョ':'jo','ファ':'fa','フィ':'fi','フェ':'fe','フォ':'fo','ディ':'di','ティ':'ti','ウォ':'wo','ウィ':'wi','ヴァ':'va'}
S={'ア':'a','イ':'i','ウ':'u','エ':'e','オ':'o','カ':'ka','キ':'ki','ク':'ku','ケ':'ke','コ':'ko','サ':'sa','シ':'shi','ス':'su','セ':'se','ソ':'so','タ':'ta','チ':'chi','ツ':'tsu','テ':'te','ト':'to','ナ':'na','ニ':'ni','ヌ':'nu','ネ':'ne','ノ':'no','ハ':'ha','ヒ':'hi','フ':'fu','ヘ':'he','ホ':'ho','マ':'ma','ミ':'mi','ム':'mu','メ':'me','モ':'mo','ヤ':'ya','ユ':'yu','ヨ':'yo','ラ':'ra','リ':'ri','ル':'ru','レ':'re','ロ':'ro','ワ':'wa','ヲ':'o','ン':'n','ガ':'ga','ギ':'gi','グ':'gu','ゲ':'ge','ゴ':'go','ザ':'za','ジ':'ji','ズ':'zu','ゼ':'ze','ゾ':'zo','ダ':'da','ヂ':'ji','ヅ':'zu','デ':'de','ド':'do','バ':'ba','ビ':'bi','ブ':'bu','ベ':'be','ボ':'bo','パ':'pa','ピ':'pi','プ':'pu','ペ':'pe','ポ':'po','ァ':'a','ィ':'i','ゥ':'u','ェ':'e','ォ':'o','ヴ':'vu'}
def hebon(kana):
    out=[];i=0
    while i<len(kana):
        c2=kana[i:i+2]
        if c2 in KMAP: out.append(KMAP[c2]); i+=2; continue
        ch=kana[i]
        if ch=='ー': out.append(out[-1][-1] if out and out[-1] else ''); i+=1; continue
        if ch=='ッ': i+=1; continue
        if ch in S: out.append(S[ch])
        i+=1
    return ''.join(out)
HEB=sorted(((hebon(k),e,k) for k,e in L.items()),key=lambda x:-len(x[0]))
# 曖昧語OVERRIDE(私が題で判定。 slug→新slug直接指定)。未記載のナイト等は触らない
OVERRIDE={
 'love-ando-fuaiyaa':'love-and-fire','ore-no-maibooru':'ore-no-my-ball','osananajimi-wa-faiaaman':'osananajimi-wa-fireman',
 'seijo-wa-naitotachi-ni-midasareru':'seijo-wa-knighttachi-ni-midasareru','vampire-naito-memories':'vampire-knight-memories',
 'princess-kun-to-naito-san':'princess-kun-to-knight-san','okubyou-hime-to-dekiai-naito':'okubyou-hime-to-dekiai-knight',
 'naito-no-musume':'knight-no-musume','aruhi-naito-ni-attanara':'aruhi-knight-ni-attanara','kukkoro-naito':'kukkoro-knight',
 '100-mandoru-naito':'100-mandoru-night','mainichi-nekozanmai-dei-naito':'mainichi-nekozanmai-dei-night',
}
def main():
    rows=[x for x in csv.reader(open(ROOT/'data'/'seeds'/'slug-loanword-genuine.tsv',encoding='utf-8-sig'),delimiter='\t') if x[0]!='slug']
    existing=set(p.stem for p in (ROOT/'data'/'manga.v2').glob('*.yml'))
    plans=[]; amb=[]
    for slug,title,miss,flag in rows:
        if flag:  # ★曖昧(knight/night)は自動でなくOVERRIDE任せ
            amb.append((slug,title,miss)); continue
        new=slug
        for heb,eng,k in HEB:
            if heb and heb in new and eng:
                new=new.replace(heb,eng)
        new=re.sub(r'-+','-',new).strip('-')
        if new!=slug and new not in existing:
            plans.append((slug,title,new))
    for slug,new in OVERRIDE.items():
        if (ROOT/'data'/'manga.v2'/f'{slug}.yml').exists() and new not in existing:
            plans.append((slug,'(手動)',new))
    print(f'rename提案: {len(plans)} / 曖昧(ナイト等・保留) {len(amb)}')
    for s,t,n in plans[:30]: print(f'  {s[:30]:30s} → {n}')
    if not APPLY:
        print('\n(dry-run。 --applyで rename+alias)'); return
    bak=ROOT/'.cache'/f'slugheb-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    af=ROOT/'data'/'seeds'/'slug-overrides.yml'  # alias記録(旧→新)
    al={};
    if af.exists(): al=yaml.safe_load(af.read_text(encoding='utf-8')) or {}
    lf=(ROOT/'data'/'seeds'/'slug-loanword-changelog.jsonl').open('a',encoding='utf-8'); st=time.strftime('%Y-%m-%dT%H:%M:%S'); n=0
    seen=set(existing)
    for slug,title,new in plans:
        if new in seen: print('skip collision',slug,'→',new); continue
        seen.add(new)
        for base in ('data/manga.v2','.preview-data/manga'):
            fp=ROOT/base/f'{slug}.yml'
            if not fp.exists(): continue
            d=yaml.safe_load(fp.read_text(encoding='utf-8'))
            shutil.copy2(fp,bak/(base.replace('/','_')+'__'+slug+'.yml'))
            d['slug']=new
            (ROOT/base/f'{new}.yml').write_text(yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False),encoding='utf-8')
            fp.unlink()
        al[slug]=new; lf.write(json.dumps({'old':slug,'new':new,'at':st},ensure_ascii=False)+'\n'); n+=1
    af.write_text(yaml.dump(al,allow_unicode=True,sort_keys=True),encoding='utf-8'); lf.close()
    print(f'\nrename適用: {n}件(alias=slug-overrides.yml) backup={bak}')

if __name__=='__main__': main()
