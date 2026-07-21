"""NDL発見316(楽天収穫済)を preview ページ化(慎重・テスト先行)。
NDL題/kana/著者/出版社 + 楽天書影/caption + enrich(あらすじ/キャッチ/ジャンル) → .preview-data/manga/*.yml。
非漫画(画集/語学/公式ガイド)・mook(コミック誌/Vol.のみ)は除外。db-v2/本番は不変(preview直書き)。
"""
import json, re, os, collections, unicodedata, yaml, pykakasi
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
PREV = f"{ROOT}/.preview-data/manga"
kks = pykakasi.kakasi()
mat = json.load(open(f"{ROOT}/.cache/ndl316-material.json", encoding="utf-8"))
enr = {r["isbn"]: r for r in json.load(open(f"{ROOT}/.cache/enrich-ndl316-results.json", encoding="utf-8"))}

GENVOCAB = set('action,adventure,fantasy,sci-fi,mystery,horror,gag,comedy,romcom,romance,drama,slice-of-life,school,sports,baseball,soccer,historical,samurai,mecha,yokai,gourmet,4-koma,essay,isekai,bl,suspense,music,supernatural,ecchi,mind-game,mahou-shoujo,war'.split(','))

# 出版社名 → キー (publishers.yml の name + 正規化照合)
_pub = yaml.safe_load(open(f"{ROOT}/data/publishers.yml", encoding="utf-8"))
def _pn(s): return re.sub(r'[\s　・()（）株式会社]', '', unicodedata.normalize("NFKC", str(s or ""))).lower()
PUBKEY = {}
for k, v in (_pub.items() if isinstance(_pub, dict) else []):
    nm = v.get("name") if isinstance(v, dict) else v
    PUBKEY[_pn(nm)] = k
    for al in (v.get("aliases") or []) if isinstance(v, dict) else []:
        PUBKEY[_pn(al)] = k
def pub_key(name):
    return PUBKEY.get(_pn(name), "(unknown)")
DROP = re.compile(r'画集|原画集|イラスト集|設定資料|ファンブック|公式ガイド|公式ファン|CLIP STUDIO|語学|韓国語|英語版|バイリンガル|コミック艶|コミケ|大全|名鑑')

def base_title(t):
    t = re.sub(r'\s*=\s*[A-Za-z].*$', '', str(t or ''))  # = English 以降
    t = re.sub(r'\s*[:：].*$', '', t)                      # 副題
    t = re.sub(r'\s*[\.．]?\s*Vol\.?\s*\d*\s*$', '', t, flags=re.I)
    t = re.sub(r'\s*\d+\s*$', '', t)
    return t.strip()

def primary_author(c):
    a = re.split(r'[／/、,]', str(c or ''))[0]
    a = re.sub(r'\s*(著|画|作画|原作|漫画|編|イラスト|脚本|監修|原案).*$', '', a)
    return a.strip()

def romaji(s):
    out = "".join(x['hepburn'] for x in kks.convert(str(s or "")))
    out = re.sub(r'[^a-z0-9]+', '-', out.lower()).strip('-')
    return out or "x"

def make_slug(title, kana):
    # ★slugは「読み(NDL/楽天のkana)」基点。 漢字をpykakasiで読ませない(君→クン誤読を防ぐ)。
    #  Latin題/数字含む題は元綴り温存(GROUNDLESS/50婚→keep)、 純日本語題はkana読みをローマ字化。
    if re.search(r'[A-Za-z]', str(title)) or re.search(r'\d', str(title)) or not kana:
        return romaji(title)
    k = re.split(r'[:：]', str(kana))[0]   # 副題off
    return romaji(k)

def volnum(m):
    v = re.sub(r'\D', '', str(m.get('volume') or ''))
    if v:
        return int(v)
    t = m.get('title') or ''
    mm = re.search(r'(\d+)\s*$', t) or re.search(r'Vol\.\s*(\d+)', t, re.I)
    return int(mm.group(1)) if mm else 1

def parse_date(d):
    d = str(d or '').replace('.', '-')
    m = re.match(r'(\d{4})-(\d{1,2})(?:-(\d{1,2}))?', d)
    if not m:
        return None
    return f"{m.group(1)}-{int(m.group(2)):02d}" + (f"-{int(m.group(3)):02d}" if m.group(3) else "")

# 作品グループ化
works = collections.defaultdict(list)
for ib, m in mat.items():
    works[(base_title(m['title']), primary_author(m['creators']))].append(ib)

used_slugs = set(os.path.splitext(os.path.basename(p))[0] for p in __import__('glob').glob(f"{PREV}/*.yml"))
gen = drop = 0
skip_meta = 0
for (bt, author), isbns in works.items():
    if not bt or DROP.search(bt):
        drop += 1
        continue
    rep0 = mat[sorted(isbns, key=lambda ib: volnum(mat[ib]))[0]]
    tk = re.sub(r'\s+', '', str(rep0.get('kana') or ''))
    # ★表示ガード: 著者・kana 必須(mook/アンソロ=著者空 を自然除外)
    if not author or not tk:
        skip_meta += 1
        continue
    isbns = sorted(isbns, key=lambda ib: volnum(mat[ib]))
    rep = mat[isbns[0]]
    # slug = ★読み(kana)基点 (漢字pykakasi誤読を避ける)。 Latin/数字は元綴り温存
    slug = make_slug(bt, tk)[:50]
    if slug in used_slugs:
        slug = f"{slug}-{romaji(author)[:12]}" if author else f"{slug}-{isbns[0][-4:]}"
    if slug in used_slugs:
        slug = f"{slug}-{isbns[0][-4:]}"
    used_slugs.add(slug)
    # genres/synopsis/catch: 代表ISBN(vol1)のenrich優先、 無ければ他巻
    g = []; syn = ""; cat = ""
    for ib in isbns:
        e = enr.get(ib, {})
        if not g: g = [x for x in (e.get('genres') or []) if x in GENVOCAB][:4]
        if not syn and e.get('synopsis'): syn = e['synopsis']
        if not cat and e.get('catch'): cat = e['catch']
    if not g:
        g = ['drama']  # 最低1(loadData表示要件)。 暫定
    vols = []
    for ib in isbns:
        m = mat[ib]
        vols.append({"number": volnum(m), "asin": None, "isbn13": ib,
                     "cover_url": (m.get('cover') or None) if 'noimage' not in str(m.get('cover') or '') else None,
                     "release_date": parse_date(m.get('date'))})
    page = {
        "slug": slug, "title": bt,
        "title_kana": tk,
        "title_romaji": romaji(bt).replace('-', ' '),
        "year_started": int(str(rep.get('date'))[:4]) if str(rep.get('date'))[:4].isdigit() else None,
        "status": "ongoing", "demographic": "seinen",
        "authors": [{"name": author, "role": "writer_artist"}],
        "publisher": pub_key(rep.get('publisher')),
        "publishers": [pub_key(rep.get('publisher'))] if pub_key(rep.get('publisher')) != "(unknown)" else [],
        "genres": g, "genres_provisional": True,
        "synopsis": syn or None, "catch": cat or None,
        "source": "ndl-discovery-2425",
        "editions": [{"type": "standard", "label": "通常版", "publisher": rep.get('publisher') or None,
                      "imprint": rep.get('publisher') or None, "volumes": vols}],
    }
    with open(f"{PREV}/{slug}.yml", "w", encoding="utf-8") as f:
        yaml.safe_dump(page, f, allow_unicode=True, sort_keys=False, width=4096)
    gen += 1

print(f"preview生成: {gen} 作 / 非漫画drop {drop} / 著者orkana欠落skip {skip_meta}")
