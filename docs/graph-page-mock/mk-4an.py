import json,yaml,collections,sys
SP=sys.argv[1]
d=json.load(open('data/manga-list-index.json',encoding='utf-8'))
f=d['f'];rows=d['d'];ix={k:i for i,k in enumerate(f)}
G=yaml.safe_load(open('data/genres.yml',encoding='utf-8'))
gn={k:v['name'] for k,v in G.items()}
gc=collections.Counter();tc=collections.Counter()
dec=collections.defaultdict(collections.Counter);dmg=collections.defaultdict(collections.Counter);dm=collections.Counter();dtot=collections.Counter()
for r in rows:
    y=r[ix['year_started']];de=(y//10*10) if isinstance(y,int) and 1970<=y<=2029 else None
    if de: dtot[de]+=1
    dem=r[ix['demographic']]
    if dem: dm[dem]+=1
    for g in (r[ix['genres']] or []):
        n=gn.get(g,g);gc[n]+=1
        if de: dec[de][n]+=1
        if dem: dmg[dem][n]+=1
    for t in (r[ix['themes']] or []): tc[t]+=1
DN={'shounen':'少年','shoujo':'少女','seinen':'青年','josei':'女性','kodomo':'子ども'}
data={'total':len(rows),'genre':gc.most_common(),'theme':tc.most_common(30),'ntheme':len(tc),
 'demo':[[DN[k],v] for k,v in dm.most_common()],
 'decade':[[f'{k}年代',v] for k,v in sorted(dtot.items())],
 'dec':{str(k):dict(v) for k,v in sorted(dec.items())},'dtot':{str(k):v for k,v in sorted(dtot.items())},
 'dmg':{DN[k]:dict(v) for k,v in dmg.items()},'dmtot':{DN[k]:v for k,v in dm.items()}}
html=open(SP+'/tpl-4an.html',encoding='utf-8').read().replace('/*DATA*/',json.dumps(data,ensure_ascii=False))
open(SP+'/graph-mihon.html','w',encoding='utf-8').write(html)
print(data['dtot'],data['dmtot']); print({k:sorted(v.items(),key=lambda x:-x[1])[:3] for k,v in data['dec'].items()})
