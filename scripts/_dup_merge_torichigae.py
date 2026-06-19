#!/usr/bin/env python3
"""取り違え新作のdup是正: 5件が既存作とdup→欠ISBNを既存にmerge+dup削除。"""
import yaml,os,json,time,shutil
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
pairs=[('shutokimegurii','kootaroo-makaritooru'),('r-2127345','moshikashite-vamp'),
       ('kingu-obu-hasura','king-of-the-hustler'),('buraitono','bright-no-yuuutsu'),('sajino','kita-no-fuuin')]
bak='.cache/dup-merge-bak-'+time.strftime('%Y%m%d-%H%M%S'); os.makedirs(bak,exist_ok=True)
log=open('data/seeds/torichigae-dupmerge-changelog.jsonl','a',encoding='utf-8'); st=time.strftime('%Y-%m-%dT%H:%M:%S')
for newslug,exist in pairs:
    nf='data/manga.v2/'+newslug+'.yml'; ef='data/manga.v2/'+exist+'.yml'
    if not os.path.exists(nf) or not os.path.exists(ef):
        print('skip',newslug,exist,'(無)'); continue
    nd=yaml.safe_load(open(nf,encoding='utf-8')); ed=yaml.safe_load(open(ef,encoding='utf-8'))
    exist_isbns={to13(v.get('isbn13')) for e in ed.get('editions',[]) for v in e.get('volumes',[]) if v.get('isbn13')}
    newvols=[v for e in nd.get('editions',[]) for v in e.get('volumes',[])]
    added=[]
    for v in newvols:
        ib=to13(v.get('isbn13'))
        if ib and ib not in exist_isbns:
            tgt=next((e for e in ed.get('editions',[]) if e.get('type')=='standard'), ed['editions'][0])
            tgt['volumes'].append(v); added.append(ib)
    for base in ('data/manga.v2','.preview-data/manga'):
        ef2=base+'/'+exist+'.yml'; nf2=base+'/'+newslug+'.yml'
        if os.path.exists(ef2):
            shutil.copy2(ef2,bak+'/'+base.replace('/','_')+'__'+exist+'.yml')
            if added:
                open(ef2,'w',encoding='utf-8').write(yaml.dump(ed,allow_unicode=True,sort_keys=False,default_flow_style=False))
        if os.path.exists(nf2):
            shutil.copy2(nf2,bak+'/'+base.replace('/','_')+'__'+newslug+'.yml'); os.remove(nf2)
    log.write(json.dumps({'removed_dup':newslug,'merged_into':exist,'added_isbns':added,'at':st},ensure_ascii=False)+'\n')
    print('  '+newslug+' → '+exist+' (追加ISBN '+str(len(added))+') dup削除')
log.close(); print('完了 backup='+bak)
