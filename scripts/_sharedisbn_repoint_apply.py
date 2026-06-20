#!/usr/bin/env python3
"""
A REPOINT適用(NDL確定分): 別著者の巻を抱えるページを、NDLで確定した自前ISBNへ差替。
別作のenrich(anilist/synopsis/原作者/年/出版社)を全clearしidentity(題/著者/kana/romaji)のみ保持=clean stub。
全件 NDL SRU(著者×題)で自前ISBN・年・出版社を裏取り済、check-digit緑。dry-run/--apply。可逆。
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
         'demographic', 'magazine', 'subtitle', 'subtitle_kana', 'year_ended']

REPOINT = {
 'tenyoritakaku':                     dict(isbn='9784832277687', pk='houbunsha',          pd='芳文社',           date='2009-01', year=2009),
 'catwalk':                           dict(isbn='9784757720527', pk='enterbrain',         pd='エンターブレイン', date='2004',    year=2004),
 'comic-higashino-keigo-mystery-2014':dict(isbn='9784408174839', pk='jitsugyo-no-nihon',  pd='実業之日本社',     date='2014',    year=2014),
 'rocketman':                         dict(isbn='9784778031541', pk='shogakukan-creative',pd='小学館クリエイティブ', date='2010', year=2010),
 'crusader-kawaso-2002':              dict(isbn='9784592172093', pk='hakusensha',          pd='白泉社',           date='2002',    year=2002),
}

def main():
    print('=== A REPOINT ' + ('APPLY' if APPLY else 'DRY-RUN') + ' ===')
    plans = {}
    for sl, r in REPOINT.items():
        fp = ROOT/'data/manga.v2'/f'{sl}.yml'
        d = yaml.safe_load(fp.read_text(encoding='utf-8'))
        old = [v.get('isbn13') for e in (d.get('editions') or []) for v in (e.get('volumes') or [])]
        au = [a.get('name') for a in (d.get('authors') or [])]
        print(f"  {sl}({'/'.join(au)}): 誤{old} → 自前[{r['isbn']}] {r['pd']}{r['year']}")
        for k in CLEAR: d.pop(k, None)
        d['original_authors'] = []
        d['publisher'] = r['pk']; d['publishers'] = [r['pk']]
        d['year_started'] = r['year']; d['year_ended'] = r['year']; d['status'] = 'completed'
        d['editions'] = [{'type': 'standard', 'label': '通常版', 'publisher': r['pd'],
                          'volumes': [{'number': 1, 'asin': None, 'isbn13': r['isbn'], 'cover_url': None, 'release_date': r['date']}]}]
        plans[sl] = d
    if not APPLY:
        print('\n(dry-run。 --applyで適用)'); return
    bak = ROOT/'.cache'/f'sharedisbn-repoint-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True, exist_ok=True)
    lf = (ROOT/'data/seeds/sharedisbn-step1-changelog.jsonl').open('a', encoding='utf-8')
    st = time.strftime('%Y-%m-%dT%H:%M:%S')
    for sl, d in plans.items():
        for base in BASES:
            fp = ROOT/base/f'{sl}.yml'
            if base == 'data/manga.v2' or fp.exists():
                if fp.exists(): shutil.copy2(fp, bak/(base.replace('/', '_')+'__'+sl+'.yml'))
                fp.write_text(yaml.dump(d, allow_unicode=True, sort_keys=False), encoding='utf-8')
        lf.write(J.dumps({'slug': sl, 'op': 'repoint_ndl', 'isbn': REPOINT[sl]['isbn'], 'at': st}, ensure_ascii=False)+'\n')
    lf.close()
    print(f'\n適用 {len(plans)}件。 backup={bak}')

if __name__ == '__main__': main()
