#!/usr/bin/env python3
"""
ISBN誤共有 un-merge ⑤(needs-content解決): ③で誤ISBNを剥がし除去した5件をNDL/AniListで実在確認。
 実在3件=正ISBN(NDL裏取り)で復元。1件=Cain Saga一編→alias。1件=別著者の実作→除去のまま記録。

 ★復元(backupから最小パッチ=検証で誤と確定したISBN/出版社/年のみ修正、正enrichは保持):
   24colors          : AniList35686=24Colors初恋のパレット(千葉コズエ,正)。誤=麻生歩COLORS ISBN→正9784091316073(小学館2008)
   venus-2015        : NDL=ヴィーナス禁じられた危険なキス(麻生歩,宙出版2015)。誤=関口シュンISBN→正9784776739586
   fire-emblem-...-2000: NDL=日野慎之助FEトラキア776(エンターブレイン2000,たかなぎ版とは別作)。誤=たかなぎISBN→正9784757700321。AniList35619(たかなぎの物)はclear
 ★alias: kafuka(AniList30885=伯爵カインシリーズの一編「カフカ」)→hakushaku-cain
 ★除去のまま: gift-2006(AniList55445=東山翔の官能Gift。当ページはユキヲ誤帰属+誤ISBN=全て誤)。記録のみ。
dry-run/--apply。backup+changelog+alias。可逆。
"""
import sys, time, shutil, json as J
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT = Path(__file__).resolve().parent.parent
import yaml
APPLY = '--apply' in sys.argv
BASES = ('data/manga.v2', '.preview-data/manga')
BAK3 = ROOT/'.cache'/'unmerge3-bak-20260620-103905'

# 復元: backup_file, patch(publisher_key, publisher_disp, year, isbn, date, clear[])
RESTORE = {
 '24colors': dict(bak='data_manga.v2__24colors.yml',
    pub_key='shogakukan', pub_disp='小学館', year=2008,
    isbn='9784091316073', date='2008', clear=[]),
 'venus-2015': dict(bak='data_manga.v2__venus-2015.yml',
    pub_key='ozora-shuppan', pub_disp='宙出版', year=2015,
    isbn='9784776739586', date='2015', clear=[]),
 'fire-emblem-thracia-776-2000': dict(bak='data_manga.v2__fire-emblem-thracia-776-2000.yml',
    pub_key='enterbrain', pub_disp='エンターブレイン', year=2000,
    isbn='9784757700321', date='2000', clear=['anilist_id','synopsis','wikidata_qid','genres_anilist','tags','catch','popularity','alternative_titles']),
}
ALIAS = [('kafuka', 'hakushaku-cain')]
LEAVE_REMOVED = {'gift-2006': 'AniList55445=東山翔の官能Gift(2007)。当ページはユキヲ誤帰属+秋本尚美ISBN=全誤。実作は別著者ゆえ別途新規要。除去のまま'}

def main():
    print('=== un-merge ⑤ ' + ('APPLY' if APPLY else 'DRY-RUN') + ' ===\n復元:')
    for slug, p in RESTORE.items():
        d = yaml.safe_load((BAK3/p['bak']).read_text(encoding='utf-8'))
        old = [v.get('isbn13') for e in d.get('editions', []) for v in e.get('volumes', [])]
        print(f'  {slug}: 誤{old} → 正[{p["isbn"]}] {p["pub_disp"]}{p["year"]}' + (f' clear={p["clear"]}' if p['clear'] else ''))
    print('alias:')
    for s, c in ALIAS: print(f'  {s} → {c}')
    print('除去のまま:')
    for s, n in LEAVE_REMOVED.items(): print(f'  {s}: {n}')
    if not APPLY:
        print('\n(dry-run。 --applyで適用)'); return

    bak = ROOT/'.cache'/f'unmerge5-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True, exist_ok=True)
    af = ROOT/'data/seeds/dup-merge-alias.yml'; alias = yaml.safe_load(af.read_text(encoding='utf-8')) or {}
    lf = (ROOT/'data/seeds/unmerge-changelog.jsonl').open('a', encoding='utf-8'); st = time.strftime('%Y-%m-%dT%H:%M:%S')

    for slug, p in RESTORE.items():
        d = yaml.safe_load((BAK3/p['bak']).read_text(encoding='utf-8'))
        # 検証済の正データで上書き
        d['editions'] = [{'type':'standard','label':'通常版','publisher':p['pub_disp'],
                          'volumes':[{'number':1,'asin':None,'isbn13':p['isbn'],'cover_url':None,'release_date':p['date']}]}]
        d['publisher'] = p['pub_key']; d['publishers'] = [p['pub_key']]
        d['year_started'] = p['year']; d['year_ended'] = p['year']
        for k in p['clear']: d.pop(k, None)
        for base in BASES:
            fp = ROOT/base/f'{slug}.yml'
            # restore into v2 always; preview only if it had one (it didn't for these)
            if base == 'data/manga.v2' or fp.exists():
                if fp.exists(): shutil.copy2(fp, bak/(base.replace('/','_')+'__'+slug+'.yml'))
                fp.write_text(yaml.dump(d, allow_unicode=True, sort_keys=False), encoding='utf-8')
        lf.write(J.dumps({'restore': slug, 'isbn': p['isbn'], 'at': st}, ensure_ascii=False)+'\n')
        print('  restored', slug)
    for s, c in ALIAS:
        alias[s] = c
        lf.write(J.dumps({'alias_needscontent': s, 'canon': c, 'at': st}, ensure_ascii=False)+'\n')
        print('  aliased', s, '->', c)
    af.write_text(yaml.dump(alias, allow_unicode=True, sort_keys=True), encoding='utf-8'); lf.close()
    print('\n適用完了。 backup=', bak)

if __name__ == '__main__': main()
