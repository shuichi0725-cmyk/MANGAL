#!/usr/bin/env python3
"""NEEDS_READING 66のうち確実な A+B の読みを手動生成・適用。C(プロジェクトX)/D(アンソロ)はflag。"""
import yaml,os,time,shutil,json
# slug -> 正しいtitle_kana(標準読み。当て字でないもの)。titleも直す場合は (kana, title)
COR={
 'fueaueino':'フェアウエイノサムライ','fushidarana':'フシダラナキャクホン',
 'iyorimosetsunakute':'オモイデヨリモセツナクテ','kanarinokanata':'ハルカナリユメノカナタ',
 'raiano':'ライアーウソノハコニワ','seishun-sankaku':'セイシュントライアングル',
 'shinderera':'シンデレラトッキュウ','shirubesutanokara':'シルベスターノホシカラ',
 'sutoritofuaita2v':'ストリートファイターツーブイレツデン',
 'tonotatakai':'トヨトミヒデヨシトテンカトウイツノタタカイ',
 'yorozuya':'ヨロズヤカギョウタダイマセイギョウチュウ','doridorikyasusan':'ドリドリキャスコサン',
 'magajin':'ショウネンマガジンダイゼンシュウフッコクバン','magajin-1888':'ショウネンマガジンダイゼンシュウフッコクバン',
 'makinonansensu':'ササキマキノナンセンスセカイ','manga':'マンガサンゴクシ',
 'nodarutanyan':'カゼノダルタニヤン','niikyonshikun':'ニーハオキョンシークン',
 'r-1064454':'アリサ','r-1782014':'タケミヤケイコサクヒンシュウ','r-1782038':'タケミヤケイコサクヒンシュウ',
 'r-2027084':'サツイノソコ','r-3611193':'アオノオトコ','r-4443774':'ゼンセントジュウゴ',
 'r-4952699':'ゼツリンキョウジュノジッケンタイ','r-6172615':'フランスマドダヨリ','r-6172622':'コサアジュ',
 'r-6300877':'サンゴクシソウソウデン','r-6728036':'シンレイジョウモノガタリ','r-8165936':'ケモノミチ',
 'r-0054222':'クビライ','r-6027884':'ヨウネンキアベセイメイイブンミメイノケモノ',
 'r-5910498':'カイキダイサクセンガクエンナヌシ','garu':'テンマノソラ','buru':'シケイシッコウニンブル',
 'r-1086685':'タンゲサゼンピストルヲアタマニノセタヒトビト','r-3966128':'マインディランド',
 'sraifu':'ノゾムズライフ','supesharu':'ガロウデンセツスペシャル',
}
# title も直す(corruption)
TFIX={'r-8301074':('ヒノコウフン','日の興奮')}
bak='.cache/kanacor-bak-'+time.strftime('%Y%m%d-%H%M%S'); os.makedirs(bak,exist_ok=True)
lf=open('data/seeds/kana-fix-changelog.jsonl','a',encoding='utf-8'); st=time.strftime('%Y-%m-%dT%H:%M:%S')
n=0
def apply(slug,kana,title=None):
    global n
    done=False
    for base in ('data/manga.v2','.preview-data/manga'):
        fp=f'{base}/{slug}.yml'
        if not os.path.exists(fp): continue
        d=yaml.safe_load(open(fp,encoding='utf-8'))
        shutil.copy2(fp,bak+'/'+base.replace('/','_')+'__'+slug+'.yml')
        old=d.get('title_kana')
        d['title_kana']=kana
        if title: d['title']=title
        open(fp,'w',encoding='utf-8').write(yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False))
        if base=='data/manga.v2':
            lf.write(json.dumps({'slug':slug,'old_kana':old,'new_kana':kana,'title_fix':title,'at':st},ensure_ascii=False)+'\n'); done=True
    if done: n+=1
for slug,kana in COR.items(): apply(slug,kana)
for slug,(kana,title) in TFIX.items(): apply(slug,kana,title)
lf.close()
print(f'適用: {n}作のtitle_kana是正(手動読み)。 backup={bak}')
print('flag(構造問題・別途): プロジェクトX16(episode≠series=統合案件) / ribonmanga・sasayananae(アンソロentry) / basara(作品集) / sayonara(岸壁vs岩壁要確認)')
