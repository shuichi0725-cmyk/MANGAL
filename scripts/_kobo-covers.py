# -*- coding: utf-8 -*-
# Kobo書影補完バッチ: --prepare N=対象上位N作のKobo照合+装丁比較ペアDL / --apply slugs=合格作をcovers seedへ
import glob, json, os, re, sys, time, unicodedata, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding='utf-8')
import yaml
try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
KEEP = {'standard', 'bunkobon', 'wideban', 'kanzenban', 'shinsoban', 'aizoban'}
CHK = f'{ROOT}/.cache/kobocheck'
os.makedirs(CHK, exist_ok=True)

env = {}
for ln in open(f'{ROOT}/.env.local', encoding='utf-8'):
    ln = ln.strip()
    if '=' in ln and not ln.startswith('#'):
        k, v = ln.split('=', 1)
        env[k.strip()] = v.strip()
ORIGIN = env.get('RAKUTEN_REFERER', '').rstrip('/')

def norm(t):
    t = unicodedata.normalize('NFKC', str(t or ''))
    return re.sub(r'[\s　・!！?？:：〜~\-＆&。、．.]', '', t).lower()

def kobo(title, page):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "title": title, "hits": "30", "page": str(page), "format": "json", "formatVersion": "2"}
    req = urllib.request.Request("https://openapi.rakuten.co.jp/services/api/Kobo/EbookSearch/20170426?" + urllib.parse.urlencode(p))
    req.add_header("Referer", ORIGIN + "/")
    req.add_header("Origin", ORIGIN)
    req.add_header("User-Agent", "Mozilla/5.0")
    return json.loads(urllib.request.urlopen(req, timeout=25).read())

VOLP = re.compile(r'[（(]\s*(\d{1,3})\s*[)）]\s*$')
# ★直結数字型(まるごし刑事69型 2026-08-06 ユーザ発見): Kobo題が「題69」とスペース無しで数字直結する
#   レーベルがあり、括弧形式限定だと全巻不一致→「Kobo一致なし」と誤記帳していた。
#   誤爆防止(続編「題2」型): 括弧一致がゼロ かつ 直結番号が3巻以上ある時だけ採用する。
VOLP_BARE = re.compile(r'(\d{1,3})\s*$')

def prepare(n_works, only=None):
    """only= slug集合を指定すると、その頁だけを対象にする(per-case「○○をKoboして」用)。
    ★only指定時は done 記録も無視する(過去の偽「一致なし」を再照会できるように)。"""
    # 軽症組をpreviewディレクトリ(=既に抽出済み)から、欠け巻数降順で
    works = []
    src = f'{ROOT}/data/manga.v2' if only else f'{ROOT}/.preview-data/manga'
    for p in glob.glob(f'{src}/*.yml'):
        if only and os.path.basename(p)[:-4] not in only:
            continue
        d = yaml.load(open(p, encoding='utf-8'), Loader=L)
        if not d:
            continue
        miss = [(e.get('type'), v['number'], str(v.get('isbn13') or ''))
                for e in d.get('editions') or [] if e.get('type') in KEEP
                for v in (e.get('volumes') or []) if not v.get('cover_url')]
        miss_isbn = [m for m in miss if len(m[2]) == 13]
        if miss_isbn:
            works.append((len(miss_isbn), os.path.basename(p)[:-4], d.get('title'), miss_isbn, d))
    works.sort(reverse=True, key=lambda x: x[0])
    done = json.load(open(f'{ROOT}/.cache/kobo-done.json', encoding='utf-8')) if os.path.exists(f'{ROOT}/.cache/kobo-done.json') else []
    if not only:
        works = [w for w in works if w[1] not in done]
    works = works[:n_works]
    pend = []
    for nmiss, slug, title, miss, d in works:
        pt = norm(title)
        vols = {}
        bare = {}
        total = None
        pg = 1
        while pg <= 4:
            try:
                r = kobo(title, pg)
            except Exception as e:
                print(f'  {slug}: kobo ERR {e}')
                break
            total = r.get('count') or 0
            for it in (r.get('Items') or []):
                t2 = unicodedata.normalize('NFKC', str(it.get('title'))).strip()
                img = str(it.get('largeImageUrl') or '')
                if not img or 'noimage' in img:
                    continue
                m = VOLP.search(t2)
                if m and norm(VOLP.sub('', t2)) == pt:
                    vols.setdefault(int(m.group(1)), img)
                    continue
                mb = VOLP_BARE.search(t2)
                if mb and norm(VOLP_BARE.sub('', t2)) == pt:
                    bare.setdefault(int(mb.group(1)), img)
            pg += 1
            time.sleep(1.3)
            if total and pg * 30 > total:
                break
        if not vols and len(bare) >= 3:
            vols = bare
            print(f'  {slug}: 直結数字型として採用({len(bare)}巻)')
        cand = [(et, vn, ib, vols[vn]) for et, vn, ib in miss if vn in vols]
        if not cand:
            print(f'  {slug}: 欠{nmiss} → Kobo一致なし(skip)')
            done.append(slug)  # 再照会しない
            continue
        # 比較ペアDL: kobo候補1枚 + 既存紙表紙1枚(同edition・近い巻)
        et0, vn0, ib0, kurl = cand[0]
        paper = None
        e = next((x for x in d['editions'] if x.get('type') == et0), None)
        if e:
            withc = sorted([v for v in e['volumes'] if v.get('cover_url') and v.get('number')],
                           key=lambda v: abs(v['number'] - vn0))
            if withc:
                paper = withc[0]['cover_url']
        try:
            urllib.request.urlretrieve(kurl, f'{CHK}/{slug}-kobo-v{vn0}.jpg')
            if paper:
                urllib.request.urlretrieve(paper, f'{CHK}/{slug}-paper.jpg')
        except Exception as e2:
            print(f'  {slug}: 画像DL失敗 {e2}')
            continue
        pend.append({'slug': slug, 'title': title, 'n_miss': nmiss, 'n_cand': len(cand),
                     'cands': [(et, vn, ib, u) for et, vn, ib, u in cand],
                     'kobo_img': f'{CHK}/{slug}-kobo-v{vn0}.jpg', 'paper_img': f'{CHK}/{slug}-paper.jpg' if paper else None})
        print(f'  {slug}: 欠{nmiss} → kobo候補{len(cand)} 比較ペアDL済(v{vn0})')
    json.dump(done, open(f'{ROOT}/.cache/kobo-done.json', 'w'))
    json.dump(pend, open(f'{ROOT}/.cache/kobo-pending.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'prepare完了: {len(pend)}作が目視待ち')

def apply(ok_slugs):
    import gzip, hashlib
    pend = json.load(open(f'{ROOT}/.cache/kobo-pending.json', encoding='utf-8'))
    rows = []
    touched = []
    for w in pend:
        if w['slug'] not in ok_slugs:
            continue
        for et, vn, ib, u in w['cands']:
            u2 = u.split('?')[0] + '?_ex=200x200'
            rows.append({'isbn13': ib, 'cover_url': u2})
        touched.append(w['slug'])
    # covers seed 追記(既存優先=既に載ってるISBNは触らない)
    existing = set()
    with gzip.open(f'{ROOT}/data/seeds/covers.jsonl.gz', 'rt', encoding='utf-8') as f:
        for ln in f:
            existing.add(json.loads(ln).get('isbn13'))
    new = [r for r in rows if r['isbn13'] not in existing]
    with gzip.open(f'{ROOT}/data/seeds/covers.jsonl.gz', 'at', encoding='utf-8') as f:
        for r in new:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    done_p = f'{ROOT}/.cache/kobo-done.json'
    done = json.load(open(done_p, encoding='utf-8')) if os.path.exists(done_p) else []
    done += touched
    json.dump(done, open(done_p, 'w'))
    json.dump(touched, open(f'{ROOT}/.cache/kobo-touched.json', 'w'))
    print(f'covers追記 {len(new)}件 / 対象頁 {len(touched)}: {touched}')

if __name__ == '__main__':
    if sys.argv[1] == '--prepare':
        prepare(int(sys.argv[2]))
    elif sys.argv[1] == '--slugs':
        s = set(sys.argv[2].split(','))
        prepare(len(s), only=s)
    elif sys.argv[1] == '--apply':
        apply(sys.argv[2].split(','))
