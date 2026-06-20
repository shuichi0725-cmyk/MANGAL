#!/usr/bin/env python3
"""
ISBN誤共有 un-merge ③ (慎重):
 A) re-point: 誤共有ISBNを剥がし種1の真ISBNへ差替+汚染enrich除去(両作生存)
      kurotokage-2019(森下裕美)→9784575945614 双葉社2019-11
      gift-2012(塩森恵子)     →9784575334906 双葉社2012-08
 B) dedup/alias: hiyoko-brand→oku-sama-wa-joshikousei(同著者+cm104題一致+愛蔵版13ISBN同一)
 C) strip→needs-content: 誤側(別著者・真ISBN無し)を除去しneeds-content記録(kafuka型)
      24colors(千葉コズエ)/venus-2015(麻生歩)/gift-2006(ユキヲ)/fire-emblem-thracia-776-2000(日野慎之助)
dry-run/--apply。 backup+changelog+alias。種2不変。可逆。
"""
import sys, time, shutil, json as J
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT = Path(__file__).resolve().parent.parent
import yaml
APPLY = '--apply' in sys.argv
BASES = ('data/manga.v2', '.preview-data/manga')

# A) re-point: 真ISBNの clean stub (汚染enrichは全除去、次promoteで再enrich)
REPOINT = {
 'kurotokage-2019': dict(title='黒トカゲ', title_kana='クロトカゲ', title_romaji='kurotokage',
    author='森下裕美', author_kana='モリシタヒロミ', author_romaji='morishitahiromi',
    isbn='9784575945614', date='2019-11', year=2019, pages=124),
 'gift-2012': dict(title='gift', title_kana='ギフト', title_romaji='gifuto',
    author='塩森恵子', author_kana='シオモリケイコ', author_romaji='shiomorikeiko',
    isbn='9784575334906', date='2012-08', year=2012, pages=None),
}
# B) dedup
DEDUP = [('oku-sama-wa-joshikousei', ['hiyoko-brand'])]
# C) strip→needs-content (別著者・真ISBN無し)
STRIP = ['24colors', 'venus-2015', 'gift-2006', 'fire-emblem-thracia-776-2000']

def fp_for(base, slug): return ROOT / base / f'{slug}.yml'

def build_stub(slug, r):
    """汚染enrichを落とした最小cleanページ"""
    vol = {'number': 1, 'asin': None, 'isbn13': r['isbn'], 'cover_url': None, 'release_date': r['date']}
    if r.get('pages'): vol['pages'] = r['pages']
    return {
        'slug': slug,
        'title': r['title'],
        'title_kana': r['title_kana'],
        'title_romaji': r['title_romaji'],
        'year_started': r['year'],
        'year_ended': r['year'],
        'status': 'completed',
        'authors': [{'name': r['author'], 'role': 'writer_artist',
                     'kana': r['author_kana'], 'romaji': r['author_romaji']}],
        'original_authors': [],
        'publisher': 'futabasha',
        'magazine': None,
        'anime_adapted': False,
        'editions': [{'type': 'standard', 'label': '通常版', 'publisher': '双葉社',
                      'volumes': [vol]}],
        'publishers': ['futabasha'],
    }

def main():
    print('=== un-merge ③ ' + ('APPLY' if APPLY else 'DRY-RUN') + ' ===')
    print('\nA) re-point:')
    for slug, r in REPOINT.items():
        d = yaml.safe_load(fp_for('data/manga.v2', slug).read_text(encoding='utf-8'))
        old = [v.get('isbn13') for e in d.get('editions', []) for v in e.get('volumes', [])]
        print(f'  {slug}: 誤ISBN{old} → 真ISBN[{r["isbn"]}] {r["author"]} 双葉社{r["date"]} (汚染enrich除去)')
    print('\nB) dedup/alias:')
    for canon, dups in DEDUP:
        print(f'  {dups} → {canon}')
    print('\nC) strip→needs-content:')
    for slug in STRIP:
        d = yaml.safe_load(fp_for('data/manga.v2', slug).read_text(encoding='utf-8'))
        print(f'  {slug}「{d.get("title")}」著{[a.get("name") for a in (d.get("authors") or [])]} 除去(真ISBN無)')

    if not APPLY:
        print('\n(dry-run。 --applyで適用)'); return

    bak = ROOT / '.cache' / f'unmerge3-bak-{time.strftime("%Y%m%d-%H%M%S")}'
    bak.mkdir(parents=True, exist_ok=True)
    af = ROOT / 'data' / 'seeds' / 'dup-merge-alias.yml'
    alias = yaml.safe_load(af.read_text(encoding='utf-8')) or {}
    lf = (ROOT / 'data' / 'seeds' / 'unmerge-changelog.jsonl').open('a', encoding='utf-8')
    st = time.strftime('%Y-%m-%dT%H:%M:%S')

    def backup(base, slug):
        fp = fp_for(base, slug)
        if fp.exists(): shutil.copy2(fp, bak / (base.replace('/', '_') + '__' + slug + '.yml'))
        return fp

    # A) re-point
    for slug, r in REPOINT.items():
        stub = build_stub(slug, r)
        for base in BASES:
            fp = backup(base, slug)
            if not fp.exists(): continue
            fp.write_text(yaml.dump(stub, allow_unicode=True, sort_keys=False), encoding='utf-8')
        lf.write(J.dumps({'repoint': slug, 'isbn': r['isbn'], 'at': st}, ensure_ascii=False) + '\n')
        print('  repointed', slug)

    # B) dedup/alias
    for canon, dups in DEDUP:
        for dup in dups:
            alias[dup] = canon
            for base in BASES:
                fp = backup(base, dup)
                if fp.exists(): fp.unlink()
            lf.write(J.dumps({'dedup': dup, 'canon': canon, 'at': st}, ensure_ascii=False) + '\n')
            print('  aliased+removed', dup, '->', canon)

    # C) strip→needs-content
    needs = []
    for slug in STRIP:
        needs.append(slug)
        for base in BASES:
            fp = backup(base, slug)
            if fp.exists(): fp.unlink()
        lf.write(J.dumps({'strip_needs_content': slug, 'at': st}, ensure_ascii=False) + '\n')
        print('  stripped(needs-content)', slug)

    af.write_text(yaml.dump(alias, allow_unicode=True, sort_keys=True), encoding='utf-8')
    lf.close()
    if needs:
        p = ROOT / 'data' / 'seeds' / 'unmerge-needs-content.tsv'
        with open(p, 'a', encoding='utf-8') as f:
            for s in needs: f.write(s + '\t' + st + '\n')
    print(f'\n適用完了。 re-point {len(REPOINT)} / dedup {sum(len(d) for _,d in DEDUP)} / strip {len(needs)}。 backup={bak}')

if __name__ == '__main__': main()
