import json,yaml,collections,sys
SP=sys.argv[1]
d=json.load(open('data/manga-list-index.json',encoding='utf-8'))
f=d['f'];rows=d['d'];ix={k:i for i,k in enumerate(f)}
gn={k:v['name'] for k,v in yaml.safe_load(open('data/genres.yml',encoding='utf-8')).items()}
DN={'shounen':'少年','shoujo':'少女','seinen':'青年','josei':'女性','kodomo':'子ども'}
C=lambda:{'genre':collections.Counter(),'theme':collections.Counter(),'demo':collections.Counter()}
allc=C();dec=collections.defaultdict(C);dtot=collections.Counter()
for r in rows:
    y=r[ix['year_started']];de=str(y//10*10) if isinstance(y,int) and 1970<=y<=2029 else None
    if de: dtot[de]+=1
    for tgt in ([allc,dec[de]] if de else [allc]):
        for g in (r[ix['genres']] or []): tgt['genre'][gn.get(g,g)]+=1
        for t in (r[ix['themes']] or []): tgt['theme'][t]+=1
        if r[ix['demographic']]: tgt['demo'][DN[r[ix['demographic']]]]+=1
cut=lambda c:{'genre':c['genre'].most_common(),'theme':c['theme'].most_common(30),'demo':c['demo'].most_common()}
data={'total':len(rows),'ntheme':len(allc['theme']),'all':cut(allc),'dec':{k:cut(v) for k,v in sorted(dec.items())},'dtot':dict(sorted(dtot.items()))}
open(SP+'/graph-iro.html','w',encoding='utf-8').write(open(SP+'/tpl-iro7.html',encoding='utf-8').read().replace('/*DATA*/',json.dumps(data,ensure_ascii=False)))
for k,v in data['dec'].items(): print(k,v['theme'][:4],v['demo'][:3])
