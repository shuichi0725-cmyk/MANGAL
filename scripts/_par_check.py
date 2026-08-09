import io,json,glob,os,sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
truth={}
for f in glob.glob(os.path.join(ROOT,'.cache','voldesc','materials*.jsonl')):
    for line in io.open(f,encoding='utf-8'):
        d=json.loads(line)
        for v in d['vols']: truth[str(v['isbn'])]=(d['slug'],v['vol'])
ok=True
for name in sys.argv[1:]:
    p=os.path.join(ROOT,'.cache','voldesc','out',name+'.jsonl')
    if not os.path.exists(p): print('%-38s MISSING'%name); ok=False; continue
    n=0;bad=[];seen=set()
    for i,line in enumerate(io.open(p,encoding='utf-8'),1):
        line=line.strip()
        if not line: continue
        try: d=json.loads(line)
        except: bad.append('L%d JSON'%i); continue
        n+=1
        isbn=str(d.get('isbn13','')); desc=d.get('desc','')
        if len(isbn)!=13 or not isbn.isdigit(): bad.append('L%d isbn'%i)
        if len(desc)<60: bad.append('L%d %d字'%(i,len(desc)))
        if '\n' in desc: bad.append('L%d 改行'%i)
        if isbn in seen: bad.append('L%d 重複'%i)
        seen.add(isbn)
        t=truth.get(isbn)
        if not t: bad.append('L%d 材料外'%i)
        elif t!=(d.get('slug'),d.get('vol')): bad.append('L%d 不一致'%i)
    if bad: ok=False
    print('%-38s %3d行 %s'%(name,n,'OK' if not bad else 'NG '+str(bad[:4])))
print('ALL_OK' if ok else 'HAS_NG')
