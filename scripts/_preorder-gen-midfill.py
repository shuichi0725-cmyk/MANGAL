#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""予約④: 途中巻でページ無し(取りこぼし作品)のpreviewドラフト生成 (= 2026-07-06)

classified.json の ex_mid を、楽天キャッシュ(isbn-title-map)で全巻回収してから生成する
(=「単巻先行登録禁止・全巻回収が先」protocolの機械適用)。
ゲート: kana/author/ym必須 / 回収巻が1..Nの80%以上連続 / slug衝突なし。
キャッシュで揃わない作品は保留(worklist)=liveハーベストは別途。
"""
import json, os, re, sys, datetime, unicodedata
sys.stdout.reconfigure(encoding="utf-8")
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today().isoformat()

# gen-previewのローマ字化/strip関数を流用(import)
import importlib.util
spec = importlib.util.spec_from_file_location("genprev", os.path.join(ROOT, "scripts", "_preorder-gen-preview.py"))
# ファイル実行を避けるため必要関数だけ再定義(軽量コピー)
exec(open(os.path.join(ROOT, "scripts", "_preorder-gen-preview.py"), encoding="utf-8").read().split("# 既存slug集合")[0])

def norm(t):
    t = unicodedata.normalize("NFKC", str(t or ""))
    return re.sub(r"[\s　・!！?？:：〜~\-＆&。、．.『』「」]", "", t).lower()

VOLP = re.compile(r"[（(]\s*(\d{1,3})\s*[)）]\s*$|\s+(\d{1,3})\s*$|第\s*(\d{1,3})\s*巻\s*$")
def split_vol(title):
    t = unicodedata.normalize("NFKC", str(title or "")).strip()
    m = VOLP.search(t)
    if m:
        n = next((g for g in m.groups() if g), None)
        return norm(VOLP.sub("", t)), (int(n) if n else None)
    return norm(t), None

tm = json.load(open(f"{ROOT}/.cache/isbn-title-map.json", encoding="utf-8"))
import sqlite3, gzip
_DBV2 = sqlite3.connect(f"{ROOT}/.cache/db-v2.sqlite")   # ★回収先行巻の発売日引き当て(種2)
# ★書影の実URL源(構築禁止): covers seed → 楽天API
from _preorder_draft_lib import real_cover as _real_cover
from _preorder_draft_lib import real_cover_and_date as _real_cover_date
try:
    from _lookup import rakuten_live as _rk_live, _env as _rk_env
    _RKENV = _rk_env()
except Exception:
    _rk_live = _RKENV = None
_COVERS = {}
try:
    for _l in gzip.open(f"{ROOT}/data/seeds/covers.jsonl.gz", "rt", encoding="utf-8"):
        _r = json.loads(_l); _COVERS[_r.get("isbn13") or _r.get("isbn")] = _r.get("url") or _r.get("cover")
except Exception:
    pass
iidx = json.load(open(f"{ROOT}/.cache/isbn-page-index.json", encoding="utf-8"))
# 題base→ [(vol, isbn)] の逆引き(キャッシュ全巻回収)
by_base = {}
for ib, t in tm.items():
    if not ib.startswith("9784"):
        continue
    b, v = split_vol(t)
    if v is not None:
        by_base.setdefault(b, {}).setdefault(v, ib)

existing = set()
idx = json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8"))
si = idx["f"].index("slug")
for r in idx["d"]:
    existing.add(r[si])
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
    return [x.strip() for x in re.split(r"[/,、;；]", str(s or "")) if x.strip()]

cls = json.load(open(f"{ROOT}/.cache/preorders/classified.json", encoding="utf-8"))
made, holds, pend = [], [], []
VOLSTRIP = re.compile(r"[\s　]*(?:[（(]\s*\d{1,3}\s*[)）]|第\s*\d{1,3}\s*巻|1)\s*$")  # ★裸数字は1のみ(N≥2を削ると「その6」の6等を破壊し誤1巻化=2026-07-06事故)
from _preorder_title_lib import split_title as _split_title, strip_kana_vol as _strip_kana_vol

def strip_vol_disp(t):
    """★分離器に委譲(2026-07-06 ユーザ裁定): タイトル/巻数/副題を正しく分解しclean題を返す"""
    r = _split_title(t)
    return r["clean"]

def _old_strip_vol_disp(t):
    t2 = VOLSTRIP.sub("", str(t or "").strip())
    return t2 if t2 else str(t or "").strip()

# ★2026-07-09 整形は _preorder_draft_lib に一本化(gen-previewと同じ規律=捏造回避)
from _preorder_draft_lib import clean_title as _clean_title, clean_kana as _clean_kana, make_slug as _make_slug, scope_out as _scope_out
for r in cls["ex_mid"]:
    if _scope_out(r.get("title")):
        holds.append((r.get("isbn"), r.get("title"), "scope外(非漫画)")); continue
    _bt, _sub, _prov = _clean_title(r.get("title"))
    if _prov:
        holds.append((r.get("isbn"), r.get("title"), "(仮)題未確定")); continue
    title = _bt
    kana = _clean_kana(r.get("titleKana"), _sub, _bt)            # 楽天ヨミのみ・捏造(漢字/汚染)はNone=hold。base=長題32字誤hold回避
    ym = r.get("ym")
    auths = author_names(r.get("author"))
    akanas = author_names(r.get("authorKana"))
    if kana is None:
        holds.append((r.get("isbn"), title, "楽天ヨミ無し/汚染=捏造回避hold")); continue
    if not (title and ym and auths):
        holds.append((r.get("isbn"), title, "必須欠け")); continue
    base = r.get("_base") or split_vol(r.get("title"))[0]
    vols_map = dict(by_base.get(base) or {})
    vols_map[r["_vol"]] = r["isbn"]  # 予約巻自身
    # 既に他頁で描画中のISBNが混ざる=別作品の可能性→その巻は除外
    vols_map = {v: ib for v, ib in vols_map.items() if ib not in iidx or ib == r["isbn"]}
    ns = sorted(vols_map)
    if not ns or ns[0] != 1 or len(ns) < 0.8 * ns[-1] or len(ns) < 2:
        holds.append((r.get("isbn"), title, f"全巻回収不成立 vols={ns[:6]}{'..' if len(ns)>6 else ''}")); continue
    slug = _make_slug(base, r.get("titleKana"))
    if not slug:
        holds.append((r.get("isbn"), title, "slug生成不可")); continue
    romaji = slug.replace("-", " ")
    if slug in existing:
        slug = f"{slug}-{ym[:4]}"
        if slug in existing:
            holds.append((r.get("isbn"), title, f"slug衝突 {slug}")); continue
    existing.add(slug)
    volumes = []
    for v in ns:
        ib = vols_map[v]
        if ib == r["isbn"]:                       # 予約巻自身=harvestから日付
            rd = ym + (f"-{r['day']:02d}" if r.get("day") else "")
        else:                                     # ★回収先行巻=種2から発売日を引く(捨てない・2026-07-09修正)
            _row = _DBV2.execute("SELECT release_date FROM volumes WHERE isbn13=? AND release_date IS NOT NULL", (ib,)).fetchone()
            rd = _row[0] if _row and _row[0] else None
        # 書影=予約巻はharvest実URL、回収巻/harvest空は covers seed→楽天API 実URL(★構築禁止=推測不可)
        # ★日付が種2未収載の回収巻は、cover照会と同一の楽天応答からsalesDateも取る(捨てない 2026-07-11)
        cov = (r.get("cover") if ib == r["isbn"] and "noimage" not in str(r.get("cover") or "") else None)
        if not cov or rd is None:
            _c2, _d2 = _real_cover_date(ib, _COVERS, _rk_live, _RKENV, need_date=(rd is None))
            cov = cov or _c2
            rd = rd or _d2
        volumes.append({"number": v, "asin": None, "isbn13": ib, "cover_url": cov, "release_date": rd})
    authors = []
    for i2, name in enumerate(auths):
        a = {"name": name, "role": "writer_artist"}  # schema必須。共著の原作/作画分離はNDL照合時に是正
        if i2 < len(akanas) and akanas[i2]:
            a["kana"] = akanas[i2]
        authors.append(a)
    doc = {"slug": slug, "title": title,
           "title_kana": kana.replace(" ", "").replace("　", ""),
           "title_romaji": romaji.replace("-", " "),
           "authors": authors, "publisher": (_pk if (_pk:=_pubkey(r.get("publisher"))) in _pubs else None), "publishers": ([_pk] if _pk in _pubs else []), "year_ended": None, "year_started": int(ym[:4]), "status": "ongoing",
           "demographic": DEMO.get(r.get("subgenre")) or "other",  # schema必須(null不可) "genres": [],
           "editions": [{"type": "standard", "label": "通常版", "publisher": (_pubkey(r.get("publisher")) or r.get("publisher")),
                          "imprint": r.get("seriesName") or "", "volumes": volumes}],
           "_preorder_draft": {"class": "ex_mid", "added_at": TODAY, "source": "rakuten-preorder",
                               "rakuten_caption": (r.get("caption") or None),  # ★あらすじ捕捉(genre/catch/synopsis元 2026-07-09)。vol1あらすじはcover API時に上書き捕捉可
                               "note": f"取りこぼし作品(予約巻v{r['_vol']}発見→キャッシュ全巻回収{len(ns)}冊)。過去巻の日付/確証は本番化前にNDL等で要補完"}}
    yaml.dump(doc, open(f"{ROOT}/.preview-data/manga/{slug}.yml", "w", encoding="utf-8"),
              allow_unicode=True, sort_keys=False, width=200)
    made.append(slug)
    pend.append(json.dumps({"isbn": r["isbn"], "slug": slug, "title": title, "title_kana": kana,
                            "authors": auths, "author_kanas": akanas, "added_at": TODAY,
                            "status": "pending"}, ensure_ascii=False))

with open(f"{ROOT}/data/seeds/rakuten-kana-pending.jsonl", "a", encoding="utf-8") as f:
    for ln in pend:
        f.write(ln + "\n")
with open(f"{ROOT}/docs/production-diagnostics/preorder-triage.tsv", "a", encoding="utf-8") as f:
    for isbn, title, why in holds:
        f.write(f"ex_mid_hold\t{isbn}\t\t{str(title)[:40]}\t\t\t{why}\n")
json.dump(made, open(f"{ROOT}/.cache/preorders/preview-made-exmid.json", "w"))
print(f"ex_mid: 生成{len(made)} / 保留{len(holds)}(キャッシュで全巻揃わず等)")
