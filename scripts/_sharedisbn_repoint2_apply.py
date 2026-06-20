#!/usr/bin/env python3
"""
A REPOINT(複数巻対応): 別著者の作品を抱えるページを、NDL著者照会で確定した自前ISBN群へ差替。
汚染enrich全clear、identity(題/著者/kana/romaji)保持。dry-run/--apply。可逆。
"""
import sys, time, shutil, json as J
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT = Path(__file__).resolve().parent.parent
import yaml
APPLY = '--apply' in sys.argv
BASES = ('data/manga.v2', '.preview-data/manga')
CLEAR = ['anilist_id', 'synopsis', 'genres_anilist', 'tags', 'catch', 'popularity', 'adult_us',
         'alternative_titles', 'wikidata_qid', 'synonyms', 'genres', 'genres_provisional',
         'demographic', 'magazine', 'subtitle', 'subtitle_kana', 'year_ended', 'original_authors']
REPOINT = {
 'to-heart-2':           dict(pk='ascii-media-works', pd='メディアワークス', year=2005,
                              vols=[(1, '9784840227742', '2005-11'), (2, '9784840235334', '2006-08'), (3, '9784840239011', '2007')]),
 'engage-watanabe-2009': dict(pk='kodansha', pd='講談社', year=2009,
                              vols=[(1, '9784063494228', '2009'), (2, '9784063494327', '2009')]),
 'nein':                 dict(pk='kadokawa', pd='KADOKAWA', year=2016,
                              vols=[(1, '9784041050514', '2016')]),
}
def main():
    print('=== REPOINT2 ' + ('APPLY' if APPLY else 'DRY-RUN') + ' ===')
    plans = {}
    for sl, r in REPOINT.items():
        fp = ROOT/'data/manga.v2'/f'{sl}.yml'
        d = yaml.safe_load(fp.read_text(encoding='utf-8'))
        old = [v.get('isbn13') for e in (d.get('editions') or []) for v in (e.get('volumes') or [])]
        au = [a.get('name') for a in (d.get('authors') or [])]
        print(f"  {sl}({'/'.join(au)}): 誤{old} → 自前{[v[1] for v in r['vols']]} {r['pd']}{r['year']}")
        for k in CLEAR: d.pop(k, None)
        d['publisher'] = r['pk']; d['publishers'] = [r['pk']]; d['year_started'] = r['year']; d['status'] = 'completed'
        d['editions'] = [{'type': 'standard', 'label': '通常版', 'publisher': r['pd'],
                          'volumes': [{'number': n, 'asin': None, 'isbn13': ib, 'cover_url': None, 'release_date': dt} for n, ib, dt in r['vols']]}]
        plans[sl] = d
    if not APPLY:
        print('\n(dry-run)'); return
    bak = ROOT/'.cache'/f'sharedisbn-repoint2-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True, exist_ok=True)
    lf = (ROOT/'data/seeds/sharedisbn-step1-changelog.jsonl').open('a', encoding='utf-8'); st = time.strftime('%Y-%m-%dT%H:%M:%S')
    for sl, d in plans.items():
        for base in BASES:
            fp = ROOT/base/f'{sl}.yml'
            if base == 'data/manga.v2' or fp.exists():
                if fp.exists(): shutil.copy2(fp, bak/(base.replace('/', '_')+'__'+sl+'.yml'))
                fp.write_text(yaml.dump(d, allow_unicode=True, sort_keys=False), encoding='utf-8')
        lf.write(J.dumps({'slug': sl, 'op': 'repoint_ndl', 'isbns': [v[1] for v in REPOINT[sl]['vols']], 'at': st}, ensure_ascii=False)+'\n')
    lf.close()
    print(f'\n適用 {len(plans)}件。 backup={bak}')
if __name__ == '__main__': main()
