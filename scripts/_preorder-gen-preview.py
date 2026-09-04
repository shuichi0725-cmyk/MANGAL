#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""予約②③: 新作1巻のpreviewドラフトページ生成 (= 2026-07-06 B裁定=テスト先行)

classified.json の new1a(②作者既知)/new1b(③作者新規) を .preview-data/manga/ に生成する。
本番(data/manga.v2)には書かない。ユーザ確認後の本番化は別工程。

ゲート(fail-closed・不備は保留worklist):
  titleKana有 / author有 / 発売月(ym)有 / ISBN13 / slug衝突なし
ヨミ: 楽天titleKana/authorKanaで仮確定し、data/seeds/rakuten-kana-pending.jsonl(git追跡)へ
  積む=日次蒸留がNDL照合を試み、確定/不一致を裁く(A裁定=漏れない仕組み)。
slug: ヨミの機械ローマ字化(長音保持・を=o・促音・スペース=hyphen)。衝突は-年suffix。
demographic: 楽天サブジャンル写像(少年/少女/青年/レディース)。genreは空(捏造しない)。
使い方: python scripts/_preorder-gen-preview.py new1a|new1b|both [--limit N]
"""
import json, os, re, sys, datetime, unicodedata
from _idx_authors import au_name  # ★索引v2 authorsパック対応(2026-07-14)
sys.stdout.reconfigure(encoding="utf-8")
import yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today().isoformat()
PEND = os.path.join(ROOT, "data", "seeds", "rakuten-kana-pending.jsonl")
TRIAGE = os.path.join(ROOT, "docs", "production-diagnostics", "preorder-triage.tsv")

WHICH = sys.argv[1] if len(sys.argv) > 1 else "both"
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10**9

# ★手動slug seed(2026-09-02): 装置が「自動で決められない」(slug生成不可)と保留した題を人がヨミ基準で裁いた答え。
#   data/seeds/preorder-slug-manual.tsv = isbn13<TAB>slug<TAB>根拠。make_slug の前に参照する。
MANUAL_SLUG = {}
try:
    for _l in open(os.path.join(ROOT, "data", "seeds", "preorder-slug-manual.tsv"), encoding="utf-8"):
        if _l.startswith("#") or not _l.strip():
            continue
        _p = _l.rstrip("\r\n").split("\t")
        if len(_p) >= 2 and _p[0].strip() and _p[1].strip():
            MANUAL_SLUG[_p[0].strip()] = _p[1].strip()
except FileNotFoundError:
    pass
# ★--isbn a,b,c = そのISBNだけ処理(保留分の再生成用。無指定の再実行は既生成と衝突するので使わない)
ONLY_ISBN = set(sys.argv[sys.argv.index("--isbn") + 1].split(",")) if "--isbn" in sys.argv else None

# --- カナ→ローマ字: ★正本は scripts/_kana_romaji.py(2026-07-25 切り出し。取りこぼし頁化と共用) ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kana_romaji import kana2romaji, _K2R  # noqa: E402
# 既存slug集合(本番+preview)
existing = set()
idx = json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8"))
si = idx["f"].index("slug")
for r in idx["d"]:
    existing.add(r[si])

# ★続編slug継承の親候補(2026-07-07 ユーザ指摘=byuutii-poppu-returns事故の恒久修正):
#   同著者の既存本番作の題ヨミが新作ヨミの真の接頭辞なら、親slugを継承し残部だけローマ字化
#   (= ビューティーポップ Returns → beauty-pop + returns)。カタカナ外来語の英語綴りslugを壊さない。
def _norm_kana_key(s):
    return re.sub(r"[\s　]+", "", unicodedata.normalize("NFKC", str(s or "")))
_ki = idx["f"].index("title_kana")
_ai = idx["f"].index("authors")
_parents = {}  # kana_norm -> list[(slug, author_name_set)]
for r in idx["d"]:
    k = _norm_kana_key(r[_ki])
    if len(k) >= 4:
        _parents.setdefault(k, []).append((r[si], {au_name(a) for a in (r[_ai] or []) if au_name(a)}))

def inherit_parent_slug(kana, auths):
    """新作ヨミ=既存本番題ヨミ+残部 かつ 著者一致 なら 親slug-残部romaji を返す(無ければNone)"""
    k = _norm_kana_key(kana)
    best = None  # (parent_kana, parent_slug)
    for pk, cands in _parents.items():
        if not (k.startswith(pk) and len(k) > len(pk)):
            continue
        hits = [slug for slug, names in cands if names & set(auths)]
        if len(hits) != 1:  # 著者不一致 or 同ヨミ同著者の曖昧は継承しない(安全側)
            continue
        if best is None or len(pk) > len(best[0]):
            best = (pk, hits[0])
    if not best:
        return None
    rest = kana2romaji(k[len(best[0]):])
    return f"{best[1]}-{rest}" if rest else None
import glob as _g
for p in _g.glob(f"{ROOT}/.preview-data/manga/*.yml"):
    existing.add(os.path.basename(p)[:-4])

DEMO = {"少年": "shounen", "少女": "shoujo", "青年": "seinen", "レディース": "josei"}

# ★publisher key正規化(2026-07-07 索引skip22事故の恒久修正): 生社名→publishers.ymlのkey。
import unicodedata as _ud
_pubs = yaml.safe_load(open(os.path.join(ROOT, "data", "publishers.yml"), encoding="utf-8")) or {}
_name2key = {}
for _k, _v in _pubs.items():
    if isinstance(_v, dict):
        if _v.get("name"): _name2key[_ud.normalize("NFKC", _v["name"])] = _k
        for _a in _v.get("aliases") or []: _name2key[_ud.normalize("NFKC", _a)] = _k
def _pubkey(name):
    return _name2key.get(_ud.normalize("NFKC", str(name or "")))

def author_names(s):
    out = []
    for x in re.split(r"[/,、;；]", str(s or "")):
        x = x.strip()
        if not x:
            continue
        # ★日本語のみの名前は姓名間の空白を除去(楽天「姓 名」形式→本番無空白慣行。蟹沢ちひろ分裂対策 2026-07-21)
        #   欧文を含む名前(Ark Performance等)の空白は公式表記なので保持
        if not re.search(r"[A-Za-z]", x):
            x = re.sub(r"[ 　]+", "", x)
        out.append(x)
    return out

# ★書影の実URL源(構築禁止 2026-07-09): covers seed → 楽天API
import gzip as _gzip
from _preorder_draft_lib import real_cover as _real_cover
try:
    from _lookup import rakuten_live as _rk_live, _env as _rk_env
    _RKENV = _rk_env()
except Exception:
    _rk_live = _RKENV = None
_COVERS = {}
try:
    for _l in _gzip.open(os.path.join(ROOT, "data", "seeds", "covers.jsonl.gz"), "rt", encoding="utf-8"):
        _r = json.loads(_l); _COVERS[_r.get("isbn13") or _r.get("isbn")] = _r.get("url") or _r.get("cover")
except Exception:
    pass

cls = json.load(open(f"{ROOT}/.cache/preorders/classified.json", encoding="utf-8"))
targets = []
if WHICH in ("new1a", "both"):
    targets += [("new1a", r) for r in cls["new1a"]]
if WHICH in ("new1b", "both"):
    targets += [("new1b", r) for r in cls["new1b"]]
if ONLY_ISBN is not None:
    targets = [(k, r) for k, r in targets if str(r.get("isbn")) in ONLY_ISBN]
targets = targets[:LIMIT]

made = []
holds = []
pend_lines = []
VOLSTRIP = re.compile(r"[\s　]*(?:[（(]\s*\d{1,3}\s*[)）]|第\s*\d{1,3}\s*巻|1)\s*$")  # ★裸数字は1のみ(N≥2を削ると「その6」の6等を破壊し誤1巻化=2026-07-06事故)
from _preorder_title_lib import split_title as _split_title, strip_kana_vol as _strip_kana_vol, split_subtitle as _split_subtitle

def strip_vol_disp(t):
    """★分離器に委譲(2026-07-06 ユーザ裁定): タイトル/巻数/副題を正しく分解しclean題を返す"""
    r = _split_title(t)
    return r["clean"]

def _old_strip_vol_disp(t):
    """表示題/ヨミから末尾の巻表記を除去(作品題に正規化)。全部消える場合は元のまま"""
    t2 = VOLSTRIP.sub("", str(t or "").strip())
    return t2 if t2 else str(t or "").strip()

# ★2026-07-09 全面作り直し: 整形は _preorder_draft_lib に一本化(副題分離/kana=楽天のみ捏造hold/pykakasi slug/@COMIC/英語保持)
from _preorder_draft_lib import clean_title as _clean_title, clean_kana as _clean_kana, make_slug as _make_slug, scope_out as _scope_out, looks_like_criticism as _criticism
# ★上下巻ペアの1頁統合(2026-09-04 ひみつー佐世保事件型)。skill A2-2 の規定だが実装が無く、
#   同日発売の上下巻が new1b(上=1巻の新作) と ex_mid(下=全巻回収不成立) に割れて散っていた。
#   兄弟は増加分の**全class**から集める(下は ex_mid/skip 側に落ちているため)。
_JOGE_ORDER = {"上": 1, "前編": 1, "中": 2, "下": 3, "後編": 2}
_JOGE_LABEL = {"上": "上巻", "中": "中巻", "下": "下巻", "前編": "前編", "後編": "後編"}
_JOGE_RE = re.compile(r"(?:[\s　]+|[\s　]*[（(])(上|中|下|前編|後編)(?:巻)?[)）]?\s*$")


def _joge_mark(title):
    """題末尾の上/中/下・前後編マーカー(無ければ None)。"""
    m = _JOGE_RE.search(unicodedata.normalize("NFKC", str(title or "")).strip())
    return m.group(1) if m else None


def _joge_key(r):
    """兄弟のグループキー = 巻表示を剥いだ題 + 著者 + 出版社。"""
    base, _sub, _p = _clean_title(r.get("title"))
    return (base, str(r.get("author") or ""), str(r.get("publisher") or ""))


_joge_sibs = {}
for _k in ("new1a", "new1b", "ex_mid", "skip"):
    for _r in cls.get(_k, []):
        _m = _joge_mark(_r.get("title"))
        if _m:
            _joge_sibs.setdefault(_joge_key(_r), {})[_m] = _r


def joge_volumes(r):
    """このrowが上下巻セットの一員なら [(number, label, row), ...] を返す。単独/非該当は None。
    ★上(前編)が揃っていなければ None=従来どおり保留(単巻先行登録禁止)。"""
    if not _joge_mark(r.get("title")):
        return None
    sibs = _joge_sibs.get(_joge_key(r)) or {}
    if len(sibs) < 2 or not ({"上", "前編"} & set(sibs)):
        return None
    order = sorted(sibs.items(), key=lambda kv: _JOGE_ORDER[kv[0]])
    return [(i + 1, _JOGE_LABEL[mk], rr) for i, (mk, rr) in enumerate(order)]


def _vol_entry(num, isbn_, rd_, cover_raw, label=None):
    o = {"number": num, "asin": None, "isbn13": isbn_,
         "cover_url": (cover_raw if "noimage" not in str(cover_raw or "") else None) or _real_cover(isbn_, _COVERS, _rk_live, _RKENV),
         "release_date": rd_}
    if label:
        o["volume_label"] = label      # ★上下巻の表示名(lib/schema.ts 対応済・promoteが搬送)
    return o


def _volumes_for(r, isbn, rd):
    """★上下巻セットなら兄弟を1頁にまとめる(2026-09-04)。単独なら従来どおり1巻。"""
    js = joge_volumes(r)
    if not js:
        return [_vol_entry(r.get("_vol") or 1, isbn, rd, r.get("cover"))]
    out = []
    for num, label, rr in js:
        _ym = str(rr.get("ym") or "")
        _rd = (_ym + (f"-{rr['day']:02d}" if rr.get("day") else "")) or None
        out.append(_vol_entry(num, str(rr.get("isbn")), _rd, rr.get("cover"), label))
    return out


_joge_done = set()
for klass, r in targets:
    raw_title = r.get("title")
    # ★上下セットは代表行(上/前編)だけ生成する。他の兄弟は同じ頁の巻として入るのでskip(2026-09-04)
    _js = joge_volumes(r)
    if _js:
        _gk = _joge_key(r)
        if _gk in _joge_done or str(r.get("isbn")) != str(_js[0][2].get("isbn")):
            continue
        _joge_done.add(_gk)
    ym = r.get("ym")
    isbn = r.get("isbn")
    auths = author_names(r.get("author"))
    akanas = author_names(r.get("authorKana"))
    if _scope_out(raw_title):                                     # カレンダー/画集/グッズ=掲載外
        holds.append((klass, isbn, raw_title, "scope外(非漫画)")); continue
    if _criticism(r):                                             # ★評論/研究書疑い(2026-09-04 手塚SFの世界型)
        holds.append((klass, isbn, raw_title, "評論/研究書疑い(コミックレーベル無し+章立てcaption)→人裁定")); continue
    base, subtitle, prov = _clean_title(raw_title)
    if prov:                                                      # (仮)=題未確定
        holds.append((klass, isbn, raw_title, "(仮)題未確定")); continue
    title = base
    kana = _clean_kana(r.get("titleKana"), subtitle, base)        # 楽天ヨミのみ・捏造(漢字/汚染)はNone=hold。base=長題32字誤hold回避
    if kana is None:
        holds.append((klass, isbn, base, "楽天ヨミ無し/汚染=捏造回避hold(NDL照合キューへ)")); continue
    if not (title and ym and isbn and len(isbn) == 13 and auths):
        holds.append((klass, isbn, title, "必須欠け(author/ym)")); continue
    # ★著者=出版社名(2026-09-02 みにくい小鳥の婚約=楽天 author「小学館」型): 楽天が著者未登録時に出版社名を入れてくる。
    #   著者不明=捏造せず hold(発売後の楽天再訪/NDLで埋まってから通す)。
    _pubn = _ud.normalize("NFKC", str(r.get("publisher") or "")).replace(" ", "")
    if all(_pubkey(a) or _ud.normalize("NFKC", a).replace(" ", "") == _pubn for a in auths):
        holds.append((klass, isbn, title, f"著者=出版社名({'/'.join(auths)})=著者不明(楽天placeholder)→保留")); continue
    # ★slugはclean済みkanaから作る(生titleKanaは末尾に巻数読み「イチ」等が残りslug汚染=channel-vampire-ichi型 2026-08-31)
    slug = MANUAL_SLUG.get(str(isbn)) or _make_slug(base, kana, existing)
    if MANUAL_SLUG.get(str(isbn)) and slug in existing:
        holds.append((klass, isbn, title, f"手動slug衝突 {slug}")); continue
    if not slug:
        slug = _make_slug(base, kana)
        if not slug:
            holds.append((klass, isbn, title, "slug生成不可(→ data/seeds/preorder-slug-manual.tsv に人が裁いたslugを置いて --isbn 再生成)")); continue
        # ★同名異作品の衝突=規則「-姓+発売年」(chuka-ichiban-manabe1993型)。裸の-西暦は禁止(shion-2026事故 2026-07-14)
        _ak = author_names(r.get("authorKana"))
        _sr = re.sub(r"[^a-z0-9]", "", kana2romaji(_ak[0].split()[0])) if _ak else ""
        if not _sr:
            holds.append((klass, isbn, title, "slug衝突(著者ヨミ無し=姓suffix不可hold)")); continue
        slug = f"{slug}-{_sr}{ym[:4]}"
        if slug in existing:
            holds.append((klass, isbn, title, f"slug衝突 {slug}")); continue
    existing.add(slug)
    romaji = slug.replace("-", " ")
    rd = ym + (f"-{r['day']:02d}" if r.get("day") else "")
    authors = []
    for i2, name in enumerate(auths):
        a = {"name": name, "role": "writer_artist"}  # schema必須。共著の原作/作画分離はNDL照合時に是正
        if i2 < len(akanas) and akanas[i2]:
            a["kana"] = akanas[i2]
        authors.append(a)
    doc = {
        "slug": slug,
        "title": title,
        "title_kana": kana.replace(" ", "").replace("　", ""),
        "title_romaji": romaji.replace("-", " "),
        "authors": authors,
        # ★トップレベルpublisher=edition社キー(2026-07-09 索引skip恒久修正: Noneだと表示ガードでskip)。未登録キーなら None のまま(=skipは正=publisher未整備signal)
        "publisher": (_pubkey(r.get("publisher")) if _pubkey(r.get("publisher")) in _pubs else None),
        "publishers": ([_pubkey(r.get("publisher"))] if _pubkey(r.get("publisher")) in _pubs else []),
        "year_ended": None, "year_started": int(ym[:4]),
        "status": "ongoing",
        "demographic": DEMO.get(r.get("subgenre")),  # ★不明はNone(旧"other"廃止2026-07-13。schemaはnullable化済み)
        "genres": [],
        "editions": [{
            "type": "standard", "label": "通常版", "publisher": (_pubkey(r.get("publisher")) or r.get("publisher")), "imprint": r.get("seriesName") or "",
            "volumes": _volumes_for(r, isbn, rd),
        }],
        "_preorder_draft": {"class": klass, "added_at": TODAY, "source": "rakuten-preorder",
                            "rakuten_caption": (r.get("caption") or None),  # ★あらすじ捕捉(genre/catch/synopsis元・書影と同じharvestで取れる=捨てない 2026-07-09)
                            "note": "予約②③previewドラフト。本番化はユーザ確認後。ヨミ=楽天仮(NDL照合待ち)。genre=captionからprovisional付与"},
    }
    yaml.dump(doc, open(f"{ROOT}/.preview-data/manga/{slug}.yml", "w", encoding="utf-8"),
              allow_unicode=True, sort_keys=False, width=200)
    # ★drafts台帳にも書く(2026-07-17): incrementの「過去draft題」網は .cache/preorders/drafts*/ を読む。
    #   A系(gen-preview)はpreview-made-*.jsonにしか記録せず、後続巻の新ISBNで同作が再登場した時に
    #   網から漏れていた(B系_distill_dailyだけがdrafts/を書く片肺)。同じdocをそのまま複製。
    os.makedirs(f"{ROOT}/.cache/preorders/drafts", exist_ok=True)
    yaml.dump(doc, open(f"{ROOT}/.cache/preorders/drafts/{slug}.yml", "w", encoding="utf-8"),
              allow_unicode=True, sort_keys=False, width=200)
    made.append(slug)
    pend_lines.append(json.dumps({"isbn": isbn, "slug": slug, "title": title, "title_kana": kana,
                                  "authors": auths, "author_kanas": akanas, "added_at": TODAY,
                                  "status": "pending"}, ensure_ascii=False))

with open(PEND, "a", encoding="utf-8") as f:
    for ln in pend_lines:
        f.write(ln + "\n")
with open(TRIAGE, "a", encoding="utf-8") as f:
    for klass, isbn, title, why in holds:
        f.write(f"{klass}_hold\t{isbn}\t\t{str(title)[:40]}\t\t\t{why}\n")
json.dump(made, open(f"{ROOT}/.cache/preorders/preview-made-{WHICH}.json", "w"))
print(f"{WHICH}: 生成{len(made)} / 保留{len(holds)} / NDL照合キュー+{len(pend_lines)}")
