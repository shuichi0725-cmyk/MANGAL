#!/usr/bin/env python3
"""
A 段1 (最安全 strip): 誤著者の巻ISBN(=種1/楽天で別著者と確認)を各ページから除去し、
本人の正巻のみ残して date順 renumber。re-point/番号水増しの危険なし。dry-run/--apply。
全件 台帳(operations.jsonl)で既処理でないことを確認済(2026-06-20)、現ymlで真owner検証済。
backup + changelog(sharedisbn-step1) + 可逆。種2不変。
"""
import sys, time, shutil, json as J, re
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT = Path(__file__).resolve().parent.parent
import yaml
APPLY = '--apply' in sys.argv
BASES = ('data/manga.v2', '.preview-data/manga')

# slug -> 除去する誤ISBN集合 (種1/楽天で別著者と確認済)
STRIP = {
 'eden-sakurazawa-2014': {'9784047139404'},                       # 岡田俊平/廣瀬雄のエデン
 # reset=保留(高橋ユキ標準+山本まゆり文庫の2著者混在+enrich疑義。段1の安全枠でない)
 'snow': {'9784088497051'},                                        # 藤谷コマキのスノウ
 'stand-up': {'9784056013740'},                                    # 白虎丸のSTAND UP!2
 'zero-matsumoto': {'9784344834347'},                              # 冬目景のZERO
}

def to13(s):
    s = str(s or '').replace('-', '').strip()
    return s if len(s) == 13 and s.isdigit() else ''

def main():
    print('=== A段1 strip ' + ('APPLY' if APPLY else 'DRY-RUN') + ' ===')
    plans = {}
    for sl, bad in STRIP.items():
        fp = ROOT/'data/manga.v2'/f'{sl}.yml'
        d = yaml.safe_load(fp.read_text(encoding='utf-8'))
        kept, removed = [], []
        for e in (d.get('editions') or []):
            survivors = []
            for v in (e.get('volumes') or []):
                ib = to13(v.get('isbn13'))
                (removed if ib in bad else survivors).append(v)
            e['volumes'] = survivors
            kept += survivors
        # date順 renumber (survivors)
        def dk(v): return str(v.get('release_date') or '9999')
        flat = [v for e in d.get('editions', []) for v in e.get('volumes', [])]
        for i, v in enumerate(sorted(flat, key=dk), 1):
            v['number'] = i
        # 空edition除去
        d['editions'] = [e for e in d.get('editions', []) if e.get('volumes')]
        au = [a.get('name') for a in (d.get('authors') or [])]
        print(f"  {sl}({'/'.join(au)}): 除去{[to13(v.get('isbn13')) for v in removed]} → 残{len(kept)}巻 {[to13(v.get('isbn13')) for v in kept]}")
        if not kept:
            print(f'    ⚠ {sl} 残巻ゼロ=異常、skip'); continue
        plans[sl] = d

    if not APPLY:
        print('\n(dry-run。 --applyで適用)'); return
    bak = ROOT/'.cache'/f'sharedisbn-step1-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True, exist_ok=True)
    lf = (ROOT/'data/seeds/sharedisbn-step1-changelog.jsonl').open('a', encoding='utf-8')
    st = time.strftime('%Y-%m-%dT%H:%M:%S')
    for sl, d in plans.items():
        for base in BASES:
            fp = ROOT/base/f'{sl}.yml'
            if base == 'data/manga.v2' or fp.exists():
                if fp.exists(): shutil.copy2(fp, bak/(base.replace('/', '_')+'__'+sl+'.yml'))
                fp.write_text(yaml.dump(d, allow_unicode=True, sort_keys=False), encoding='utf-8')
        lf.write(J.dumps({'slug': sl, 'op': 'strip_wrong_author_isbn', 'removed': sorted(STRIP[sl]), 'at': st}, ensure_ascii=False)+'\n')
        print('  applied', sl)
    lf.close()
    print(f'\n適用 {len(plans)}件。 backup={bak}')

if __name__ == '__main__': main()
