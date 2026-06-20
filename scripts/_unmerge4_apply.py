#!/usr/bin/env python3
"""
ISBN誤共有 un-merge ④(慎重・残存共有解消): 残2スロットを真ISBN(ユーザ調査)へ選択的差替。
 colors-2001(啄木鳥しんき): 誤=麻生歩のColors 3ISBN+自前vol4 → 啄木鳥の全4ISBN(エンターブレイン)に置換。
                            qidは麻生歩作の可能性で不確実→clear。kana/romaji/author/genres(provisional)は保持。
 gift-ichinose-2015(一ノ瀬ゆま): 誤=秋本尚美のGift 2ISBN+自前下巻 → 一ノ瀬の上中下3ISBN(幻冬舎)に置換。
                            ★enrich(synopsis/synonyms/anilist_id 106164/BLタグ)は一ノ瀬本人に正マッチ済=全保持。巻+出版社+年のみ修正。
裏取り: 一ノ瀬3巻=種1で[著]一ノ瀬ゆま確認。啄木鳥vol4=楽天確認、vol1-3=ユーザ調査+ISBN連番一致。
dry-run/--apply。 backup+changelog。種2不変。可逆。
"""
import sys, time, shutil, json as J
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT = Path(__file__).resolve().parent.parent
import yaml
APPLY = '--apply' in sys.argv
BASES = ('data/manga.v2', '.preview-data/manga')

PLAN = {
 'colors-2001': dict(
    publisher_key='enterbrain', publisher_disp='エンターブレイン', imprint=None,
    year_started=2001, year_ended=2002, clear=['wikidata_qid'],
    volumes=[
      (1, '9784757705128', None),
      (2, '9784757707054', None),
      (3, '9784757708846', None),
      (4, '9784757711716', '2002-11'),
    ]),
 'gift-ichinose-2015': dict(
    publisher_key='gentosha-comics', publisher_disp='幻冬舎コミックス', imprint='幻冬舎コミックス',
    year_started=2015, year_ended=2018, clear=[],
    volumes=[
      (1, '9784344834798', '2015-06', '上'),
      (2, '9784344839205', '2017-02', '中'),
      (3, '9784344843585', '2018-12', '下'),
    ]),
}

def build_volume(t):
    num, isbn, date = t[0], t[1], t[2]
    v = {'number': num, 'asin': None, 'isbn13': isbn, 'cover_url': None, 'release_date': date}
    if len(t) > 3 and t[3]:
        v = {'number': num, 'volume_label': t[3], 'asin': None, 'isbn13': isbn, 'cover_url': None, 'release_date': date}
    return v

def main():
    print('=== un-merge ④ ' + ('APPLY' if APPLY else 'DRY-RUN') + ' ===')
    for slug, p in PLAN.items():
        d = yaml.safe_load((ROOT/'data/manga.v2'/f'{slug}.yml').read_text(encoding='utf-8'))
        old = [v.get('isbn13') for e in d.get('editions', []) for v in e.get('volumes', [])]
        new = [t[1] for t in p['volumes']]
        au = [a.get('name') for a in (d.get('authors') or [])]
        print(f'\n■{slug}「{d.get("title")}」著{au}')
        print(f'   旧ISBN {old}')
        print(f'   新ISBN {new}  ({p["publisher_disp"]} {p["year_started"]}-{p["year_ended"]})')
        if p['clear']: print(f'   clear: {p["clear"]}')
        keep = [k for k in ('synopsis','synonyms','anilist_id','genres_anilist','tags','catch','adult_us') if d.get(k)]
        if keep: print(f'   保持enrich: {keep}')

    if not APPLY:
        print('\n(dry-run。 --applyで適用)'); return
    bak = ROOT/'.cache'/f'unmerge4-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True, exist_ok=True)
    lf = (ROOT/'data/seeds/unmerge-changelog.jsonl').open('a', encoding='utf-8')
    st = time.strftime('%Y-%m-%dT%H:%M:%S')
    for slug, p in PLAN.items():
        newed = {'type': 'standard', 'label': '通常版', 'publisher': p['publisher_disp']}
        if p['imprint']: newed['imprint'] = p['imprint']
        newed['volumes'] = [build_volume(t) for t in p['volumes']]
        for base in BASES:
            fp = ROOT/base/f'{slug}.yml'
            if not fp.exists(): continue
            d = yaml.safe_load(fp.read_text(encoding='utf-8'))
            shutil.copy2(fp, bak/(base.replace('/','_')+'__'+slug+'.yml'))
            d['editions'] = [newed]
            d['publisher'] = p['publisher_key']
            d['publishers'] = [p['publisher_key']]
            d['year_started'] = p['year_started']
            d['year_ended'] = p['year_ended']
            for k in p['clear']:
                d.pop(k, None)
            fp.write_text(yaml.dump(d, allow_unicode=True, sort_keys=False), encoding='utf-8')
        lf.write(J.dumps({'repoint4': slug, 'isbns': [t[1] for t in p['volumes']], 'at': st}, ensure_ascii=False)+'\n')
        print('  repointed', slug)
    lf.close()
    print(f'\n適用完了。 backup={bak}')

if __name__ == '__main__': main()
