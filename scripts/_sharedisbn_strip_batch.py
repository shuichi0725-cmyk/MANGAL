#!/usr/bin/env python3
"""
A 段1拡大 (汎用strip): slug→[誤ISBN] map を読み、誤著者の巻を除去し本人巻のみ残しdate順renumber。
map = .cache/_strip_batch_map.json。reconcile(現yml+種1/楽天著者照合)+異体字正規化チェックで
「別著者の単巻混入(wrong==1)」と確定した分のみ対象。dry-run/--apply。backup+changelog+可逆。
"""
import sys, time, shutil, json as J
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT = Path(__file__).resolve().parent.parent
import yaml
APPLY = '--apply' in sys.argv
BASES = ('data/manga.v2', '.preview-data/manga')
STRIP = J.load(open(ROOT/'.cache/_strip_batch_map.json', encoding='utf-8'))

def to13(s):
    s = str(s or '').replace('-', '').strip()
    return s if len(s) == 13 and s.isdigit() else ''

def main():
    print(f'=== strip batch ({len(STRIP)}件) ' + ('APPLY' if APPLY else 'DRY-RUN') + ' ===')
    plans = {}
    for sl, bad in STRIP.items():
        bad = set(bad)
        fp = ROOT/'data/manga.v2'/f'{sl}.yml'
        if not fp.exists(): print('  ⚠no yml', sl); continue
        d = yaml.safe_load(fp.read_text(encoding='utf-8'))
        removed = []
        for e in (d.get('editions') or []):
            surv = []
            for v in (e.get('volumes') or []):
                (removed if to13(v.get('isbn13')) in bad else surv).append(v)
            e['volumes'] = surv
        flat = [v for e in d.get('editions', []) for v in e.get('volumes', [])]
        if not flat:
            print(f'  ⚠ {sl} 残ゼロ skip'); continue
        for i, v in enumerate(sorted(flat, key=lambda v: str(v.get('release_date') or '9999')), 1):
            v['number'] = i
        d['editions'] = [e for e in d.get('editions', []) if e.get('volumes')]
        plans[sl] = (d, [to13(v.get('isbn13')) for v in removed], len(flat))
    for sl, (d, rem, keep) in sorted(plans.items()):
        print(f'  {sl}: 除去{rem} → 残{keep}巻')
    if not APPLY:
        print(f'\n適用可能 {len(plans)}件 (dry-run。 --apply)'); return
    bak = ROOT/'.cache'/f'sharedisbn-strip-batch-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True, exist_ok=True)
    lf = (ROOT/'data/seeds/sharedisbn-step1-changelog.jsonl').open('a', encoding='utf-8')
    st = time.strftime('%Y-%m-%dT%H:%M:%S')
    for sl, (d, rem, keep) in plans.items():
        for base in BASES:
            fp = ROOT/base/f'{sl}.yml'
            if base == 'data/manga.v2' or fp.exists():
                if fp.exists(): shutil.copy2(fp, bak/(base.replace('/', '_')+'__'+sl+'.yml'))
                fp.write_text(yaml.dump(d, allow_unicode=True, sort_keys=False), encoding='utf-8')
        lf.write(J.dumps({'slug': sl, 'op': 'strip_wrong_author_isbn', 'removed': sorted(set(STRIP[sl])), 'at': st}, ensure_ascii=False)+'\n')
    lf.close()
    print(f'\n適用 {len(plans)}件。 backup={bak}')

if __name__ == '__main__': main()
