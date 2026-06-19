#!/usr/bin/env python3
"""
取り違え是正 CREATE_NEW: 真の中身(別作品)を新規フォルダで保全(追加のみ・削除しない)。
ラベル作に入っている誤ISBN巻を、真の作品として新規作成。
身元= NDL(ISBN→題/ヨミ=kana/著者/年) + 楽天種(書影/発売日/出版社/あらすじ)。
genres/demographic= 楽天あらすじから暫定(genres_provisional)。
--limit N で試作。 既存slugは作らない(衝突回避)。
"""
import sys,csv,re,json,time,unicodedata,urllib.request,urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
LIMIT=None
for a in sys.argv:
    if a.startswith('--limit='): LIMIT=int(a.split('=')[1])
env={}
for ln in open(ROOT/'.env.local',encoding='utf-8'):
    if '=' in ln: k,v=ln.split('=',1); env[k.strip()]=v.strip()
def lnm(t): return t.split('}')[-1]
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
def stripvol(s):
    s=unicodedata.normalize('NFKC',str(s or '')); s=re.sub(r'[（(〈\[【].*?[）)〉\]】]','',s)
    s=re.sub(r'\s*(第)?\d+\s*(巻|集)?\s*$','',s); return s.strip()
# --- kana→romaji(簡易ヘボン) ---
KMAP={'キャ':'kya','キュ':'kyu','キョ':'kyo','シャ':'sha','シュ':'shu','ショ':'sho','チャ':'cha','チュ':'chu','チョ':'cho','ニャ':'nya','ニュ':'nyu','ニョ':'nyo','ヒャ':'hya','ヒュ':'hyu','ヒョ':'hyo','ミャ':'mya','ミュ':'myu','ミョ':'myo','リャ':'rya','リュ':'ryu','リョ':'ryo','ギャ':'gya','ギュ':'gyu','ギョ':'gyo','ジャ':'ja','ジュ':'ju','ジョ':'jo','ビャ':'bya','ビュ':'byu','ビョ':'byo','ピャ':'pya','ピュ':'pyu','ピョ':'pyo'}
S={'ア':'a','イ':'i','ウ':'u','エ':'e','オ':'o','カ':'ka','キ':'ki','ク':'ku','ケ':'ke','コ':'ko','サ':'sa','シ':'shi','ス':'su','セ':'se','ソ':'so','タ':'ta','チ':'chi','ツ':'tsu','テ':'te','ト':'to','ナ':'na','ニ':'ni','ヌ':'nu','ネ':'ne','ノ':'no','ハ':'ha','ヒ':'hi','フ':'fu','ヘ':'he','ホ':'ho','マ':'ma','ミ':'mi','ム':'mu','メ':'me','モ':'mo','ヤ':'ya','ユ':'yu','ヨ':'yo','ラ':'ra','リ':'ri','ル':'ru','レ':'re','ロ':'ro','ワ':'wa','ヲ':'o','ン':'n','ガ':'ga','ギ':'gi','グ':'gu','ゲ':'ge','ゴ':'go','ザ':'za','ジ':'ji','ズ':'zu','ゼ':'ze','ゾ':'zo','ダ':'da','ヂ':'ji','ヅ':'zu','デ':'de','ド':'do','バ':'ba','ビ':'bi','ブ':'bu','ベ':'be','ボ':'bo','パ':'pa','ピ':'pi','プ':'pu','ペ':'pe','ポ':'po','ァ':'a','ィ':'i','ゥ':'u','ェ':'e','ォ':'o','ー':'','・':' ','　':' ',' ':' '}
def romaji(kana):
    kana=hk(unicodedata.normalize('NFKC',str(kana or '')))
    out=[];i=0
    while i<len(kana):
        c2=kana[i:i+2]
        if c2 in KMAP: out.append(KMAP[c2]); i+=2; continue
        ch=kana[i]
        if ch=='ッ':
            nx=kana[i+1:i+2]; r=KMAP.get(kana[i+1:i+3]) or S.get(nx,'')
            if r: out.append(r[0])
            i+=1; continue
        if ch in S: out.append(S[ch])
        elif re.match(r'[a-zA-Z0-9]',ch): out.append(ch.lower())
        i+=1
    return re.sub(r'\s+',' ',''.join(out)).strip()
def slugify(kana,title):
    base=romaji(kana) or romaji(title)
    s=re.sub(r'[^a-z0-9 ]','',base.lower()); s=re.sub(r'\s+','-',s.strip())
    return s or 'work'
# --- genre 暫定(楽天あらすじ keyword) ---
GK=[('isekai',['異世界','転生','転移']),('romance',['恋','ラブ','結婚','婚約','溺愛']),('romcom',['ラブコメ']),('fantasy',['ファンタジー','魔法','魔王','勇者','ドラゴン']),('action',['バトル','戦い','格闘','アクション']),('sports',['スポーツ','部活','甲子園']),('baseball',['野球']),('soccer',['サッカー']),('horror',['ホラー','恐怖','怪談']),('mystery',['推理','謎','探偵','事件']),('comedy',['コメディ','ギャグ','笑']),('school',['学園','高校','生徒','クラス']),('historical',['歴史','戦国','幕末']),('sci-fi',['sf','宇宙','ロボット','未来']),('gourmet',['料理','グルメ','食']),('slice-of-life',['日常']),('drama',['ドラマ','人生','感動']),('bl',['ボーイズラブ','bl']),('supernatural',['妖怪','幽霊','超能力'])]
def guess_genres(cap):
    c=(cap or '').lower(); g=[]
    for key,kws in GK:
        if any(k.lower() in c for k in kws): g.append(key)
    return g[:3] or ['drama']
def demo_from(genres,cap):
    c=(cap or '')
    if 'bl' in genres or 'ボーイズラブ' in c: return 'josei'
    if any(x in genres for x in ('romance','romcom')): return 'shoujo'
    return 'seinen'

PUB=None
def pubkey(name):
    global PUB
    if PUB is None:
        PUB={}
        f=ROOT/'data'/'publishers.yml'
        if f.exists():
            y=yaml.safe_load(f.read_text(encoding='utf-8')) or {}
            for k,v in (y.items() if isinstance(y,dict) else []):
                PUB[k]=k
                for al in (v.get('aliases') or [] if isinstance(v,dict) else []): PUB[al]=k
    n=unicodedata.normalize('NFKC',str(name or ''))
    return PUB.get(n) or '(unknown)'

def ndl_isbn(isbn):
    u='https://ndlsearch.ndl.go.jp/api/sru?'+urllib.parse.urlencode({'operation':'searchRetrieve','recordSchema':'dcndl','recordPacking':'xml','maximumRecords':'1','query':f'isbn="{isbn}"'})
    for at in range(3):
        try: b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'MANGAL/0.1'}),timeout=25).read(); break
        except Exception:
            if at<2: time.sleep(2); continue
            return {}
    try: root=ET.fromstring(b)
    except: return {}
    res={}
    for rd in root.iter():
        if lnm(rd.tag)!='recordData': continue
        kids=list(rd); it=list(rd.iter()) if kids else (list(ET.fromstring(rd.text).iter()) if rd.text and '<' in rd.text else [])
        for el in it:
            k=lnm(el.tag); tx=(el.text or '').strip()
            if not tx: continue
            if k=='title' and 'title' not in res: res['title']=tx
            if k in ('titleTranscription',) and 'yomi' not in res: res['yomi']=tx
            if k=='creator' and 'creator' not in res: res['creator']=re.sub(r'\s*著$|\s*\d{4}-.*$','',tx)
            if k in ('date','issued') and 'date' not in res:
                m=re.search(r'(\d{4})',tx); res['date']=m.group(1) if m else None
        break
    return res

def main():
    # CREATE_NEW 対象 (計画表)
    targets=[]
    for x in csv.reader(open(ROOT/'data'/'seeds'/'torichigae-plan.tsv',encoding='utf-8-sig'),delimiter='\t'):
        if x[0]=='label_slug': continue
        if x[9].startswith('CREATE_NEW'): targets.append(x[0])
    if LIMIT: targets=targets[:LIMIT]
    print(f'CREATE_NEW 対象 {len(targets)}',flush=True)
    # 誤ISBN per label
    wrong=defaultdict(set); truen={}
    def aset(s):
        return set(re.sub(r'[（(].*?[）)]|[\s　・。.]','',hk(unicodedata.normalize('NFKC',x))).lower() for x in re.split(r'[;／/、,]',s) if x.strip())
    for x in csv.reader(open(ROOT/'data'/'seeds'/'isbn-source-table.tsv',encoding='utf-8-sig'),delimiter='\t'):
        if len(x)<7 or x[6]!='TORICHIGAE': continue
        if aset(x[3]) & aset(x[5]): continue
        wrong[x[1]].add(x[0]); truen[x[0]]=(x[4],x[5])
    # 楽天種 isbn->item
    rk={}
    for line in (ROOT/'.cache'/'rakuten-isbn.jsonl').open(encoding='utf-8'):
        try: o=json.loads(line); ib=to13(o.get('isbn') or (o.get('item') or {}).get('isbn'))
        except: continue
        if ib and o.get('item'): rk[ib]=o['item']
    existing=set(p.stem for p in (ROOT/'data'/'manga.v2').glob('*.yml'))
    made=[]
    for slug in targets:
        d=yaml.load((ROOT/'data'/'manga.v2'/f'{slug}.yml').read_text(encoding='utf-8'),Loader=L)
        # 誤ISBN巻を収集(number, isbn)
        vols=[]
        for e in (d.get('editions') or []):
            for v in (e.get('volumes') or []):
                ib=to13(v.get('isbn13'))
                if ib in wrong[slug]: vols.append((v.get('number') or 0, ib))
        if not vols: continue
        vols=sorted(set(vols))
        isbns=[ib for _,ib in vols]
        nd=ndl_isbn(isbns[0]); time.sleep(0.8)
        tt=stripvol(nd.get('title') or truen[isbns[0]][0]); ttk=stripvol(nd.get('yomi') or '')
        au=nd.get('creator') or truen[isbns[0]][1].split(';')[0]
        # 巻 build (楽天 cover/date)
        nv=[]; years=[]; pubs=set(); caps=[]
        for num,ib in vols:
            it=rk.get(ib,{}); u=it.get('largeImageUrl') or ''
            cov=(u.split('?')[0]+'?_ex=200x200') if u and 'noimage' not in u else None
            sd=it.get('salesDate') or ''; m=re.search(r'(\d{4})\D+(\d{1,2})\D+(\d{1,2})',sd) or re.search(r'(\d{4})',sd)
            rd=None
            if m and m.lastindex>=3: rd=f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
            elif m: rd=m.group(1); years.append(int(m.group(1)))
            if rd and len(rd)>=4: years.append(int(rd[:4]))
            if it.get('publisherName'): pubs.add(it['publisherName'])
            if it.get('itemCaption'): caps.append(it['itemCaption'])
            vv={'number':int(num) if num else len(nv)+1,'isbn13':ib}
            if cov: vv['cover_url']=cov
            if rd: vv['release_date']=rd
            nv.append(vv)
        if not ttk: ttk=tt   # ヨミ取れない時は題で代用(後段kana精緻化)
        nslug=slugify(ttk,tt)
        if nslug in existing or nslug in [m['slug'] for m in made]: nslug=f'{nslug}-{isbns[0][-4:]}'
        cap=' '.join(caps); genres=guess_genres(cap)
        ystart=min(years) if years else 2000
        pk=pubkey(sorted(pubs)[0]) if pubs else '(unknown)'
        work={'slug':nslug,'title':tt,'title_kana':hk(ttk),'title_romaji':romaji(ttk),
              'year_started':ystart,'year_ended':max(years) if years else None,
              'authors':[{'name':au,'role':'writer_artist'}],'original_authors':[],'credits':[],
              'publisher':pk,'publishers':[pk] if pk!='(unknown)' else [],
              'demographic':demo_from(genres,cap),'genres':genres,'genres_provisional':True,
              'synopsis':'','status':'completed',
              'editions':[{'type':'standard','label':'通常版','publisher':pk,'volumes':nv}],
              'note_origin':f'取り違え救済: {slug} に誤格納されていた {au}「{tt}」を保全(CREATE_NEW)'}
        made.append(work)
        print(f'  {slug[:20]:20s} → 新作 {nslug[:24]:24s}「{tt[:12]}」by {au[:10]} {len(nv)}巻 g={genres}',flush=True)
    # 書き出し
    for w in made:
        y=yaml.dump(w,allow_unicode=True,sort_keys=False,default_flow_style=False)
        for base in ('data/manga.v2','.preview-data/manga'):
            (ROOT/base/f"{w['slug']}.yml").write_text(y,encoding='utf-8')
    with (ROOT/'data'/'seeds'/'torichigae-created.jsonl').open('a',encoding='utf-8') as f:
        st=time.strftime('%Y-%m-%dT%H:%M:%S')
        for w in made: f.write(json.dumps({'new_slug':w['slug'],'title':w['title'],'author':w['authors'][0]['name'],'vols':len(w['editions'][0]['volumes']),'at':st},ensure_ascii=False)+'\n')
    print(f'\n作成 {len(made)} 新作 (data/manga.v2 + preview)')

if __name__=='__main__': main()
