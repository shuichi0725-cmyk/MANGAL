# 並列巻説明: 材料の型を測って作品ごと(大型は分割)にジョブファイルを作る
import io,json,os,sys,statistics
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC=os.path.join(ROOT,'.cache','voldesc','materials.jsonl')
PAR=os.path.join(ROOT,'.cache','voldesc','par')
os.makedirs(PAR,exist_ok=True)
CHUNK=int(sys.argv[1]) if len(sys.argv)>1 else 25
jobs=[]
for line in io.open(SRC,encoding='utf-8'):
    d=json.loads(line)
    vols=sorted(d['vols'],key=lambda v:v['vol'])
    if not vols: continue
    caps=[(v.get('caption') or '').strip() for v in vols]
    uniq=len(set(caps)); avg=statistics.mean(len(c) for c in caps)
    ratio=uniq/len(caps)
    if ratio<0.5 or avg<55:
        print('SKIP %-34s vols=%3d 相異%3d(%.0f%%) 平均%d字' % (d['slug'],len(caps),uniq,ratio*100,avg)); continue
    kind='long' if avg>=280 else ('mid' if avg>=140 else 'short')
    n=len(vols); nsplit=max(1,(n+CHUNK-1)//CHUNK); size=(n+nsplit-1)//nsplit
    for i in range(nsplit):
        part=vols[i*size:(i+1)*size]
        if not part: continue
        name=d['slug'] if nsplit==1 else '%s-p%d'%(d['slug'],i+1)
        p=os.path.join(PAR,name+'.txt')
        with io.open(p,'w',encoding='utf-8') as f:
            f.write('SERIES slug=%s  title=%s\n'%(d['slug'],d['title']))
            for v in part:
                f.write('--- vol %s  isbn13 %s\n%s\n'%(v['vol'],v['isbn'],(v.get('caption') or '').replace('\n',' / ')))
        jobs.append((name,len(part),kind,int(avg)))
for n,c,k,a in jobs: print('JOB  %-34s %3d巻  型=%-5s 平均%d字'%(n,c,k,a))
print('合計 %d巻 / %dジョブ'%(sum(c for _,c,_,_ in jobs),len(jobs)))
