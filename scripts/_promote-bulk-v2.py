"""step G: db-v2.sqlite + series-supplement-v2.yml から MANGAL yml を 生成。

v1 scope: 既存 56 yml に 対応する series のみ regenerate
  - data/manga/*.yml の slug を 起点に db-v2 で 検索
  - 新 schema (= subtitle, subtitle_kana, volume_label 等) で 出力
  - data/manga.v2/<slug>.yml に書き出し (= 旧 data/manga は 不変)
  - 後で diff で 比較

filter (= step A/B、 「本編以外は極力表示しない」):
  - step A: 同 qid series で 「親 / 子」 関係 検出
            親 = title が prefix で 親 has MORE volumes → 子 is spinoff
  - step B: 本編 series 内の edition filter
            keep: standard / bunkobon / wideban / kanzenban / shinsoban / aizoban
            drop: anime / other / renewal
            drop imprint: 'My first big%' / '%コンビニ%' / '%増刊%'
            spinoff series は max(release_date) >= CUTOFF_YEAR なら keep
"""

import datetime
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import yaml

# 高速 YAML loader (= libyaml の CSafeLoader、 なければ pure-python に fallback)。
# series-supplement-v2.yml (= 92万行) を pure-python で読むと数分かかるため。
# parse 結果は yaml.safe_load と完全同一。
try:
    from yaml import CSafeLoader as _YLoader
except ImportError:  # libyaml 無し環境
    from yaml import SafeLoader as _YLoader


def _yload(f):
    return yaml.load(f, Loader=_YLoader)


ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
# ★フリガナ補正 seed (= 3ソースconsensus: NDL公式 / 種3-AI / 種2-MADB)。 種2/種3とも
# 誤り(副題/著者名/英字混入)だった key を NDL ground-truth 等で補正。 title_kana を
# ★最優先(series_row[種2]/src_yml[種3]より先)で読む。 blast radius=本file記載keyのみ。
FURIGANA_CORR = ROOT / "data" / "seeds" / "furigana-corrections.yml"
FURIGANA_FILL = ROOT / "data" / "seeds" / "title-kana-fill.yml"  # MADB由来 kana 補完(欠落埋め)
SRC_DIR = ROOT / "data" / "manga"
OUT_DIR = ROOT / "data" / "manga.v2"
MERGE_YML = ROOT / "data" / "seeds" / "series-merge.yml"
# 自動生成 merge (= 著者集合+title、 scripts/_gen-author-set-merges.py)。 JSON で持つ
# (= 約1万 group の PyYAML パースは遅い、 json.load は <1秒)。 hand yaml と両方 load し
# 同 sid は hand 版優先。 docs/series-fragmentation-analysis.md。
AUTO_MERGE_JSON = ROOT / "data" / "seeds" / "series-merge-auto.json"
ADULT_OVERRIDES = ROOT / "data" / "seeds" / "adult-overrides.yml"
# ★画集 = 漫画と別カテゴリ・別ストリーム (art-books.v2)。 設計 docs/art-book-display-design.md。
ART_BOOKS_YML = ROOT / "data" / "seeds" / "art-books.yml"
ART_BOOK_EXCLUDE_YML = ROOT / "data" / "seeds" / "art-book-exclude-isbn.yml"
ART_BOOK_SEGMENTED_YML = ROOT / "data" / "seeds" / "art-book-furigana-segmented.yml"
# ★書影を promote 内で直接貼る (= 旧 _apply-covers-stage.py の 66k 再走を廃止=毎回-50分)。
# covers.jsonl.gz (isbn13→cover_url) を lazy load し clean_vol で null cover を埋める。
COVERS_GZ = ROOT / "data" / "seeds" / "covers.jsonl.gz"

# ★特装版是正 seed(案B: 通常版を主に・特装はvariants併存)。 6ファイルを順に読み後勝ち。
#   旧 _special_edition_fix_apply.py の直接パッチはフルpromoteで消えた(2026-07-03発覚)→promote内蔵で恒久化。
_SPECIAL_FIX = None
def _special_fix_map():
    global _SPECIAL_FIX
    if _SPECIAL_FIX is None:
        _SPECIAL_FIX = {}
        import yaml as _y
        for name in ("special-edition-fix.yml", "special-edition-fix-b.yml", "special-edition-fix-extra.yml",
                     "special-edition-fix-ndl.yml", "special-edition-fix-redo.yml", "special-edition-fix-redo2.yml"):
            p = ROOT / "data" / "seeds" / name
            if not p.exists():
                continue
            d = _y.safe_load(p.read_text(encoding="utf-8")) or {}
            for c in (d.get("corrections") or []):
                si = str(c.get("special_isbn") or "")
                ni = str(c.get("normal_isbn") or "")
                # ★出版社コード跨ぎペアは無視(臨場→王様ゲーム型の誤爆ガード 2026-07-03。seed側も除去済だが二重防御)
                if len(si) == 13 and len(ni) == 13 and si[4:6] != ni[4:6]:
                    continue
                if si:
                    _SPECIAL_FIX[si] = c
    return _SPECIAL_FIX

_SPECIAL_BY_NORMAL = None
def _special_by_normal():
    global _SPECIAL_BY_NORMAL
    if _SPECIAL_BY_NORMAL is None:
        _SPECIAL_BY_NORMAL = {}
        for si, c in _special_fix_map().items():
            ni = str(c.get("normal_isbn") or "")
            if ni:
                _SPECIAL_BY_NORMAL[ni] = c
    return _SPECIAL_BY_NORMAL

_COVERS = None
def _cover_for(isbn13):
    global _COVERS
    if _COVERS is None:
        import gzip as _gz
        _COVERS = {}
        if COVERS_GZ.exists():
            with _gz.open(COVERS_GZ, "rt", encoding="utf-8") as _f:
                for _ln in _f:
                    try:
                        _o = json.loads(_ln); _COVERS[_o["isbn13"]] = _o["cover_url"]
                    except Exception:
                        pass
    if not isbn13:
        return None
    return _norm_cover_ex(_COVERS.get(str(isbn13).replace("-", "")))


# ★書影の _ex 正規化(2026-07-25): 楽天サムネは「1枚のマスター + _ex サイズ指定」で、
#   APIの largeImageUrl(=_ex=200x200) は最大ではない。300 にするとマスター原寸まで返り
#   (新刊 141x200 → 211x300)、マスターが小さい古書は据置き=容量も増えない。
#   seed(covers.jsonl.gz)は200x200で焼かれているので、書き出し時にここで揃える。
COVER_EX = "?_ex=300x300"


def _norm_cover_ex(url):
    if not url or not url.startswith("https://thumbnail.image.rakuten.co.jp/"):
        return url
    base, _, q = url.partition("?")
    if q and not q.startswith("_ex="):
        return url                      # 想定外クエリは触らない
    return base + COVER_EX

# ★発売日 精密化 seed (= release-date-fill.jsonl。 2026-07-18 結線=素材ハーベスト①)。
#   楽天salesDate由来の年月日フル値。 収集時に「現在値が空 or 新値のprefix」ゲート済みだが、
#   promote時にも同条件を再チェック=純粋な精密化(年月→年月日)以外は絶対に書かない。
DATE_FILL_SEED = ROOT / "data" / "seeds" / "release-date-fill.jsonl"
_DATE_FILL = None
def _date_fill_for(isbn13):
    global _DATE_FILL
    if _DATE_FILL is None:
        _DATE_FILL = {}
        if DATE_FILL_SEED.exists():
            with DATE_FILL_SEED.open(encoding="utf-8") as _f:
                for _ln in _f:
                    try:
                        _o = json.loads(_ln)
                        if re.match(r"^\d{4}-\d{2}-\d{2}$", str(_o.get("date") or "")):
                            _DATE_FILL[str(_o["isbn"])] = _o["date"]
                    except Exception:
                        pass
    if not isbn13:
        return None
    return _DATE_FILL.get(str(isbn13).replace("-", ""))

# ★巻説明 seed (= volume-desc-ja.jsonl。 2026-07-20 結線=skill volume-desc)。
#   単行本(巻)単位の説明文。 isbn13キーで clean_vol の書込直前に充填(書影と同じ最終pass)。
#   標準版+版バージョン(versions[])の両方が clean_vol を通るので1箇所で両対応。
VOLDESC_SEED = ROOT / "data" / "seeds" / "volume-desc-ja.jsonl"
_VOLDESC = None
def _desc_for(isbn13):
    global _VOLDESC
    if _VOLDESC is None:
        _VOLDESC = {}
        if VOLDESC_SEED.exists():
            with VOLDESC_SEED.open(encoding="utf-8") as _f:
                for _ln in _f:
                    try:
                        _o = json.loads(_ln)
                        if _o.get("isbn13") and _o.get("desc"):
                            _VOLDESC[str(_o["isbn13"])] = _o["desc"]
                    except Exception:
                        pass
    if not isbn13:
        return None
    return _VOLDESC.get(str(isbn13).replace("-", ""))

def _norm_date(s):
    """release_date を schema形式(YYYY / YYYY-MM / YYYY-MM-DD)へ正規化。
    NDL生形式(2014.8 / 1997-9 / 全角２００５．４)がZod検証(^\\d{4}(-\\d{2}(-\\d{2})?)?$)で
    落ちて頁が404化するのを恒久防止。 不正で解釈不能は None。"""
    if s is None:
        return None
    import unicodedata as _u
    s = _u.normalize("NFKC", str(s)).strip().replace(".", "-").replace("/", "-")
    m = re.match(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", s)
    if not m:
        return None
    y = m.group(1)
    if not m.group(2):
        return y
    if not m.group(3):
        return f"{y}-{m.group(2).zfill(2)}"
    return f"{y}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"

_ART_BOOK_SEGMENTED: dict | None = None


def get_art_book_segmented() -> dict:
    """series_key -> 分かち書きフリガナ (= slug生成用)。 NDL spaced 由来 (純粋追加・任意)。"""
    global _ART_BOOK_SEGMENTED
    if _ART_BOOK_SEGMENTED is None:
        if ART_BOOK_SEGMENTED_YML.exists():
            d = yaml.safe_load(ART_BOOK_SEGMENTED_YML.read_text(encoding="utf-8")) or {}
            _ART_BOOK_SEGMENTED = d.get("segmented", {}) or {}
        else:
            _ART_BOOK_SEGMENTED = {}
    return _ART_BOOK_SEGMENTED


def _norm_isbn(s) -> str:
    """ISBN13 を数字のみに正規化 (= ハイフン/型ゆれ吸収、 set 突合用)。"""
    return re.sub(r"[^0-9]", "", str(s if s is not None else ""))


def _jp_pub_prefix(s) -> str:
    """日本(978-4)ISBN の ★出版者記号プレフィックスを登録グループ長ルールで正確に返す。
    publisher コードは可変長(2-7桁)のため 固定長 slice では大手(講談社06等)を誤分割する。
    978-4 群範囲: 0-1→2桁 / 2-6→3桁 / 70-84→4桁 / 85-89→5桁 / 900-949→6桁 / 950-999→7桁。
    例: 講談社=978406 / リイド社系=97847683 / 双葉社=9784575。 dedup の出版者線判定に使う。"""
    i = _norm_isbn(s)
    if len(i) < 13 or not i.startswith("9784"):
        return i[:7]
    r = i[4:]
    if r[0] in "01": ln = 2
    elif r[0] in "23456": ln = 3
    elif "70" <= r[:2] <= "84": ln = 4
    elif "85" <= r[:2] <= "89": ln = 5
    elif "900" <= r[:3] <= "949": ln = 6
    else: ln = 7
    return i[:4 + ln]


def load_art_books() -> dict[str, dict]:
    """series_key -> {artist, adult, multi_artist}。 画集 (= 漫画とは別カテゴリ)。"""
    if not ART_BOOKS_YML.exists():
        return {}
    data = yaml.safe_load(ART_BOOKS_YML.read_text(encoding="utf-8")) or {}
    out: dict[str, dict] = {}
    for e in data.get("art_books", []) or []:
        sk = e.get("series_key")
        if not sk:
            continue
        out[sk] = {
            "artist": e.get("artist") or "",
            "adult": bool(e.get("adult")),
            "multi_artist": bool(e.get("multi_artist")),
            # ★任意 override: MADB が NDL 題を誤 parse した画集の是正用 (種2/種3不変)。
            #   例: 「S : 高橋ツトム画集」→ MADB title「S」→ ここで正題に上書き。
            "title": e.get("title"),
            "title_kana": e.get("title_kana"),
        }
    return out


def load_art_book_exclude_isbn() -> set[str]:
    """漫画 series に混在した画集巻の ISBN13 集合 (= 漫画の巻列から除外)。"""
    if not ART_BOOK_EXCLUDE_YML.exists():
        return set()
    data = yaml.safe_load(ART_BOOK_EXCLUDE_YML.read_text(encoding="utf-8")) or {}
    return {_norm_isbn(e.get("isbn13")) for e in data.get("exclude_isbn", []) or [] if e.get("isbn13")}


_ART_BOOK_EXCLUDE_ISBN: set[str] | None = None


def get_art_book_exclude_isbn() -> set[str]:
    global _ART_BOOK_EXCLUDE_ISBN
    if _ART_BOOK_EXCLUDE_ISBN is None:
        _ART_BOOK_EXCLUDE_ISBN = load_art_book_exclude_isbn()
    return _ART_BOOK_EXCLUDE_ISBN


_REL_DATE_SUPP: dict | None = None
def get_release_date_supplement() -> dict:
    """ISBN13(数字) → 発売日(YYYY-MM/YYYY) の補完 map (= NDL由来、 release_date欠落巻用)。
    ★種2のrelease_dateがNone/空の時だけこの seed で上書き(dedup日付tie-break+表示の正規化)。
    data/seeds/release-date-supplement.jsonl (純粋追加・種2不変)。 date=null行はskip。"""
    global _REL_DATE_SUPP
    if _REL_DATE_SUPP is None:
        _REL_DATE_SUPP = {}
        p = ROOT / "data" / "seeds" / "release-date-supplement.jsonl"
        if p.exists():
            for line in p.open(encoding="utf-8"):
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("date") and d.get("isbn13"):
                    _REL_DATE_SUPP[_norm_isbn(d["isbn13"])] = d["date"]
    return _REL_DATE_SUPP


_REL_DATE_OVERRIDE = None


def get_release_date_override() -> dict:
    """ISBN13 → 発売日 の ★強制上書き map (= 発売日逆行是正、 種2に値が有っても上書く)。
    補完(get_release_date_supplement)は『種2が空の時だけ』だが、 こちらは再版日を初版日へ
    正規化する用途なので 種2値が有っても優先する。
    data/seeds/release-date-override.jsonl (純粋追加・種2不変・可逆=行削除で戻る)。"""
    global _REL_DATE_OVERRIDE
    if _REL_DATE_OVERRIDE is None:
        _REL_DATE_OVERRIDE = {}
        p = ROOT / "data" / "seeds" / "release-date-override.jsonl"
        if p.exists():
            for line in p.open(encoding="utf-8"):
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("date") and d.get("isbn13"):
                    _REL_DATE_OVERRIDE[_norm_isbn(d["isbn13"])] = d["date"]
    return _REL_DATE_OVERRIDE


_COVER_OVERRIDE = None


def get_cover_override() -> dict:
    """ISBN13 → cover_url の ★強制上書き map (= release-date-override と同型)。
    covers.jsonl.gz(seed)は『null の時だけ』充填だが、 こちらは種2に書影が有っても優先する
    (= 例: 頁全体をKobo装丁で統一したいのに1巻だけ種2の紙gifが勝つ、 の是正。 2026-07-12 ライ26巻)。
    data/seeds/cover-override.jsonl (純粋追加・種2不変・可逆=行削除で戻る)。"""
    global _COVER_OVERRIDE
    if _COVER_OVERRIDE is None:
        _COVER_OVERRIDE = {}
        p = ROOT / "data" / "seeds" / "cover-override.jsonl"
        if p.exists():
            for line in p.open(encoding="utf-8"):
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("cover_url") and d.get("isbn13"):
                    _COVER_OVERRIDE[_norm_isbn(d["isbn13"])] = d["cover_url"]
    return _COVER_OVERRIDE


_EDITION_CANONICAL = None


def get_edition_canonical() -> dict:
    """版分離 canonical seed (= data/seeds/edition-canonical/*.yml) → {slug: seed}。
    ★版混在シリーズ(golgo/釣りバカ等)の standard/compact 版を Wikipedia確定の
    vol→ISBN→初版日 で再構築する権威seed。 db-v2クラスタの版混在汚染を上書き是正。
    各seed: {slug, canonical_label, volumes:[{number,isbn13,release_date}],
             compact_edition?:{label, volumes:[...]}}。 cover_url は後段 cover stage が ISBN で充填。"""
    global _EDITION_CANONICAL
    if _EDITION_CANONICAL is None:
        _EDITION_CANONICAL = {}
        d = ROOT / "data" / "seeds" / "edition-canonical"
        if d.exists():
            for p in sorted(d.glob("*.yml")):
                try:
                    with p.open(encoding="utf-8") as f:
                        s = _yload(f)
                    if s and s.get("slug"):
                        _EDITION_CANONICAL[s["slug"]] = s
                except Exception:
                    continue
    return _EDITION_CANONICAL


def get_extra_editions() -> dict:
    """★版付加 seed (= data/seeds/extra-editions.yml → {slug: [edition,...]})。
    既存版に一切触れず、指定した版を頁末尾に追加する軽量機構(2026-07-21 手塚全集版の可視化)。
    canonical(全面再構築=外部権威必須)/separate_editions(全imprint分離=古典で版爆発)の
    どちらも過剰な「同type統合で沈んだ特定版を1本だけ足す」ケース用。
    ISBNが頁内の既存版と重複する巻は自動skip(冪等・ダブリ防止)。"""
    p = ROOT / "data" / "seeds" / "extra-editions.yml"
    if not p.exists():
        return {}
    with p.open(encoding="utf-8") as f:
        doc = _yload(f) or {}
    return doc.get("extra") or {}


def apply_extra_editions(slug: str, editions: list, extra: dict) -> tuple[list, bool]:
    """slug の extra-editions を editions 末尾へ追加。既存ISBNと重複する巻はskip。"""
    xes = extra.get(slug)
    if not xes:
        return editions, False
    seen = {str(v.get("isbn13")) for e in editions
            for vs in [e.get("volumes") or []] + [vv.get("volumes") or [] for vv in (e.get("versions") or [])]
            for v in vs if v.get("isbn13")}
    added = False
    for xe in xes:
        vols = []
        for v in (xe.get("volumes") or []):
            if str(v.get("isbn13")) in seen:
                continue
            o = {"number": v["number"], "asin": None, "isbn13": v.get("isbn13"),
                 "cover_url": None, "release_date": v.get("release_date")}
            if v.get("title_display"):
                o["title_display"] = v["title_display"]
            vols.append(o)
        if vols:
            editions.append({"type": xe.get("type") or "standard", "label": xe.get("label") or "別版",
                             "publisher": xe.get("publisher"),
                             "imprint": xe.get("imprint") or xe.get("label"), "volumes": vols})
            added = True
    return editions, added


def apply_edition_canonical(slug: str, editions: list, canon: dict) -> list:
    """slug の canonical seed で standard/compact 版を再構築。 他版(文庫等)は温存。
    cover_url=None で出し、 後段 _apply-covers-stage が ISBN で正書影を充填。"""
    s = canon.get(slug)
    if not s:
        return editions
    def mk(vols, label, publisher, imprint, etype):
        def _v(v):
            o = {"number": v["number"], "asin": None, "isbn13": v.get("isbn13"),
                 "cover_url": None, "release_date": v.get("release_date")}
            if v.get("volume_label"):  # ★上下巻対応(2026-07-04): seedのvolume_labelを搬送
                o["volume_label"] = v["volume_label"]
            return o
        return {"type": etype, "label": label, "publisher": publisher, "imprint": imprint,
                "volumes": [_v(v) for v in (vols or [])]}
    # 既存 standard の publisher を継承(無ければ seed/None)
    cur_std = next((e for e in editions if e.get("type") == "standard"), None)
    pub = (cur_std or {}).get("publisher") or s.get("publisher")
    out = []
    out.append(mk(s.get("volumes"), s.get("canonical_label") or "通常版", pub,
                  s.get("canonical_label") or (cur_std or {}).get("imprint"), "standard"))
    # ★刷タブ(2026-07-04 うる星復旧): 同冊数の別カバー刷(新装版等)を standard の versions[] に畳む
    #   ([[urusei_version_display_rules]]。 旧 _regroup-versions.py 直接パッチは非durableで消えた→canonical結線)
    if s.get("versions"):
        def _vv(v):
            o = {"number": v["number"], "asin": None, "isbn13": v.get("isbn13"),
                 "cover_url": None, "release_date": v.get("release_date")}
            if v.get("volume_label"):
                o["volume_label"] = v["volume_label"]
            return o
        out[0]["versions"] = [
            {"label": vv.get("label") or "別刷", "volumes": [_vv(v) for v in (vv.get("volumes") or [])]}
            for vv in s["versions"]]
    if s.get("compact_edition"):
        ce = s["compact_edition"]
        out.append(mk(ce.get("volumes"), ce.get("label") or "コンパクト版", pub, ce.get("label"), "aizoban"))
    # ★extra_editions(2026-07-04 激マン型=完全版侵食の版分離用): 任意type/labelの追加版を並べる
    for xe in (s.get("extra_editions") or []):
        out.append(mk(xe.get("volumes"), xe.get("label") or "別版", xe.get("publisher") or pub,
                      xe.get("label"), xe.get("type") or "kanzenban"))
    # standard/aizoban 以外の既存版(文庫等)は温存
    # ★suppress_types(2026-07-05 009): canonicalのextraと重複する既存タブを明示除去(opt-in)
    _sup = set(s.get("suppress_types") or [])
    for e in editions:
        if e.get("type") not in ("standard", "aizoban") and e.get("type") not in _sup:
            out.append(e)
    return out


def _load_adult_overrides() -> set[str]:
    """成人判定 手動 override (= force 非adult の series_key 集合)。
    作者signal単独の誤爆を種aで全年齢確認した分 (Phase A、 純粋追加・種2不変)。"""
    if not ADULT_OVERRIDES.exists():
        return set()
    try:
        with ADULT_OVERRIDES.open(encoding="utf-8") as f:
            data = _yload(f) or {}
    except Exception:
        return set()
    out = set()
    for o in data.get("overrides", []) or []:
        if isinstance(o, dict) and o.get("force_adult") is False and o.get("series_key"):
            out.add(str(o["series_key"]))
    return out


def _load_adult_force() -> set[str]:
    """★逆方向: force_adult: true の series_key 集合 (= scoreすり抜け成年の per-case 除外)。
    穴の型: adult_publisher signal が imprint文字列内の社名一致のみで、成年専業社の
    ブランドimprint(バベルコミックス等)が score=0 で素通りする (獣耳のリコリス 2026-07-11)。"""
    if not ADULT_OVERRIDES.exists():
        return set()
    try:
        with ADULT_OVERRIDES.open(encoding="utf-8") as f:
            data = _yload(f) or {}
    except Exception:
        return set()
    return {str(o["series_key"]) for o in (data.get("overrides") or [])
            if isinstance(o, dict) and o.get("force_adult") is True and o.get("series_key")}


ADULT_US_MAP = ROOT / ".cache" / "adult-us-map.json"


def _load_adult_us_map() -> set[str]:
    """adult_us = 種a(v14マッチ)isAdult な series_key 集合(米基準フラグ)。
    `scripts/_build-adult-us-map.py` が生成。 非日本geoで非表示にする本番ページ判定用。
    無ければ空(= adult_us フラグ無しで動作、 graceful)。"""
    if not ADULT_US_MAP.exists():
        return set()
    try:
        return set(json.loads(ADULT_US_MAP.read_text(encoding="utf-8")))
    except Exception:
        return set()


ANILIST_ENRICH_MAP = ROOT / ".cache" / "anilist-enrich-map.json"


def _load_anilist_enrich_map() -> dict:
    """AniList productionization = series_key → {anilist_id, synonyms, genres_anilist, tags}。
    `scripts/_build-anilist-enrich-map.py`(match-v14 + dump)が生成。 promote が join し
    本番 yml の箱(lib/schema.ts)を埋める。 ★種3不変。 無ければ空(graceful)。"""
    if not ANILIST_ENRICH_MAP.exists():
        return {}
    try:
        return json.loads(ANILIST_ENRICH_MAP.read_text(encoding="utf-8"))
    except Exception:
        return {}

# --dry-run = 別 dir に出力 (= 既存上書きしない、 diff 比較用)
if "--dry-run" in sys.argv:
    OUT_DIR = ROOT / "data" / "manga.dryrun"

# --only slug1,slug2 = 指定 slug だけ再生成 (= ターゲット再生成、 高速反復用)。
# 指定時は OUT_DIR 全削除をスキップし、 他ページを温存。
ONLY_SLUGS: set[str] = set()
for _i, _a in enumerate(sys.argv):
    if _a == "--only" and _i + 1 < len(sys.argv):
        ONLY_SLUGS = {s.strip() for s in sys.argv[_i + 1].split(",") if s.strip()}
        # ★安全ガード(2026-07-06 事故): --only指定なのに空(シェル変数の展開ミス等)なら
        #   フルモード(=全66k削除→再生成)に落とさず即abort。全消し誤発動の再発防止。
        if not ONLY_SLUGS:
            print("[abort] --only が空(シェル変数の展開ミス?)。フルpromoteに落とさず終了。", file=sys.stderr)
            sys.exit(2)


def _entry_sids(entry: dict, key_to_sid: dict) -> list[int]:
    """★STEP6: entry の merge_keys (= series_key、 安定) を 現 sid に解決。
    legacy の merge_sids (= raw sid) も後方互換で対応。"""
    out: list[int] = []
    for sk in (entry.get("merge_keys") or []):
        sid = key_to_sid.get(sk)
        if sid is not None:
            out.append(sid)
    for s in (entry.get("merge_sids") or []):  # legacy
        out.append(int(s))
    return out


def load_merge_sids(con: sqlite3.Connection) -> dict[int, list[int]]:
    """merge group → {sid: [all_sids_in_group]} dict 構築。
    auto (JSON, merge_keys) を先に load → hand (YAML) で上書き (= 同 sid は手動版優先)。
    ★STEP6: series_key で持つので db 再build しても解決できる (sid非依存)。"""
    key_to_sid = {sk: sid for sid, sk in con.execute("SELECT id, series_key FROM series")}
    sid_to_group: dict[int, list[int]] = {}
    if AUTO_MERGE_JSON.exists():
        with AUTO_MERGE_JSON.open(encoding="utf-8") as f:
            for entry in (json.load(f).get("merges") or []):
                sids = _entry_sids(entry, key_to_sid)
                for sid in sids:
                    sid_to_group[sid] = sids
    if MERGE_YML.exists():
        with MERGE_YML.open(encoding="utf-8") as f:
            for entry in (_yload(f) or []):
                sids = _entry_sids(entry, key_to_sid)
                if not sids:
                    continue
                for sid in sids:
                    sid_to_group[sid] = sids
    return sid_to_group


def load_merge_edition_types(con: sqlite3.Connection) -> set[int]:
    """merge_edition_types: true の cluster の 全 sid set を 返す (= shinsoban→standard 統合対象)。
    edition-type 統合は hand 版のみ。 ★STEP6: merge_keys/merge_sids 両対応。"""
    if not MERGE_YML.exists():
        return set()
    key_to_sid = {sk: sid for sid, sk in con.execute("SELECT id, series_key FROM series")}
    sids: set[int] = set()
    with MERGE_YML.open(encoding="utf-8") as f:
        for entry in (_yload(f) or []):
            if entry.get("merge_edition_types"):
                sids.update(_entry_sids(entry, key_to_sid))
    return sids


def load_renumber_sids(con: sqlite3.Connection) -> set[int]:
    """renumber: true の cluster の 全 sid set。 ★巻割れ統合(個別題の0巻/extra本が
    1作の連番シリーズ)で、 merge した全巻を発売日順に 1..N 連番付与する対象。
    cm104凍結でシリーズ構造が無い orphan を 著者+題で merge した群に使う。"""
    if not MERGE_YML.exists():
        return set()
    key_to_sid = {sk: sid for sid, sk in con.execute("SELECT id, series_key FROM series")}
    sids: set[int] = set()
    with MERGE_YML.open(encoding="utf-8") as f:
        for entry in (_yload(f) or []):
            if entry.get("renumber"):
                sids.update(_entry_sids(entry, key_to_sid))
    return sids


def load_separate_edition_sids(con: sqlite3.Connection) -> set[int]:
    """separate_editions: true の cluster の 全 sid set。 ★版統合(opt-in):
    通常は 同 type editions を imprint 跨ぎで 1 つに畳む(最古正典表示)が、 この flag を
    付けた群だけ (type × imprint) で 分離 = 別版を 別セクションで並べる(うる星/シートン型)。
    ★blanket化は古典の重版(鉄腕アトム=Akita/KCDX/KPC…)を爆発させるため opt-in 限定。"""
    if not MERGE_YML.exists():
        return set()
    key_to_sid = {sk: sid for sid, sk in con.execute("SELECT id, series_key FROM series")}
    sids: set[int] = set()
    with MERGE_YML.open(encoding="utf-8") as f:
        for entry in (_yload(f) or []):
            if entry.get("separate_editions"):
                sids.update(_entry_sids(entry, key_to_sid))
    return sids


SUPP_YML = ROOT / "data" / "seeds" / "volumes-supplement.yml"
# NDL 自動登録分 (= 種4 auto、 scripts/_register-seed4-ndl.py)。 手動版と両方 load。
SUPP_AUTO_YML = ROOT / "data" / "seeds" / "volumes-supplement-auto.yml"
# OFFSET低巻補完 (= vol1取りこぼし[2,3]始まりを楽天harvestで補完、scripts/_offset_harvest.py)
SUPP_OFFSET_YML = ROOT / "data" / "seeds" / "volumes-supplement-offset.yml"

_VEX_ALL: set | None = None
def _all_excluded_isbns() -> set:
    """volume-exclude.yml の全ISBN集合(slug横断)。 種4番号ガードの先読み用。"""
    global _VEX_ALL
    if _VEX_ALL is None:
        _VEX_ALL = set()
        _p = ROOT / "data" / "seeds" / "volume-exclude.yml"
        if _p.exists():
            for _e in (yaml.safe_load(_p.read_text(encoding="utf-8")) or {}).get("excludes", []):
                if _e.get("isbn13"):
                    _VEX_ALL.add(_norm_isbn(_e["isbn13"]))
    return _VEX_ALL


def load_volumes_supplement(con: sqlite3.Connection) -> dict[int, list[dict]]:
    """volumes-supplement(.yml + -auto.yml + -offset.yml) → {sid: [補完 vol dict, ...]} dict 構築。
    series_keys (= 種2 series.series_key) と qid で 該当 sid を 引く。"""
    cur = con.cursor()
    out: dict[int, list[dict]] = {}
    for path in (SUPP_YML, SUPP_AUTO_YML, SUPP_OFFSET_YML):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            data = _yload(f) or {}
        for entry in (data.get("volumes") or []):
            # 紐付き sid 解決
            sids: set[int] = set()
            for sk in (entry.get("series_keys") or []):
                for r in cur.execute("SELECT id FROM series WHERE series_key=?", (sk,)).fetchall():
                    sids.add(r[0])
            qid = entry.get("qid")
            if qid:
                # ★種2のqid=作者QID(shu2_qid_is_author)。無条件qid一致は「作者の全作品」に巻を
                #   注入する事故になる(うしおととらワイド版が藤田全15作へ滲んだ 2026-07-07)。
                #   → qid一致sidは、entryのseries_keysのname部/title_displayと題が合う時だけ採用。
                _names = {sk.split("name:")[-1] for sk in (entry.get("series_keys") or []) if "name:" in sk}
                if entry.get("title_display"):
                    _names.add(str(entry["title_display"]))
                _nnames = {re.sub(r"[\s　]+", "", n) for n in _names if n}
                for r in cur.execute("SELECT id, title FROM series WHERE qid=?", (qid,)).fetchall():
                    _t = re.sub(r"[\s　]+", "", r[1] or "")
                    if not _nnames or any(_t and (_t in n or n in _t) for n in _nnames):
                        sids.add(r[0])
            if not sids:
                continue
            vol_dict = {
                "number": entry["number"],
                "volume_label": None,
                "isbn13": entry.get("isbn13"),
                "release_date": entry.get("release_date"),
                "cover_url": None,
                "asin": None,
                "_edition_type": entry.get("edition_type") or "standard",
                # ★_edition_label = 新設版ブロックの表示ラベル(任意。完全版/完全復刻版等。無ければ通常版)
                "_edition_label": entry.get("edition_label"),
                # ★_imprint = imprint(任意・separate_editions合流用) → 無ければ publisher fallback(後方互換)
                "_imprint": entry.get("imprint") or entry.get("publisher") or "",
            }
            for sid in sids:
                out.setdefault(sid, []).append(vol_dict)
    return out


# 起動時 1 回 load
_MERGE_SIDS = None
_MERGE_EDT = None
_SUPP_VOLS = None
def get_merge_sids(con) -> dict[int, list[int]]:
    global _MERGE_SIDS
    if _MERGE_SIDS is None:
        _MERGE_SIDS = load_merge_sids(con)
    return _MERGE_SIDS

def get_merge_edition_types(con) -> set[int]:
    global _MERGE_EDT
    if _MERGE_EDT is None:
        _MERGE_EDT = load_merge_edition_types(con)
    return _MERGE_EDT

_RENUMBER_SIDS = None
def get_renumber_sids(con) -> set[int]:
    global _RENUMBER_SIDS
    if _RENUMBER_SIDS is None:
        _RENUMBER_SIDS = load_renumber_sids(con)
    return _RENUMBER_SIDS

_SEP_EDITION_SIDS = None
def get_separate_edition_sids(con) -> set[int]:
    global _SEP_EDITION_SIDS
    if _SEP_EDITION_SIDS is None:
        _SEP_EDITION_SIDS = load_separate_edition_sids(con)
    return _SEP_EDITION_SIDS

def get_supplement_vols(con) -> dict[int, list[dict]]:
    global _SUPP_VOLS
    if _SUPP_VOLS is None:
        _SUPP_VOLS = load_volumes_supplement(con)
    return _SUPP_VOLS

CUTOFF_YEAR = 2015  # spinoff で この年 以降なら keep
KEEP_EDITION_TYPES = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban", "deluxe"}

# brand (= MADB imprint) → magazine key (= data/magazines.yml master)
# 確度高い 1対1 のみ。
BRAND_TO_MAGAZINE = {
    "ジャンプコミックス": "weekly-shonen-jump",
    "JUMPCOMICS": "weekly-shonen-jump",
    "ジャンプcomics": "weekly-shonen-jump",
    "Jumpcomics": "weekly-shonen-jump",
    "少年サンデーコミックス": "weekly-shonen-sunday",
    "SHONENSUNDAYCOMICS": "weekly-shonen-sunday",
    "少年マガジンコミックス": "weekly-shonen-magazine",
    "SHONENMAGAZINECOMICS": "weekly-shonen-magazine",
    "少年チャンピオンコミックス": "champion",
    "SHONENCHAMPIONCOMICS": "champion",
    "SHŌNENCHAMPIONCOMICS": "champion",
    "ガンガンコミックス": "gangan",
    "Gangancomics": "gangan",
    "角川コミックスエース": "shonen-ace",
    "コミックボンボン": "comic-bonbon",
    "月刊少年マガジン": "monthly-shonen-magazine",
    "別冊少年マガジン": "bessatsu-shonen-magazine",
    "ヤングジャンプコミックス": "weekly-young-jump",
    "YOUNGJUMPCOMICS": "weekly-young-jump",
    "ヤングマガジンKC": "weekly-young-magazine",
    "ヤンマガKC": "weekly-young-magazine",
    "ヤングサンデーコミックス": "weekly-young-sunday",
    "ウルトラジャンプコミックス": "ultra-jump",
    "ビッグコミックス": "big-comic",
    "BIGCOMICS": "big-comic",
    "ビッグコミックススペシャル": "big-comic",
    "BIGCOMICSSPECIAL": "big-comic",
    "モーニングKC": "morning",
    "MorningKC": "morning",
    "アフタヌーンKC": "afternoon",
    "AfternoonKC": "afternoon",
    "アクションコミックス": "manga-action",
    "ACTIONCOMICS": "manga-action",
    "マーガレットコミックス": "margaret",
    "MARGARETCOMICS": "margaret",
    "別冊マーガレットコミックス": "betsuma",
    "りぼんマスコットコミックス": "ribon",
    "なかよしコミックス": "nakayoshi",
    "ちゃおコミックス": "ciao",
    "花とゆめCOMICS": "hana-to-yume",
    "花とゆめコミックス": "hana-to-yume",
    "LaLacomics": "lala",
    "LaLaCOMICS": "lala",
    "ヤングアニマルコミックス": "young-animal",
    "YOUNGANIMALCOMICS": "young-animal",
    "BELOVE": "be-love",
    "てんとう虫コミックス": "ciao",
}


def _normalize_brand_for_mag(brand: str) -> str:
    """brand を BRAND_TO_MAGAZINE key 形式に正規化 (= 中黒/空白 strip)。"""
    if not brand:
        return ""
    return brand.replace("・", "").replace("　", "").replace(" ", "").strip()


def infer_magazine_from_brand(editions: list[dict], valid_mags: set) -> str | None:
    """editions の 主 brand から magazine 推定。"""
    for ed in editions:
        norm = _normalize_brand_for_mag(ed.get("imprint") or "")
        if norm in BRAND_TO_MAGAZINE:
            mag = BRAND_TO_MAGAZINE[norm]
            if not valid_mags or mag in valid_mags:
                return mag
    return None
DROP_IMPRINT_PATTERNS = ["My first big", "コンビニ", "増刊", "同人", "ジャンプremix", "フィルムコミック",
                         "カッパ・ノベル", "カッパノベル", "カッパ・ホーム", "カッパホーム",
                         # ★コンビニ向け廉価再録レーベル(既刊の抜粋/収録 = 本編でない。 2026-06)。
                         #   KPC=講談社プラチナコミックス(頭文字D始動編 等)。 ★DX/デラックスは正規装丁で除外しない。
                         "KPC", "プラチナコミックス",
                         # ★remixカナ表記(2026-07-02: 「ジャンプremix」だけでは Shueisha jump remix 等の
                         #   latin variantを素通し=こち亀年度別コンビニ本54頁が漏れていた。latin側はlowerで捕捉)
                         "リミックス",
                         # ★略記SJR=ShueishaジャンプREMIX(2026-07-11: 'remix'文字列を含まない略記が
                         #   平成こち亀13-28年等41頁を素通し=ユーザ発見)
                         "SJR",
                         # ★アニメ物 imprint (2026-07-26 ユーザ発見「セーラームーンSはフィルムコミック」)。
                         #   既存の網は **title の「アニメコミック」prefix** と **edition_type=anime** だけを見ており、
                         #   ★title が素の作品名 + edition_type=standard で **imprint だけがアニメ物**の版を素通ししていた
                         #   (= もののけ姫/千と千尋/AKIRAアニメコミックス/セーラームーンR・SuperS 等 20頁)。
                         #   フィルムコミック(場面写)・アニメ絵本・絵コンテ集は描き下ろし漫画でない = 掲載対象外。
                         #   ★種2実測で該当 imprint 15+3+4+1+1 種は **全て**アニメ tie-in で、正規漫画レーベルの
                         #   巻き添えは0(「アニメージュコミックス」=ナウシカ等のオリジナル漫画レーベルは
                         #   この文字列に当たらない。 逆に「アニメ」1文字で切ると巻き添えるので当てない)。
                         #   ★「アニメKC」= 講談社のアニメコミックス叢書(アニメKC・アフタヌーン含む)。
                         #     ISBN単位の除外では **別刷り(2000年版→2003年版)が次々出てきて塞げない**ため
                         #     レーベル単位で封じる(2026-07-26 AKIRAで実証)。 実測9頁は全てフィルムコミック
                         #     (AKIRA/十二国記/ガンダム2・3・SEED・SEED DESTINY/さよなら999/逮捕しちゃうぞ)。
                         #   ★「絵コンテ全集」= スタジオジブリ絵コンテ全集(第2期含む)。 絵コンテ=演出設計図で
                         #     漫画でない。 種2実測で該当は同叢書のみ(ゲド戦記/ハウル/ルパン三世/名探偵ホームズ)。
                         "アニメコミック", "アニメ絵本", "テレビ絵本", "アニメアルバム", "メディアブックス",
                         "アニメKC", "絵コンテ全集",
                         # ★ノベライズレーベル(2026-07-27 ユーザ発見: CITY HUNTER SPECIAL=JUMP J BOOKS)。
                         #   既存 'novel'/'novels' の網は「Shonen sunday novels」型のみで、J BOOKSが素通り。
                         #   種2実測11series=全て小説編(るろ剣/こち亀/バスタード等の枠内novel含む)=巻き添え0。
                         "JUMP J BOOKS",
                         # ★コンビニ廉価再録レーベル(2026-07-27 凍牌竜凰位戦上下=ユーザ裁定drop)。
                         #   種2実測で「秋田トップコミックス」(WIDE含む)は当該1seriesのみ=巻き添え0。
                         #   ★Gコミックス/SPコミックス/マンサンコミックス等は**正規レーベル**なので
                         #   一括不可(コンビニ再録は「◯◯スペシャル」等のtitle単位で個別drop)。
                         #   ★パーフェクト・メモワール(リイド社廉価再録・関与74series)は候補=未裁定。
                         "秋田トップコミックス"]
# bilingual / 英訳版 imprint は drop (= 翻訳版 は 別 product)
# ★"remix" = コンビニ廉価再録レーベル全variant(Shueisha jump remix/ガンガンコミックスremix/
#   G fantasy comics remix/My first big special remix等)。種2実測で全てコンビニ再録・正規版に'remix'無し。
DROP_IMPRINT_LOWER_PATTERNS = ["bilingual", "english", "novel", "novels", "remix"]
# 'complete works' は 英訳 全集 で 多用 (= 「TEZUKA OSAMU THE COMPLETE WORKS」、
# 「The complete works of Fujiko・F・Fujio」 等)。 但し 日本語 imprint で 「= English」
# 並列表記 cases (= 「藤子・F・不二雄大全集 = The Complete Works of Fujiko・F・Fujio」)
# は 日本語版 で keep。 「=」 含む imprint は drop 対象外。
DROP_IMPRINT_LOWER_PATTERNS_NO_EQ = ["complete works"]
# 漫画以外 series は MANGAL 掲載対象外 (= title prefix で detect)。
# CLAUDE.md / MEMORY.md 大原則: 「通常版/ワイド版/文庫版/愛蔵版 等 漫画 only」
DROP_TITLE_PREFIX_PATTERNS = [
    "テレビアニメ版", "TVアニメ版", "TVアニメ", "アニメコミック",
    "劇場版", "映画", "OVA",
    "ノベライズ", "ノベル",
    "英訳・", "英訳",
]
# 関連書 (= ガイドブック / 設定資料集 / 攻略本 等、 漫画作品ではない 副次出版物)。
# title 内 包含で detect。 「大全集」 は 主作品 compilation 多いので 除外しない。
DROP_TITLE_CONTAINS_PATTERNS = [
    "ガイドブック", "ファンブック", "設定資料集",
    "公式図録", "公式読本", "公式ファン", "公式コミックガイド",
    "アンソロジー",
    "キャラクター名鑑", "人物名鑑", "キャラクターブック",
    "心理分析", "心理解析", "完全解析", "完全攻略", "攻略本",
    "解析書", "解体新書", "解体全書",
    "大研究", "最終研究", "超研究", "大事典", "大百科", "大解剖",
    "パーフェクトガイド", "完全読本", "完全ガイド", "必勝法",
    "の秘密", "の謎", "コミック大全", "コミックスペシャル",
    "ナビゲーション", "考察",
    # 抜粋本 / 編集本 (= 本編ではない、 既刊の再編。 2026-05-26 追加、 2026-05-29 拡充):
    # 注意: 「短編集 / 作品集」 は 描き下ろし漫画 が多く keep (= drop しない)。
    #       既刊抜粋系のみ drop。
    "傑作選", "傑作集", "ベストセレクション", "特集号", "特別総集編",
    "名作集", "名作選", "自選", "総集編",
    # 画集 / 関連書 (= 漫画でない):
    "原画集", "画集", "ポケット画廊", "うちあけ話",
]

# subtitle に隠れた 抜粋本 (= title 判定を 素通りする 「○○傑作集」 等)。
# 抜粋本系語のみ sub 適用 (= 「の秘密」 等 他の title pattern を sub に広げると
# 誤爆するため、 既刊抜粋系 に限定。 2026-05-29 追加)。
DROP_SUBTITLE_PATTERNS = [
    "傑作集", "傑作選", "ベストセレクション", "名作集", "名作選", "自選", "総集編",
]

# ★本番前sanitize(2026-06-04): 不可視PUA文字(❤/é等が私用領域に化けた物)を title/kana/subtitle から除去。
_PUA_RE = re.compile(r"[-�]")


def _strip_pua(s):
    return _PUA_RE.sub("", s) if s else s


# ★副題noise除去: 出版社/レーベル/形式が副題欄に漏れた物(merge sub-key encoding由来)。
#   real副題はこれらで終わらないので安全。 末尾label or 純label形のみ。
_SUBTITLE_NOISE_RE = re.compile(
    r"^(レディース|ホラー|アニメ|ヤング|プリンセス)?コミックス?$"
    r"|^コミック$|アンコール出版$"                       # 復刻imprint(: アンコール出版 suffix含む)
    r"|新聞漫画集成$|漫画集成$|特別編集コミックス$"      # 集成/形式
    r"|Nazomizu|Comics$")


SEED3_CACHE = ROOT / ".cache" / "seed3-promote.pkl"

_FURIGANA_CORR: dict | None = None


def load_furigana_corrections() -> dict:
    """series_key → {title_kana, title_kana_segmented} の補正 map。
    ★種2(MADB)も種3(AI)も誤っていた key を NDL ground-truth 等で正した小 seed。
    build_yml が title_kana を ★最優先で読む。 file 不在なら空(=従来動作)。"""
    global _FURIGANA_CORR
    if _FURIGANA_CORR is not None:
        return _FURIGANA_CORR
    _FURIGANA_CORR = {}
    if FURIGANA_CORR.exists():
        with FURIGANA_CORR.open(encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        for e in (doc.get("corrections") or []):
            k = e.get("key")
            if k and e.get("title_kana"):
                _FURIGANA_CORR[k] = {
                    "title_kana": e["title_kana"],
                    "title_kana_segmented": e.get("title_kana_segmented", ""),
                }
    return _FURIGANA_CORR


_FURIGANA_FILL: dict | None = None
def load_kana_fill() -> dict:
    """series_key → kana_segmented(空白区切り)。 title_kana 欠落 series の MADB由来補完。
    corr の次・db series_row の前に適用(純粋な欠落埋め、 既存値は上書きしない)。"""
    global _FURIGANA_FILL
    if _FURIGANA_FILL is not None:
        return _FURIGANA_FILL
    _FURIGANA_FILL = {}
    if FURIGANA_FILL.exists():
        with FURIGANA_FILL.open(encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        for e in (doc.get("fills") or []):
            k, kseg = e.get("key"), e.get("kana_segmented")
            if k and kseg:
                _FURIGANA_FILL[k] = kseg
    return _FURIGANA_FILL


# かな(ひら/カタ)→ ヘボン式ローマ字。 title_romaji 用(検索フィールド・全小文字・空白で分かち)。
_HEP = {
    "きゃ": "kya", "きゅ": "kyu", "きょ": "kyo", "しゃ": "sha", "しゅ": "shu", "しょ": "sho",
    "ちゃ": "cha", "ちゅ": "chu", "ちょ": "cho", "にゃ": "nya", "にゅ": "nyu", "にょ": "nyo",
    "ひゃ": "hya", "ひゅ": "hyu", "ひょ": "hyo", "みゃ": "mya", "みゅ": "myu", "みょ": "myo",
    "りゃ": "rya", "りゅ": "ryu", "りょ": "ryo", "ぎゃ": "gya", "ぎゅ": "gyu", "ぎょ": "gyo",
    "じゃ": "ja", "じゅ": "ju", "じょ": "jo", "びゃ": "bya", "びゅ": "byu", "びょ": "byo",
    "ぴゃ": "pya", "ぴゅ": "pyu", "ぴょ": "pyo", "ふぁ": "fa", "ふぃ": "fi", "ふぇ": "fe", "ふぉ": "fo",
    "うぃ": "wi", "うぇ": "we", "ゔぁ": "va", "ゔぃ": "vi", "ゔぇ": "ve", "ゔぉ": "vo",
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o", "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so", "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no", "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo", "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro", "わ": "wa", "を": "o", "ん": "n",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go", "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do", "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po", "ゔ": "vu",
    "ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o", "ゃ": "ya", "ゅ": "yu", "ょ": "yo",
}
def romanize_kana(s: str) -> str:
    """かな(空白で分かち書き)→ ヘボン式ローマ字(全小文字)。 長音ー省略・促音っ重子音。"""
    if not s:
        return ""
    # カタカナ→ひらがな
    s = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヴ" else c for c in s)
    s = re.sub(r"[\s　]+", " ", s).strip()
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == " ":
            out.append(" "); i += 1; continue
        if c == "ー":  # 長音は省略
            i += 1; continue
        if c == "っ":  # 促音 = 次の子音を重ねる
            nxt = _HEP.get(s[i+1:i+3]) or _HEP.get(s[i+1:i+2], "") if i + 1 < len(s) else ""
            if nxt and nxt[0] not in "aiueo":
                out.append(nxt[0])
            i += 1; continue
        two = s[i:i+2]
        if two in _HEP:
            out.append(_HEP[two]); i += 2; continue
        r = _HEP.get(c)
        if r is not None:
            out.append(r)
        # 未知文字(漢字混じり等)は捨てる
        i += 1
    return re.sub(r"\s+", " ", "".join(out)).strip().lower()


def load_seed3() -> dict:
    """series_key → seed3 entry の dict。
    SEED3 (= 33MB/92万行) の YAML パースは CSafeLoader でも 70秒級なので、
    mtime 連動の pickle cache を使う (= 2回目以降 ~1秒)。"""
    import pickle
    if SEED3_CACHE.exists() and SEED3.exists() and SEED3_CACHE.stat().st_mtime >= SEED3.stat().st_mtime:
        try:
            with SEED3_CACHE.open("rb") as f:
                return pickle.load(f)
        except Exception:
            pass  # cache 破損時は 再生成
    with SEED3.open("r", encoding="utf-8") as f:
        d = _yload(f)
    out = {e["key"]: e for e in d["series"]}
    SEED3_CACHE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with SEED3_CACHE.open("wb") as f:
            pickle.dump(out, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass
    return out


def normalize_title_for_prefix(t: str) -> str:
    """『〜』 strip、 「英訳・」「劇場版」「テレビアニメ版」 等 接頭辞 strip。"""
    s = t.strip()
    # 『...』 → ...
    s = re.sub(r"[『「【〔]", "", s)
    s = re.sub(r"[』」】〕]", "", s)
    # 接頭辞 strip
    for prefix in ["英訳・", "劇場版", "劇場用アニメ", "テレビアニメ版",
                   "映画 ", "映画"]:
        if s.startswith(prefix):
            s = s[len(prefix):].lstrip()
    return s


def build_parent_map(con: sqlite3.Connection) -> dict[int, int]:
    """series_id → parent_series_id (= 親検出済 only)。 公開対象 (= score<3) のみ。

    親判定:
      - 同 qid または 同 creator_name
      - 親 title が 子 title の prefix (= normalize 後)
      - 親 has MORE total ISBN volumes than 子
      - 親 自身 が 副題なし

    全 series 走査で 重い (= ~70秒) ため、 DB mtime 連動 pickle cache を使う。
    """
    import pickle
    cache = ROOT / ".cache" / "parent-map.pkl"
    if cache.exists() and DB.exists() and cache.stat().st_mtime >= DB.stat().st_mtime:
        try:
            with cache.open("rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    # 成人判定 手動 override (= adult_score>=3 でも force 非adult で本番採用)。
    #   data/seeds/adult-overrides.yml = 作者signal単独誤爆を種aで全年齢確認した分 (Phase A)。
    #   純粋追加 only / 種2 不変 / 再build耐性。
    _ovr = _load_adult_overrides()
    if _ovr:
        ph = ",".join("?" * len(_ovr))
        cur.execute(f"""
            SELECT s.id, s.qid, s.title, s.subtitle,
                   (SELECT COUNT(*) FROM volumes v JOIN editions e ON e.id=v.edition_id
                    WHERE e.series_id=s.id AND v.isbn13 IS NOT NULL) AS n_isbn
            FROM series s
            WHERE s.adult_score < 3 OR s.series_key IN ({ph})
        """, sorted(_ovr))
    else:
        cur.execute("""
            SELECT s.id, s.qid, s.title, s.subtitle,
                   (SELECT COUNT(*) FROM volumes v JOIN editions e ON e.id=v.edition_id
                    WHERE e.series_id=s.id AND v.isbn13 IS NOT NULL) AS n_isbn
            FROM series s
            WHERE s.adult_score < 3
        """)
    all_series = [dict(r) for r in cur.fetchall()]
    by_qid = defaultdict(list)
    for s in all_series:
        if s["qid"]:
            by_qid[s["qid"]].append(s)
    parent_map: dict[int, int] = {}
    for qid, sib in by_qid.items():
        # 候補 parent (= 副題なし、 n_isbn 多い順)
        parents = [s for s in sib if not s["subtitle"]]
        parents.sort(key=lambda s: -s["n_isbn"])
        for child in sib:
            child_norm = normalize_title_for_prefix(child["title"])
            for parent in parents:
                if parent["id"] == child["id"]:
                    continue
                parent_norm = normalize_title_for_prefix(parent["title"])
                if not parent_norm:
                    continue
                # parent_norm が child_norm の prefix
                if child_norm.startswith(parent_norm) and child_norm != parent_norm:
                    # 親 has more vol
                    if parent["n_isbn"] > child["n_isbn"]:
                        parent_map[child["id"]] = parent["id"]
                        break
                # 副題ある child は parent と base title が一致 (= no prefix relation)
                # ケースも spinoff 扱い
                elif child.get("subtitle") and parent_norm == child_norm:
                    if parent["n_isbn"] > child["n_isbn"]:
                        parent_map[child["id"]] = parent["id"]
                        break
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        with cache.open("wb") as f:
            pickle.dump(parent_map, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass
    return parent_map


def get_max_release_year(con: sqlite3.Connection, series_id: int) -> int | None:
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    r = cur.execute("""
        SELECT MAX(SUBSTR(v.release_date, 1, 4)) AS y
        FROM volumes v JOIN editions e ON e.id=v.edition_id
        WHERE e.series_id=? AND v.release_date IS NOT NULL
    """, (series_id,)).fetchone()
    if r and r["y"]:
        try:
            return int(r["y"])
        except ValueError:
            return None
    return None


def find_series(con: sqlite3.Connection, slug: str, title: str, qid: str | None,
                series_key: str | None = None) -> dict | None:
    """旧 yml の (slug, title, qid) から db-v2 で series 探す。

    ★series_key が渡されたら **series_key で直接照合**(slug-final駆動の確実join。
      homophone接尾辞で title照合が曖昧になるのを回避)。
    優先順(series_key 無し時):
      1. qid + title 完全一致
      2. title 完全一致 (= qid なし時)
      3. title 部分一致
    """
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    if series_key:
        rows = cur.execute(
            "SELECT * FROM series WHERE series_key=? LIMIT 1", (series_key,)
        ).fetchall()
        if rows:
            return dict(rows[0])
        return None
    if qid:
        rows = cur.execute(
            "SELECT * FROM series WHERE qid=? AND title=? ORDER BY adult_score LIMIT 1",
            (qid, title),
        ).fetchall()
        if rows:
            return dict(rows[0])
    rows = cur.execute(
        "SELECT * FROM series WHERE title=? ORDER BY adult_score LIMIT 1", (title,)
    ).fetchall()
    if rows:
        return dict(rows[0])
    return None


def _title_punct_suffix(title: str | None) -> str:
    """title から alphanumeric + kana + 漢字 を 全部 strip し、 残った punctuation を 返す。

    例: 'バクマン。' → '。'、 'BAKUMAN。' → '。'、 'バクマン!' → '!'
    『BAKUMAN。』 と 『バクマン。』 は match (= 同作品の表記揺れ)、
    『バクマン!』 (= 別作品) は punct 違いで 非 match。
    """
    if not title:
        return ""
    return re.sub(r"[a-zA-Z0-9ぁ-んァ-ヶー一-龯々〆〇 　]", "", title)


def _normalize_kana(kana: str | None) -> str:
    """title_kana を normalize (= 空白 / 中黒 / × 等 strip)。

    'ハンター ハンター' と 'ハンター × ハンター' を 共通 'ハンターハンター' に
    寄せて kana match の 表記揺れ吸収。
    """
    if not kana:
        return ""
    return re.sub(r"[^ぁ-んァ-ヶー一-龯]", "", kana)


def _is_ascii_title(title: str | None) -> bool:
    """title に 漢字/かな が 含まれない なら ASCII (= ローマ字表記) 扱い。

    'Hunter×hunter' = ASCII (= 'H','u','n',...,×,'h','u','n','t','e','r' で kana/kanji なし)
    'ハンター×ハンター' = non-ASCII (= カナ含む)
    """
    if not title:
        return False
    return not bool(re.search(r"[ぁ-んァ-ヶー一-龯]", title))


def _strip_trailing_punct(title: str | None) -> str:
    """title 末尾 の punct (= '.', ',', '。', '．' 等) を strip。
    '銀河英雄伝説.' と '銀河英雄伝説' を 同一視 する 用途。
    """
    if not title:
        return ""
    return re.sub(r"[.,。．・、]+$", "", title.strip())


# publisher prefix + kana normalize cache (= 起動時 1 回 build、 lookup O(1))
# extract で 2000 candidates × find_related_series_ids = 大量 SQL を 回避
_PUB_CACHE: dict | None = None
_MAJOR_CACHE: dict | None = None
_KANA_INDEX: dict | None = None  # normalized_kana → list of (series_id, title, title_kana)
_TITLE_STRIP_INDEX: dict | None = None  # qid-null series: title_strip → [series_id]
_TITLE_LOWER_NULL_INDEX: dict | None = None  # qid-null series: lower(title) → [series_id]


def _build_kana_index(con: sqlite3.Connection) -> None:
    """全 series で normalize_kana(title_kana) → [(id, title, title_kana)] map 構築。"""
    global _KANA_INDEX
    if _KANA_INDEX is not None:
        return
    from collections import defaultdict
    _KANA_INDEX = defaultdict(list)
    cur = con.cursor()
    rows = cur.execute(
        "SELECT id, title, title_kana FROM series WHERE title_kana IS NOT NULL"
    ).fetchall()
    for sid, title, kana in rows:
        k_norm = _normalize_kana(kana)
        if k_norm:
            _KANA_INDEX[k_norm].append((sid, title, kana))


def _build_title_strip_index(con: sqlite3.Connection) -> None:
    """qid IS NULL の series を title_strip → [id] で索引化(= per-page の全表scan回避)。
    起動時 1 回 build、 find_related_series_ids の orphan title 一致を O(1) に。"""
    global _TITLE_STRIP_INDEX, _TITLE_LOWER_NULL_INDEX
    if _TITLE_STRIP_INDEX is not None:
        return
    from collections import defaultdict
    _TITLE_STRIP_INDEX = defaultdict(list)
    _TITLE_LOWER_NULL_INDEX = defaultdict(list)
    cur = con.cursor()
    for sid, title in cur.execute(
        "SELECT id, title FROM series WHERE qid IS NULL"
    ).fetchall():
        _TITLE_STRIP_INDEX[_strip_trailing_punct(title)].append(sid)
        if title:
            _TITLE_LOWER_NULL_INDEX[title.lower()].append(sid)


def _build_publisher_cache(con: sqlite3.Connection) -> None:
    """全 series の publisher prefixes を 1 回 SQL scan で 構築 (= cache)。"""
    global _PUB_CACHE, _MAJOR_CACHE
    if _PUB_CACHE is not None:
        return
    from collections import defaultdict, Counter
    _PUB_CACHE = defaultdict(set)
    counters: dict = defaultdict(Counter)
    cur = con.cursor()
    rows = cur.execute(
        "SELECT e.series_id, v.isbn13, e.type, e.imprint "
        "FROM volumes v JOIN editions e ON e.id=v.edition_id "
        "WHERE v.isbn13 IS NOT NULL"
    ).fetchall()
    for sid, isbn, type_, imp in rows:
        if type_ not in KEEP_EDITION_TYPES:
            continue
        imp = imp or ""
        if any(pat in imp for pat in DROP_IMPRINT_PATTERNS):
            continue
        imp_l = imp.lower()
        if any(pat in imp_l for pat in DROP_IMPRINT_LOWER_PATTERNS):
            continue
        if "=" not in imp and any(pat in imp_l for pat in DROP_IMPRINT_LOWER_PATTERNS_NO_EQ):
            continue
        p = (isbn or "").replace("-", "")
        if len(p) >= 6:
            prefix = p[:6]
            _PUB_CACHE[sid].add(prefix)
            counters[sid][prefix] += 1
    _MAJOR_CACHE = {
        sid: cnt.most_common(1)[0][0]
        for sid, cnt in counters.items()
    }


def get_major_publisher_prefix(con: sqlite3.Connection, series_id: int) -> str | None:
    """cache から series の 最大 vol 数 publisher prefix 取得。"""
    _build_publisher_cache(con)
    return _MAJOR_CACHE.get(series_id) if _MAJOR_CACHE else None


# === publisher 解決 (設計b: 種2 ISBN→当時社名(版表示) → キー(work集合)) ===
# edition.publisher = 当時の生社名(事実・表示)、 work.publishers = 全版の社キー distinct、
# work.publisher = 代表(最多巻の社キー)。 名前→キーは publishers.yml(display名norm照合) +
# publisher-aliases.yml(別名同一実体 merge、 ISBN帯確認済)。 long尾は key無し=生社名表示のみ。
_PUBKEY: dict | None = None        # norm社名 → key
_ISBN2PUB: dict | None = None      # isbn(digits) → 生社名


def _to_isbn13(s) -> str | None:
    """ISBN文字列(10/13、ハイフン有無)→ 13桁digits。 不正は None。"""
    d = re.sub(r"[^0-9Xx]", "", str(s))
    if len(d) == 13:
        return d
    if len(d) == 10:
        core = "978" + d[:9]
        c = sum((1 if i % 2 == 0 else 3) * int(x) for i, x in enumerate(core))
        return core + str((10 - c % 10) % 10)
    return None


def _norm_pub(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[\(\[（【].{0,6}?(発売|発行|製作|配給).{0,2}?[\)\]）】]", "", s)
    s = re.sub(r"(株式会社|有限会社|合同会社|\(株\)|\(有\)|㈱|㈲)", "", s)
    s = re.sub(r"[\s・･,，\.\-—–]", "", s).strip()
    return s


# ★本のクレジット名(2026-07-26 ユーザ方針「表示はその本のクレジット」):
#   MADB は schema:creator に**その本に刷られた名義**を持つ(美月めいあ/さんかく)。
#   一方 dcterms:creator の典拠IDで人物解決すると mangaka.name は**代表名**(風緒/生倉大福)になり、
#   従来はそちらで上書きしていたため本の名義が失われていた
#   (2026-07-26 実測: 本番の 2,820頁 がこの型。ユーザ提供のMADB生RDFで判明)。
#   ★典拠解決は同定にだけ使い、**表示名は本のクレジット**にする。
_ISBN2CREDIT: dict | None = None
_PREFIX_PUB: dict | None = None
_PREFIX_RATIO: dict | None = None


def _implied_pub(isbn13: str, table: dict, ratio: dict):
    """ISBN出版者記号が示す社名。 ★最長の有効記号だけを見る(桁をまたいで降りない)。
    その記号が割れている(majority<0.6)なら **判定不能=None**(誤判定より取りこぼしを選ぶ)。"""
    for pf in sorted(_isbn_prefixes(isbn13), key=len, reverse=True):
        if pf not in table:
            continue
        return table[pf] if ratio.get(pf, 0) >= 0.6 else None
    return None


def _isbn_prefixes(isbn13: str) -> list:
    """ISBN13 の出版者記号候補(978-4-XXXX..)。 桁数不定なので 2..7桁を全部返す。"""
    body = isbn13[4:]
    return [body[:n] for n in (2, 3, 4, 5, 6, 7)]


def _credit_names(v) -> list:
    """schema:creator から **ja の素の名前だけ** 取り出す(ja-hrkt の読みは除外)。
    形は ["名", {@value:"ヨミ",@language:ja-hrkt}] / [{@value:[ヨミ,ヨミ]}, ["名","名"]] 等が混在。"""
    out = []

    def walk(x):
        if isinstance(x, str):
            t = x.strip()
            if t:
                out.append(t)
        elif isinstance(x, list):
            for y in x:
                walk(y)
        elif isinstance(x, dict):
            if x.get("@language") == "ja-hrkt":
                return            # 読み(カナ)は名前ではない
            walk(x.get("@value"))
    walk(v)
    return out


def _apply_book_credit(authors: list[dict], isbns: list, alias: dict) -> list[dict]:
    """著者の**表示名だけ**を「その本のクレジット」へ1:1で寄せる。
    ★人の追加/削除は絶対にしない(監修者・原作者・題名の混入を原理的に防ぐ。
      2026-07-26: 追加を許すと『妖怪マンガで楽しい古典→小松和彦(監修)』型の事故が出た)。
    条件 = 現在名が本のクレジットに無く、かつ **その人物の別名(alt_names)がクレジットに在る** 時だけ改名。"""
    if not authors or not isbns:
        return authors
    cred = []
    for ib in isbns:
        cred += (_ISBN2CREDIT or {}).get(str(ib), [])
    if not cred:
        return authors
    cset = {_norm_pub(c): c for c in cred}      # 空白/記号を落とした照合キー
    out = []
    for a in authors:
        nm = a.get("name") or ""
        if _norm_pub(nm) in cset:
            out.append(a); continue
        hit = next((cset[k] for k in (_norm_pub(x) for x in alias.get(nm, ())) if k in cset), None)
        out.append({**a, "name": hit} if hit else a)
    return out


_MANGAKA_ALIAS: dict | None = None


def _mangaka_alias(con) -> dict:
    """name -> 別名集合(mangaka.alt_names)。 本のクレジットへ寄せる時の**同一人物の証拠**。"""
    global _MANGAKA_ALIAS
    if _MANGAKA_ALIAS is None:
        _MANGAKA_ALIAS = {}
        for nm, al in con.execute("SELECT name, alt_names FROM mangaka"):
            if al:
                _MANGAKA_ALIAS[nm] = {x.strip() for x in str(al).split("|") if x.strip()}
    return _MANGAKA_ALIAS


def _load_pub_resolver() -> None:
    global _PUBKEY, _ISBN2PUB
    if _PUBKEY is not None:
        return
    pub = yaml.safe_load(open(ROOT / "data" / "publishers.yml", encoding="utf-8")) or {}
    _PUBKEY = {_norm_pub(v["name"]): k for k, v in pub.items()}
    ali = ROOT / "data" / "publisher-aliases.yml"
    if ali.exists():
        for nm, key in (yaml.safe_load(open(ali, encoding="utf-8")) or {}).items():
            _PUBKEY[nm] = key   # alias key は norm社名 → 既存/新キー
    _ISBN2PUB = {}
    from collections import Counter as _Counter, defaultdict as _dd
    _votes, _multi = _dd(_Counter), {}
    global _ISBN2CREDIT
    _ISBN2CREDIT = {}
    meta = ROOT / ".cache" / "madb" / "metadata101-clean.json"
    if meta.exists():
        g = json.load(open(meta, encoding="utf-8"))
        rows = g.get("@graph", g) if isinstance(g, dict) else g
        for r in rows:
            p = r.get("schema:publisher") or r.get("publisher")
            if isinstance(p, list):
                p = p[0] if p else None
            if isinstance(p, dict):
                p = p.get("@value") or p.get("name")
            i = r.get("schema:isbn") or r.get("isbn")
            if isinstance(i, list):
                i = i[0] if i else None
            if not p or not i:
                continue
            k = _to_isbn13(i)   # ★metadata101はISBN-10混在 → 13に正規化してDB(isbn13)と突合
            if k:
                _raw = r.get("schema:publisher")
                _cands = [x.strip() for x in ([_raw] if isinstance(_raw, str) else _raw)
                          if isinstance(x, str) and x.strip()] if _raw else []
                _ISBN2PUB[k] = p
                if len(_cands) > 1:
                    _multi[k] = _cands          # ★複数候補は後で ISBN出版者記号 で選び直す
                elif _cands and k.startswith("9784"):
                    for _pf in _isbn_prefixes(k):
                        _votes[_pf][_cands[0]] += 1
                cr = _credit_names(r.get("schema:creator"))
                if cr:
                    _ISBN2CREDIT[k] = cr
    # ★発行元 vs 頒布元の取り違え是正(2026-07-26 ユーザ提供のMADB生RDFで発覚):
    #   MADB raw は ["一迅社", "[頒布]講談社"] と役割を明示するが、clean が
    #   stripLeadingRolePrefix で [頒布]/[発売] を落とすため区別が消え、従来は
    #   **配列の先頭**を採っていた(順序に意味は無い)。 実測4,149版が食い違い、
    #   うち1,537版が複数候補からの誤採用(講談社←→一迅社だけで501)。
    #   ★ISBN出版者記号は不変の事実なので、単一出版社ISBNから記号→社名を自己学習し、
    #     複数候補のときは記号に一致する候補を採る。
    global _PREFIX_PUB
    # ★票数だけで採否を決め、比率で切らない。 引く時に「最長の有効記号だけ」を使い
    #   **桁をまたぐフォールバックをしない**(短い記号は別社と共有する帯。
    #   4-8342[ホーム社126/集英社54]が未学習→4-83..→芳文社 に化けた 2026-07-26)。
    _table, _ratio = {}, {}
    for _pf, _c in _votes.items():
        _top, _n = _c.most_common(1)[0]
        _tot = sum(_c.values())
        if _tot >= 8:
            _table[_pf] = _top
            _ratio[_pf] = _n / _tot
    _fixed = 0
    for k, _cands in _multi.items():
        _want = _implied_pub(k, _table, _ratio)
        if _want and _want in _cands and _ISBN2PUB.get(k) != _want:
            _ISBN2PUB[k] = _want
            _fixed += 1
    _PREFIX_PUB, _PREFIX_RATIO = _table, _ratio
    print(f"  出版社: ISBN出版者記号で是正 {_fixed:,} 件 (記号表 {len(_table):,})", file=sys.stderr)


_PUB_DISPLAY: dict | None = None


def _pub_display_name(key: str) -> str | None:
    """publishers.yml のキー → 表示名(cygames→Cygames / home-sha→ホーム社)。
    ★ISBN出版者記号が未学習の小規模社(2026-07-26 実測41版)の最終フォールバック。
    キーは我々が付けた内部識別子なので、表示名は yml が唯一の正。"""
    global _PUB_DISPLAY
    if _PUB_DISPLAY is None:
        _doc = yaml.safe_load(open(ROOT / "data" / "publishers.yml", encoding="utf-8")) or {}
        _PUB_DISPLAY = {k: (v or {}).get("name") for k, v in _doc.items() if (v or {}).get("name")}
    return _PUB_DISPLAY.get(key)


def edition_pub_name(ed: dict) -> str | None:
    """版の当時社名 = 巻ISBN群から最多の生社名 (= 種2 ISBN→metadata101)。"""
    from collections import Counter
    _load_pub_resolver()
    c = Counter()
    for v in ed.get("volumes", []):
        isbn = v.get("isbn13")
        if not isbn:
            continue
        k13 = _to_isbn13(isbn)
        nm = _ISBN2PUB.get(k13)
        if not nm and k13 and k13.startswith("9784") and _PREFIX_PUB:
            # ★metadata101に無いISBN(新刊/予約)は **出版者記号** から社名を引く。
            #   これが無いと edition.publisher に予約頁の**内部キー**(kadokawa等)が
            #   そのまま表示に残る(2026-07-26 実測1,248版、うち894が未収載ISBN)。
            nm = _implied_pub(k13, _PREFIX_PUB, _PREFIX_RATIO or {})
        if nm:
            c[nm] += 1
    return c.most_common(1)[0][0] if c else None


def pub_key_of(name: str | None) -> str | None:
    """生社名 → publishers.yml キー (norm照合 + alias)。 未登録(long尾)は None。"""
    if not name:
        return None
    _load_pub_resolver()
    return _PUBKEY.get(_norm_pub(name))


# === 著者ヨミ (50音索引用、 MADB metadata504 公式ヨミ由来) ===
_AUTHOR_YOMI: dict | None = None
_AUTHOR_CORR: dict | None = None


def _load_page_dedup() -> set:
    """page-dedup.yml の drop slug 集合(= 中身同一の二重出力ページ。 canonical 側だけ出力)。"""
    p = ROOT / "data" / "seeds" / "page-dedup.yml"
    if not p.exists():
        return set()
    doc = yaml.safe_load(open(p, encoding="utf-8")) or {}
    return {e["drop"] for e in doc.get("dedup", []) if e.get("drop")}


_PAGE_DEDUP_DROPS: set = _load_page_dedup()


def _load_company_drops() -> set:
    # ★会社/編集部著者の非漫画(編集部編纂のアンソロ/ガイド/ムック)= slug単位drop。 多ソース検証(WF)で確定分。
    p = ROOT / "data" / "seeds" / "company-nonmanga-drop.json"
    return set(json.loads(p.read_text(encoding="utf-8"))) if p.exists() else set()


_COMPANY_DROPS: set = _load_company_drops()


def _load_drop_series_keys() -> set:
    """非掲載 series_key 集合(non-manga-drop.yml)。 ★merge除外用: drop済series(外国版/
    フィルムコミック等)が find_related_series_ids で他ページに混入するのを防ぐ。
    drop は「単独ページ化を止める」だけだったため、同題merge経由で巻が漏れ込んでいた
    (= コナン映画フィルムコミックが同題コミカライズページに混入)。"""
    p = ROOT / "data" / "seeds" / "non-manga-drop.yml"
    if not p.exists():
        return set()
    doc = yaml.safe_load(open(p, encoding="utf-8")) or {}
    return {e["series_key"] for e in doc.get("non_manga", []) if e.get("series_key")}


_DROP_SERIES_KEYS: set = _load_drop_series_keys()


def _load_genre_additions() -> dict:
    """genre-additions.yml(野球/サッカー手動)+ genre-wiki.yml(Wikipediaカテゴリ突合)。
    どちらも信頼源の純粋追加 = series_key -> 追加ジャンルkey list。"""
    out: dict = {}
    for fn in ("genre-additions.yml", "genre-wiki.yml"):
        p = ROOT / "data" / "seeds" / fn
        if not p.exists():
            continue
        doc = yaml.safe_load(open(p, encoding="utf-8")) or {}
        for e in doc.get("additions", []):
            k = e.get("series_key")
            if k:
                out.setdefault(k, []).extend(e.get("add") or [])
    return out


_GENRE_ADDITIONS: dict = _load_genre_additions()


def _load_rakuten_labels() -> tuple[dict, dict]:
    """楽天あらすじ由来ラベル(Phase③、 slug単位の純粋追加。 [[genre_from_rakuten_story_plan]])。
    genre-rakuten.yml = provisional work(trusted空)へ振るジャンル。
    tag-rakuten.yml   = theme tag未保有 work へ足す要素タグ。
    どちらも較正(信頼度閾値)済の高精度ラベルのみ。 trusted/手動は不変。"""
    g: dict = {}; t: dict = {}
    pg = ROOT / "data" / "seeds" / "genre-rakuten.yml"
    if pg.exists():
        for e in (yaml.safe_load(open(pg, encoding="utf-8")) or {}).get("additions", []):
            if e.get("slug"):
                g[e["slug"]] = e.get("genres") or []
    pt = ROOT / "data" / "seeds" / "tag-rakuten.yml"
    if pt.exists():
        for e in (yaml.safe_load(open(pt, encoding="utf-8")) or {}).get("additions", []):
            if e.get("slug"):
                t[e["slug"]] = e.get("tags") or []
    return g, t


_RAKUTEN_GENRES, _RAKUTEN_TAGS = _load_rakuten_labels()


def _load_enrich_genres_tags():
    # ★enrich作り直し(vol1 caption基点・closed vocab)の genre/要素タグ。 slug単位。 trusted無時のAI上書き。
    gp = ROOT / "data" / "seeds" / "genre-enrich-2425.json"
    tp = ROOT / "data" / "seeds" / "tags-enrich-2425.json"
    g = json.loads(gp.read_text(encoding="utf-8")) if gp.exists() else {}
    t = json.loads(tp.read_text(encoding="utf-8")) if tp.exists() else {}
    return g, t


_GENRE_ENRICH, _TAGS_ENRICH = _load_enrich_genres_tags()


def _load_author_yomi() -> None:
    global _AUTHOR_YOMI
    if _AUTHOR_YOMI is not None:
        return
    p = ROOT / "data" / "seeds" / "author-yomi.yml"
    _AUTHOR_YOMI = (yaml.safe_load(open(p, encoding="utf-8")) or {}).get("yomi", {}) if p.exists() else {}


def _load_author_corr() -> None:
    """著者補正seed (生MADB役割タグ由来) を series_key -> {drop:set, add:list} で読む。
    drop=非著者role(編/解説/発売等)除去 / add=実在人物の取りこぼし著者(救済)。 種2不変overlay。"""
    global _AUTHOR_CORR
    if _AUTHOR_CORR is not None:
        return
    _AUTHOR_CORR = {}
    p = ROOT / "data" / "seeds" / "author-role-corrections.yml"
    if not p.exists():
        return
    doc = yaml.safe_load(open(p, encoding="utf-8")) or {}
    for e in doc.get("corrections", []):
        k = e.get("series_key")
        if not k:
            continue
        creds = e.get("credits") or []
        _AUTHOR_CORR[k] = {"drop": {cc["name"] for cc in creds if cc.get("name")},
                           "credits": creds,
                           "original": set(e.get("original") or []),
                           "add": list(e.get("add") or []),
                           # ★remove=誤クレジット人物の完全除去(creditsに出さない。うさ銀太郎/むつきらん型 2026-07-10)
                           "remove": set(e.get("remove") or [])}


def get_author_credits(series_key: str) -> list[dict]:
    """series_key の credits(副次クレジット name+role)。 表示用、 著者でない。"""
    _load_author_corr()
    corr = _AUTHOR_CORR.get(series_key)
    return list(corr["credits"]) if corr else []


def apply_author_corrections(authors: list[dict], series_key: str) -> list[dict]:
    """series_key の補正を適用(生MADB役割タグ由来):
      drop     = 非著者role(編/監修/訳/装丁/協力/企画...)を除去
      original = 原作系を role=original_author に(promoteが original_authors 欄へ振り分け)
      add      = 取りこぼし著者の救済追加(writer_artist)
    enrich_author で kana/romaji は後段付与。 種2不変。"""
    _load_author_corr()
    corr = _AUTHOR_CORR.get(series_key)
    if not corr:
        return authors
    drop, orig = corr["drop"] | corr.get("remove", set()), corr["original"]
    out = []
    for a in authors:
        nm = a.get("name")
        if nm in drop:
            continue
        if nm in orig and a.get("role") != "original_author":
            a = {**a, "role": "original_author"}
        out.append(a)
    have = {a.get("name") for a in out}
    for nm in corr["add"]:
        if nm not in have:
            # ★add×original 両指定=「取りこぼした原作者」の救済(FF Lost Stranger水瀬葉月 2026-07-10)。
            #   従来はwriter_artist固定で原作がauthors欄に混ざった。既存seedにadd∩original重複は0=無影響。
            out.append({"name": nm, "role": "original_author" if nm in orig else "writer_artist"})
            have.add(nm)
    # ★最終安全網: 原作化で authors(非original)が0になったら、 我々が原作化した分を著者へ戻す
    if out and not any(a.get("role") != "original_author" for a in out):
        out = [{**a, "role": "writer_artist"} if a.get("name") in orig else a for a in out]
    return out


_SLUG_OVR = None
def _slug_override(slug: str) -> str:
    """slug-overrides.yml (主版slug是正の恒久指示) を適用。 旧slug→無印 等。 再promoteでも保持。"""
    global _SLUG_OVR
    if _SLUG_OVR is None:
        _SLUG_OVR = {}
        p = ROOT / "data" / "seeds" / "slug-overrides.yml"
        if p.exists():
            doc = yaml.safe_load(open(p, encoding="utf-8")) or {}
            for old, v in (doc.get("overrides") or {}).items():
                if isinstance(v, dict) and v.get("slug"):
                    _SLUG_OVR[old] = v["slug"]
    return _SLUG_OVR.get(slug, slug)


_SKEY_OVR = None
def _skey_override(slug: str, fallback):
    """skey-overrides.yml (どのdb-v2 seriesに繋ぐかの恒久是正・git追跡)。誤クラスタjoinの恒久fix。"""
    global _SKEY_OVR
    if _SKEY_OVR is None:
        _SKEY_OVR = {}
        p = ROOT / "data" / "seeds" / "skey-overrides.yml"
        if p.exists():
            doc = yaml.safe_load(open(p, encoding="utf-8")) or {}
            for s, v in (doc.get("overrides") or {}).items():
                if isinstance(v, dict) and v.get("skey"):
                    _SKEY_OVR[s] = v["skey"]
    return _SKEY_OVR.get(slug, fallback)


def enrich_author(a: dict) -> dict:
    """著者dictに kana(504由来カタカナ)+ romaji(kana→ヘボン)を付与。 無ければ素のまま。"""
    _load_author_yomi()
    kana = _AUTHOR_YOMI.get(a.get("name"))
    if kana:
        a["kana"] = kana
        rom = romanize_kana(kana)
        if rom:
            a["romaji"] = rom
    return a


def _get_major_publisher_prefix_legacy(con: sqlite3.Connection, series_id: int) -> str | None:
    """旧 (= cache 不使用) 実装、 比較 / 確認 用。"""
    from collections import Counter
    cur = con.cursor()
    rows = cur.execute(
        "SELECT v.isbn13, e.type, e.imprint "
        "FROM volumes v JOIN editions e ON e.id=v.edition_id "
        "WHERE e.series_id=? AND v.isbn13 IS NOT NULL", (series_id,)
    ).fetchall()
    counter: Counter = Counter()
    for r in rows:
        if r[1] not in KEEP_EDITION_TYPES:
            continue
        imp = r[2] or ""
        if any(pat in imp for pat in DROP_IMPRINT_PATTERNS):
            continue
        imp_l = imp.lower()
        if any(pat in imp_l for pat in DROP_IMPRINT_LOWER_PATTERNS):
            continue
        if "=" not in imp and any(pat in imp_l for pat in DROP_IMPRINT_LOWER_PATTERNS_NO_EQ):
            continue
        p = (r[0] or "").replace("-", "")
        if len(p) >= 6:
            counter[p[:6]] += 1
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def get_publisher_prefixes(con: sqlite3.Connection, series_id: int) -> set:
    """cache から series の publisher prefixes set 取得。"""
    _build_publisher_cache(con)
    return _PUB_CACHE.get(series_id, set()) if _PUB_CACHE else set()


def _get_publisher_prefixes_legacy(con: sqlite3.Connection, series_id: int) -> set:
    """旧 (= cache 不使用) 実装。"""
    cur = con.cursor()
    prefixes: set = set()
    rows = cur.execute(
        "SELECT v.isbn13, e.type, e.imprint "
        "FROM volumes v JOIN editions e ON e.id=v.edition_id "
        "WHERE e.series_id=? AND v.isbn13 IS NOT NULL", (series_id,)
    ).fetchall()
    for r in rows:
        if r[1] not in KEEP_EDITION_TYPES:
            continue
        imp = r[2] or ""
        if any(pat in imp for pat in DROP_IMPRINT_PATTERNS):
            continue
        imp_l = imp.lower()
        if any(pat in imp_l for pat in DROP_IMPRINT_LOWER_PATTERNS):
            continue
        if "=" not in imp and any(pat in imp_l for pat in DROP_IMPRINT_LOWER_PATTERNS_NO_EQ):
            continue
        p = (r[0] or "").replace("-", "")
        if len(p) >= 6:
            prefixes.add(p[:6])
    return prefixes


_SID_AUTH_IDX: dict | None = None
_SID_VOLNUM_IDX: dict | None = None


def _build_author_vol_index(con: sqlite3.Connection) -> None:
    """homonym guard用: sid→正規化著者名集合 / sid→巻番号集合 を1回build。"""
    global _SID_AUTH_IDX, _SID_VOLNUM_IDX
    if _SID_AUTH_IDX is not None:
        return
    _SID_AUTH_IDX = {}
    for sid, name in con.execute(
        "SELECT sa.series_id, m.name FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id"
    ):
        _SID_AUTH_IDX.setdefault(sid, set()).add(re.sub(r"[\s　・･,，]", "", name or ""))
    _SID_VOLNUM_IDX = {}
    for sid, num in con.execute(
        "SELECT e.series_id, v.number FROM volumes v JOIN editions e ON e.id=v.edition_id WHERE v.number IS NOT NULL"
    ):
        _SID_VOLNUM_IDX.setdefault(sid, set()).add(num)


def _is_homonym(main_id: int, cand_id: int) -> bool:
    """別作homonym判定: 共通著者が無く かつ 巻番号が重複(=各々独立した完結作)なら True。
    ★FULL SWING型(同名別qid)は共通著者ありで False=merge維持。 原作/作画(相補巻)も重複無しで
    False=merge維持。 JIPANG(速水翼)≠ジパング(かわぐち)等(別著者+巻重複)のみ True=分離。"""
    au = _SID_AUTH_IDX or {}
    vn = _SID_VOLNUM_IDX or {}
    ma, ca = au.get(main_id, set()), au.get(cand_id, set())
    if not ma or not ca or (ma & ca):
        return False  # 著者不明 or 共通著者あり → homonym扱いしない(安全側=merge)
    mv, cv = vn.get(main_id, set()), vn.get(cand_id, set())
    if not mv or not cv:
        return False
    # ∩/min(=小さい方の何割が重複)。 JIPANG[1,2,3]⊂ジパング[1..46]=3/3=1.0=別作。
    # 巻数差で薄まるJaccardでなくmin基準(片方が完全に他方の巻番号域に被る=独立した別作)。
    overlap = len(mv & cv) / min(len(mv), len(cv))
    return overlap >= 0.5  # 別著者 かつ 小さい方の半数以上が巻番号重複 = 別作


_MERGE_EXC = None


def find_related_series_ids(con: sqlite3.Connection, main: dict) -> list[int]:
    """main series と 関連 series id を 返す。

    cluster 分裂で 同一作品の volumes が 別 series row に 散らばってる cases を 統合する。

    rules:
      - main 自身
      - 同 qid で title が case-insensitive 一致
      - 同 title (= 完全一致 + 末尾 punct strip 後) で qid IS NULL な orphan
      - title_kana + punct suffix 一致 (= ローマ字/カタカナ 表記揺れ)
      - **publisher group check**: main の publisher と 候補の publisher が 別 (= 6桁
        ISBN prefix で 別 系列) なら merge しない (= 銀河英雄伝説 道原版 徳間 vs
        藤崎竜版 集英社 の 誤統合 防止)
    """
    cur = con.cursor()
    ids = {main["id"]}
    main_title_lower = (main["title"] or "").lower()
    main_title_strip = _strip_trailing_punct(main["title"])
    main_kana = main.get("title_kana") or ""
    main_punct = _title_punct_suffix(main["title"])
    main_pubs = get_publisher_prefixes(con, main["id"])

    def pub_compatible(cand_id: int) -> bool:
        """候補の major publisher (= 最多 vol publisher prefix) が main の publishers
        set に 含まれる か 候補 不明なら merge OK。

        - 銀英伝 117723 (= 主 集英社 ヤング ジャンプ 33 vols、 副 徳間 アニメ 6 vols)
          → major=集英社 978408、 道原 main pubs={978419} → skip
        - ドラえもん 78712 (= 主 小学館 てんとう虫 36、 副 中公 35)
          → major=小学館 978409、 main pubs={978409} → merge OK
        """
        if not main_pubs:
            return True
        cand_major = get_major_publisher_prefix(con, cand_id)
        if not cand_major:
            return True
        return cand_major in main_pubs

    # 同 qid で title case-insensitive 一致
    if main.get("qid"):
        for r in cur.execute(
            "SELECT id, title FROM series WHERE qid=?", (main["qid"],)
        ).fetchall():
            if (r[1] or "").lower() == main_title_lower and pub_compatible(r[0]):
                ids.add(r[0])
    # 同 title (= 末尾 punct strip 後) で qid 無し orphan (= ★索引で O(1)、 全表scan回避)
    _build_title_strip_index(con)
    for sid in _TITLE_STRIP_INDEX.get(main_title_strip, []):
        if pub_compatible(sid):
            ids.add(sid)
    # title_kana + punct suffix 一致 (= romaji/katakana 表記揺れ cluster)
    # 安全策: 片方が ASCII (= ローマ字表記、 e.g. 'BAKUMAN。', 'Hunter×hunter') の cases のみ。
    # でないと 'テレビアニメ版 犬夜叉' と '犬夜叉' (= 両方 kana='イヌヤシャ') が
    # 誤 merge され、 別作品 が 統合されてしまう。
    # kana は normalize (= 空白/×/中黒 strip) で 'ハンター ハンター' と
    # 'ハンター × ハンター' を 同 'ハンターハンター' として 比較。
    main_title = main["title"] or ""
    main_is_ascii = _is_ascii_title(main_title)
    main_kana_norm = _normalize_kana(main_kana)
    if main_kana_norm:
        # cache から 同 normalized kana の series を 即取得 (= 旧 full table scan 回避)
        _build_kana_index(con)
        for sid, other_title, _other_kana in _KANA_INDEX.get(main_kana_norm, []):
            if sid == main["id"]:
                continue
            other_title = other_title or ""
            other_is_ascii = _is_ascii_title(other_title)
            if not (main_is_ascii or other_is_ascii):
                continue
            if _title_punct_suffix(other_title) == main_punct and pub_compatible(sid):
                ids.add(sid)
    # transitive expansion: 既に merge 済 ids の titles から 同 qid +
    # case-insensitive title match を 追加探索 (= e.g. HUNTER で kana=NULL な
    # 'HUNTER×HUNTER' cluster を 'Hunter×hunter' cluster 経由で 拾う)
    merged_titles_lower = set()
    if ids:
        ph = ",".join("?" for _ in ids)
        for r in cur.execute(
            f"SELECT title, qid FROM series WHERE id IN ({ph})", list(ids)
        ).fetchall():
            if r[0]:
                merged_titles_lower.add((r[0].lower(), r[1] or ""))
    for t_lower, q in merged_titles_lower:
        # 同 qid + title case-insensitive 一致 で merge (= 安全: ASCII variant 同士)
        if q:
            for r in cur.execute(
                "SELECT id, title FROM series WHERE qid=?", (q,)
            ).fetchall():
                if (r[1] or "").lower() == t_lower and pub_compatible(r[0]):
                    ids.add(r[0])
        # qid 無し orphan で title case-insensitive 一致 (= ★索引で O(1)、 LOWER()全表scan回避)
        for sid in _TITLE_LOWER_NULL_INDEX.get(t_lower, []):
            if pub_compatible(sid):
                ids.add(sid)
    # ★ merge.yml の merge_sids 強制統合 (= 個別判断、 既存 logic で 漏れる
    # 表記揺れ / 著者振り分け差異 等 を ユーザ明示で 統合)
    merge_sids_map = get_merge_sids(con)
    for sid in list(ids):
        if sid in merge_sids_map:
            ids.update(merge_sids_map[sid])
    # ★ drop済(非掲載)series を merge cluster から除外。
    #   同題auto-mergeで フィルムコミック等(non-manga-drop登録済)が 実ページ(コミカライズ
    #   /本編)に巻として混入するのを防ぐ。 main自身はmain loopでdrop判定通過済なので必ず保持。
    if _DROP_SERIES_KEYS and len(ids) > 1:
        keep = {main["id"]}
        ph = ",".join("?" for _ in ids)
        for r in cur.execute(
            f"SELECT id, series_key FROM series WHERE id IN ({ph})", list(ids)
        ).fetchall():
            if r[1] not in _DROP_SERIES_KEYS:
                keep.add(r[0])
        ids = keep
    # ★homonym guard(実行時): main と「共通著者なし＋巻番号重複」の候補をclusterから除外。
    #   JIPANG(速水翼)≠ジパング(かわぐち)等の読み/題衝突mergeを構造的に阻止。
    #   FULL SWING型(同名別qid)=共通著者ありでmerge維持(regression無し)。原作/作画=相補巻でmerge維持。
    if len(ids) > 1:
        _build_author_vol_index(con)
        ids = {i for i in ids if i == main["id"] or not _is_homonym(main["id"], i)}
    # ★merge例外seed(2026-07-03 ドカベン発): 同qidスピンオフ(プロ野球編/スーパースターズ編)が
    #   本編clusterに吸われ番号衝突で不可視化する型を、明示ペアでblock(git追跡・対称)。
    global _MERGE_EXC
    if _MERGE_EXC is None:
        _MERGE_EXC = set()
        _mep = ROOT / "data" / "seeds" / "merge-exceptions.yml"
        if _mep.exists():
            for pair in (yaml.safe_load(_mep.read_text(encoding="utf-8")) or {}).get("blocks", []):
                if isinstance(pair, list) and len(pair) == 2:
                    _MERGE_EXC.add(frozenset(pair))
    if _MERGE_EXC and len(ids) > 1:
        ids = {i for i in ids if i == main["id"] or frozenset({main["id"], i}) not in _MERGE_EXC}
    return list(ids)


# ★著者名に紛れた「pub. 年」アーティファクトを除去(db-v2 mangaka 189件の汚染)。
#   例: 「Aipub. 2025」→「Ai」 / 「HIKARIpub. 2022」→「HIKARI」 / 「Sugar.Pub. 2021」→「Sugar」。
#   「pub. 19xx/20xx(.月)」は実著者名に現れない=機械的に安全に剥がせる。 種2不変・promote出力時のみ。
_AUTHOR_PUB_RE = re.compile(r'\s*[\(（]?\s*\.?\s*pub\.?\s*(?:19|20)\d\d(?:\.\d+)?\s*[\)）]?\s*$', re.I)

def _clean_author_name(n: str) -> str:
    return _AUTHOR_PUB_RE.sub('', str(n or '')).strip()


# ★著者override(楽天種突合+多ソース回収で確証ある分のみ。 slug単位で本番著者を是正。 種2不変overlay)
_AUTHOR_OVERRIDES = None
def _load_author_overrides() -> dict:
    global _AUTHOR_OVERRIDES
    if _AUTHOR_OVERRIDES is None:
        p = ROOT / "data" / "seeds" / "author-overrides.json"
        _AUTHOR_OVERRIDES = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _AUTHOR_OVERRIDES


_EDITION_OVERRIDES = None


def _load_edition_overrides() -> dict:
    """教育系の年代版分離/補完を本番durability化 (= preview編集を seed 化、 promote が editions を置換)。"""
    global _EDITION_OVERRIDES
    if _EDITION_OVERRIDES is None:
        p = ROOT / "data" / "seeds" / "edition-overrides.json"
        _EDITION_OVERRIDES = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _EDITION_OVERRIDES


_ISBN_FILL = None


def _load_isbn_fill() -> dict:
    """★ガラスの仮面型ISBN補充 seed (2026-07-18)。旧刊初版書誌のISBN欠け巻に、
    Wiki×楽天等2ソース確証済みの現行刷ISBNを純粋補充する。
    形式: {slug: [{edition, number, isbn13, release_date?}, ...]}
    ★空欄のみ埋める(既存isbn13は不可侵)。release_dateはseedが持つ時だけ確定日で置換。"""
    global _ISBN_FILL
    if _ISBN_FILL is None:
        p = ROOT / "data" / "seeds" / "isbn-fill.json"
        _ISBN_FILL = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _ISBN_FILL


def _load_status_corrections() -> dict:
    """★Wiki検証済みの完結漏れ是正(2026-07-09)。slug→{status,year_ended,wiki_url}。種3不変を汚さず可逆。"""
    p = ROOT / "data" / "seeds" / "status-corrections.yml"
    if p.exists():
        return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("corrections", {})
    return {}


_STATUS_CORR = _load_status_corrections()


def get_authors(con: sqlite3.Connection, series_id: int) -> list[dict]:
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    rows = cur.execute(
        """
        SELECT m.name, sa.role
        FROM series_authors sa
        JOIN mangaka m ON m.id = sa.mangaka_id
        WHERE sa.series_id = ?
        """,
        (series_id,),
    ).fetchall()
    return [{"name": _clean_author_name(r["name"]), "role": r["role"]} for r in rows]


def edition_passes_filter(ed_row: dict) -> bool:
    """edition の type / imprint で 本編判定。 step B filter。"""
    if ed_row["type"] not in KEEP_EDITION_TYPES:
        return False
    imp = ed_row["imprint"] or ""
    for pat in DROP_IMPRINT_PATTERNS:
        if pat in imp:
            return False
    imp_l = imp.lower()
    for pat in DROP_IMPRINT_LOWER_PATTERNS:
        if pat in imp_l:
            return False
    # 'complete works' 等 「=」 並列表記 除く 英訳 全集 系
    if "=" not in imp:
        for pat in DROP_IMPRINT_LOWER_PATTERNS_NO_EQ:
            if pat in imp_l:
                return False
    return True


# AniList genre → master key 対応(種a/種3 カテゴリ統合。 Hentai は除外=成年フラグで処理)
ANILIST_GENRE_TO_MASTER = {
    "Romance": "romance", "Comedy": "comedy", "Drama": "drama", "Action": "action",
    "Fantasy": "fantasy", "Slice of Life": "slice-of-life", "Adventure": "adventure",
    "Sci-Fi": "sci-fi", "Mystery": "mystery", "Horror": "horror", "Sports": "sports",
    "Mecha": "mecha", "Music": "music", "Thriller": "suspense",
    "Supernatural": "supernatural", "Ecchi": "ecchi", "Psychological": "mind-game",
    "Mahou Shoujo": "mahou-shoujo",
}


def _sanitize_volnum(number, release_date, volume_label):
    """誤 parse された巻番号を 0 (= 号扱い) に降格:
      - 季刊/年刊 issue の『年』 (= 「2022 春」→ number 2022)
      - ★タイトルの漢数字混入 (= 「千」→1000 / 「人間噂八百」→800 / 「一騎当千」→1000)
    ★実漫画の最大巻数は ちび本当にあった笑える話 236 が最大級、 [237,1899] に正規番号は
    存在しない (= 609/800/999/1000 は全て誤値) ため number≥400 を無条件で誤値判定
    (= ちびの成長余地も確保しつつ外れ値を捕捉)。 release日null/ズレでも確実に捕捉。
    → 既存 number=0 ロジックが、 混在 series は正規巻のみ残し、 号番号は連番化する。"""
    if number and number >= 400:
        return 0
    return number


_EDITION_TYPE_JP = {
    "standard": "通常版", "wideban": "ワイド版", "bunkobon": "文庫版",
    "kanzenban": "完全版", "shinsoban": "新装版", "aizoban": "愛蔵版", "deluxe": "デラックス版",
}
# ★版ブランドの title 内マーカー(優先抽出。 imprint より作品横断ブランドを優先)。
_EDITION_TITLE_MARKERS = [
    "CLAMP PREMIUM COLLECTION", "CLAMP CLASSIC COLLECTION",
    "完全版", "新装版", "愛蔵版", "復刻版", "オールカラー", "カラー版",
]


def _sep_edition_label(src_title: str, imprint: str | None, etype: str, volumes: list[dict]) -> str:
    """separate_editions 版の人間可読ラベル。 = 版名 +（年範囲）。
    版名 = ①title内ブランドマーカー(CLAMP PREMIUM等) ②imprint ③type日本語名 の順。
    同 imprint 別年(KCデラックス 1994/2002/2022)も 年で 区別できる。"""
    name = None
    for m in _EDITION_TITLE_MARKERS:
        if m in (src_title or ""):
            name = m
            break
    if not name:
        name = (imprint or "").strip() or _EDITION_TYPE_JP.get(etype, etype) or "通常版"
    yrs = sorted((v.get("release_date") or "")[:4] for v in volumes if v.get("release_date"))
    if yrs:
        y0, y1 = yrs[0], yrs[-1]
        name += f"（{y0}）" if y0 == y1 else f"（{y0}–{y1}）"
    return name


def get_editions_with_volumes(con: sqlite3.Connection, series_ids: list[int] | int) -> list[dict]:
    """editions + volumes を まとめて取得し、 同 type editions を 1 つに merge。

    merge logic (= 同 series 内の 同 type editions = 限定版/DVD付き 等 packaging variant が
                  imprint 違いで 分裂しているため):
      - imprint 違いの 同 type editions を 1 つに統合
      - volume number で dedup、 同 number は 最古 release_date の entry を採用
      - 統合後 edition の imprint = 最多 volumes を持つ imprint
      - label は 最多 volumes を持つ edition から
    """
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    if isinstance(series_ids, int):
        series_ids = [series_ids]
    placeholders = ",".join("?" for _ in series_ids)
    # ★renumber(巻割れ統合): 全巻が個別題の0巻/extra本 → 全巻を発売日順に 1..N 連番付与。
    #   cm104凍結のorphanを著者+題で merge した群(series-merge.yml の renumber:true)。
    #   ISBN重複は除去。 1ページにN巻として正しく表示する(by_num collapse を回避)。
    if get_renumber_sids(con) & set(series_ids):
        from collections import Counter as _Counter
        _rows = cur.execute(
            f"SELECT v.*, e.type AS _etype, e.imprint AS _eimprint, e.series_id AS _sid "
            f"FROM volumes v JOIN editions e ON e.id=v.edition_id "
            f"WHERE e.series_id IN ({placeholders})", series_ids).fetchall()
        _excl_isbn = get_art_book_exclude_isbn()
        # ★volume-exclude(全体除外集合)も尊重(2026-07-27 あなたのオモチャ: 新装版再販ISBNが
        #   別巻として混入する型。renumber経路だけ素通りだった)
        _passed = [r for r in _rows if edition_passes_filter(
            {"type": r["_etype"], "imprint": r["_eimprint"]})
            and _norm_isbn(r["isbn13"]) not in _excl_isbn
            and _norm_isbn(r["isbn13"]) not in _all_excluded_isbns()]
        # ★日付=精密化チェーン(override>種2>NDL補完seed)で並べる(2026-07-27: 種2日付欠落巻が
        #   renumber順を壊していた。emitも同じ実効日付)
        _rds = get_release_date_supplement()
        _rdo = get_release_date_override()
        def _rn_date(r):
            ni = _norm_isbn(r["isbn13"])
            return _rdo.get(ni) or r["release_date"] or _rds.get(ni)
        # ★代表巻 = (source series_id, 巻番号) 単位で最古release→最小ISBN。
        #   同一書籍の別版ISBN(通常版/文庫版等・同番号)を別巻に数えない = 過剰巻数を防ぐ。
        #   ★sid単位だった旧実装は、1sidが別の本を複数持つ時(VPアンソロ第1集+第3集が同sid)に
        #   2冊目以降を取りこぼした(2026-07-07是正)。番号が違えば別書籍として代表を立てる。
        _by_sid: dict = defaultdict(list)
        for r in _passed:
            _by_sid[(r["_sid"], r["number"])].append(r)
        _reps = [min(rs, key=lambda v: (_rn_date(v) or "9999-99", v["isbn13"] or ""))
                 for rs in _by_sid.values()]
        _reps.sort(key=lambda v: (_rn_date(v) or "9999-99", v["isbn13"] or ""))
        # ★巻題の搬送(2026-07-27 ユーザ指示「ソーサリアン方式で題名だけ入れて」):
        #   巻割れ統合の各巻は「元クラスタの題」がその巻の個別題(世紀末☆ダーリン2006 /
        #   ハニ太郎です。の「だって〜」等)。群内に複数の題がある時だけ title_display に載せる
        #   (単一題の群=真の番号巻なので付けない)。
        _stitles = {r["id"]: r["title"] for r in cur.execute(
            f"SELECT id, title FROM series WHERE id IN ({placeholders})", series_ids)}
        _multi = len({t for t in _stitles.values() if t}) > 1
        _rvols = [{"number": i + 1, "volume_label": v["volume_label"], "isbn13": v["isbn13"],
                   "release_date": _rn_date(v), "cover_url": v["cover_url"], "asin": v["asin"],
                   **({"title_display": _stitles[v["_sid"]]}
                      if _multi and _stitles.get(v["_sid"]) else {})}
                  for i, v in enumerate(_reps)]
        if not _rvols:
            return []
        _impc = _Counter(r["_eimprint"] for r in _passed if r["_eimprint"])
        return [{"type": "standard", "label": "通常版",
                 "imprint": _impc.most_common(1)[0][0] if _impc else "",
                 "year_started": None, "year_ended": None, "volumes": _rvols}]
    eds = cur.execute(
        f"SELECT * FROM editions WHERE series_id IN ({placeholders})", series_ids
    ).fetchall()
    # ★STEP5: 重複巻 dedup の決定的 tie-break。 同 number に複数 ISBN が compete する時、
    #   ★多数派出版者線(= series内で巻数最多の出版線 = 主たる版/通常版)を ★最優先 し、
    #   その中で 最古 release_date、 最終は 最小 ISBN で完全決定化(= rebuild で flip しない)。
    #   ★2026-06-22 是正: 旧実装は「日付優先」だったため、 本物巻が release_date 欠落(None)の時に
    #   ★日付を持つ別社の混入巻に負けて化ける穴があった(菜 #4/#6型)。 多数派出版線を先に置いて封鎖。
    #   出版者線キーは ★_jp_pub_prefix(可変長の出版者記号を正確抽出。 isbn[:9]固定長は大手を誤分割)。
    _pfreq: dict[str, int] = {}
    for (_isbn,) in cur.execute(
        f"SELECT v.isbn13 FROM volumes v JOIN editions e ON e.id=v.edition_id "
        f"WHERE e.series_id IN ({placeholders}) AND v.isbn13 IS NOT NULL", series_ids
    ):
        _p = _jp_pub_prefix(_isbn)
        _pfreq[_p] = _pfreq.get(_p, 0) + 1

    _rdsupp = get_release_date_supplement()  # release_date欠落巻のNDL補完日付(isbn→date)
    _rdovr = get_release_date_override()      # ★発売日逆行是正の強制上書き(種2値より優先)

    def _eff_date(isbn, rd):
        # ★強制override(再版日→初版日正規化)が有ればそれを最優先。
        # 無ければ 種2の発売日、 それも無ければ NDL補完seed。
        ni = _norm_isbn(isbn)
        if ni in _rdovr:
            return _rdovr[ni]
        return rd or _rdsupp.get(ni)

    def _dedup_key(isbn, rd):
        isbn = isbn or ""
        # ★volume-exclude予定ISBNは必ず負けさせる(こち亀vol1=ノベライズが偽日付タイ+最小ISBNで
        #   真巻に勝ち、その後の除去でvol1消失した穴 2026-07-07)。
        _vex = 1 if _norm_isbn(isbn) in _all_excluded_isbns() else 0
        # 多数派出版者線を最優先(降順) → その中で最古日付(NDL補完込み) → 最小ISBN。
        return (_vex, -_pfreq.get(_jp_pub_prefix(isbn), 0), _eff_date(isbn, rd) or "9999-99", isbn)

    # merge_edition_types: true の sid なら shinsoban/aizoban 等 → standard 統合
    merge_edt_sids = get_merge_edition_types(con)
    apply_edt_merge = any(sid in merge_edt_sids for sid in series_ids)
    # ★版統合(opt-in): separate_editions 群は (type × imprint) で別版を分離(畳まない)。
    #   無印は従来通り type 単位で畳む(最古正典)。 blanket化=古典重版爆発のため opt-in 限定。
    sep_editions = bool(get_separate_edition_sids(con) & set(series_ids))
    # type → [edition+volumes] list
    by_type: dict[str, list[dict]] = defaultdict(list)
    for ed in eds:
        if not edition_passes_filter(dict(ed)):
            continue
        # ORDER BY で release_date NULL を 後回し (= date あり record を dedup で 優先採用)
        vols = cur.execute(
            """SELECT * FROM volumes WHERE edition_id=?
               ORDER BY number, (release_date IS NULL), release_date""",
            (ed["id"],),
        ).fetchall()
        # ★画集混在巻を漫画の巻列から除外 (= うる星等に紛れた原画集1巻。 art-book-exclude-isbn.yml)
        _excl_isbn = get_art_book_exclude_isbn()
        if _excl_isbn:
            vols = [v for v in vols if _norm_isbn(v["isbn13"]) not in _excl_isbn]
        if not vols:
            continue
        # number=0 (= 巻号 extract 失敗) 扱い:
        #   - edition 内に 1 つでも numbered vol あれば → number=0 は skip (= 偽 #1 dedup 弊害除去)
        #   - edition 内 全部 number=0 → release_date 昇順で #1, #2,... 連番付与 (= 短編集等)
        # ★年番号サニタイズ(「2022春」= number 2022 を 0=号扱いに降格)
        nonzero_exists = any(_sanitize_volnum(v["number"], v["release_date"], v["volume_label"]) for v in vols)
        # 同 number 内で 1 件採用 (= 初版 representative)。 ★STEP5: _dedup_key で
        #   決定的選択(最古日→支配ISBN線→最小ISBN)。 同 edition 内 dedup。
        primary_vols = []
        if nonzero_exists:
            by_n: dict[int, list] = defaultdict(list)
            for v in vols:
                sn = _sanitize_volnum(v["number"], v["release_date"], v["volume_label"])
                if sn:
                    by_n[sn].append(v)
            for n in sorted(by_n):
                v = min(by_n[n], key=lambda r: _dedup_key(r["isbn13"], r["release_date"]))
                primary_vols.append(
                    {
                        "number": n,
                        "volume_label": v["volume_label"],
                        "isbn13": v["isbn13"],
                        "release_date": _eff_date(v["isbn13"], v["release_date"]),
                        "cover_url": v["cover_url"],
                        "asin": v["asin"],
                    }
                )
        else:
            # 全 vol が number=0 → release_date 順で連番(NDL補完込み)
            vols_sorted = sorted(vols, key=lambda x: _eff_date(x["isbn13"], x["release_date"]) or "9999-99")
            for idx, v in enumerate(vols_sorted, start=1):
                primary_vols.append(
                    {
                        "number": idx,
                        "volume_label": v["volume_label"],
                        "isbn13": v["isbn13"],
                        "release_date": _eff_date(v["isbn13"], v["release_date"]),
                        "cover_url": v["cover_url"],
                        "asin": v["asin"],
                    }
                )
        if not primary_vols:
            continue
        # merge_edition_types: true なら shinsoban/aizoban/kanzenban → standard 統合
        effective_type = ed["type"]
        if apply_edt_merge and effective_type in ("shinsoban", "aizoban", "kanzenban", "deluxe"):
            effective_type = "standard"
        # ★版統合 opt-in: separate_editions 群は source sid 単位で別版を畳まない。
        #   ("type" フィールドは実 edition type を保持 = 後段 output で primary_ed["type"] 採用)
        #   ★sid単位 = imprint共有(KCデラックス通常版/新装版/premium 全部同imprint)でも分離可。
        #    各 source series_id = 1 版 (= MADB の登録単位 = 版違いの単位) という前提。
        group_key = effective_type
        if sep_editions:
            group_key = f"{effective_type}\x00sid{ed['series_id']}"
        by_type[group_key].append(
            {
                "type": effective_type,
                "label": ed["label"],
                "imprint": ed["imprint"],
                "year_started": ed["year_started"],
                "year_ended": ed["year_ended"],
                "volumes": primary_vols,
                "_src_sid": ed["series_id"],  # ★sep版ラベル生成用(出力前にpop)
            }
        )
    # ★ 種4 補完 = volumes-supplement.yml from 該当 sid の vol を 該当 edition_type に 追加
    supp_map = get_supplement_vols(con)
    for sid in series_ids:
        for supp_vol in supp_map.get(sid, []):
            target_type = supp_vol["_edition_type"]
            if apply_edt_merge and target_type in ("shinsoban", "aizoban", "kanzenban", "deluxe"):
                target_type = "standard"
            # ★separate_editions群は補完巻も source sid 単位で該当版へ合流(sid=版単位)。
            #   種4 は supp_map[sid] 由来=紐付き sid が分かるので imprint一致不要・確実。
            target_key = target_type
            if sep_editions:
                target_key = f"{target_type}\x00sid{sid}"
            ed_group = by_type.get(target_key)
            if not ed_group:
                # 新 edition group 作成 (= 補完巻 1 巻のみ)
                ed_group = [{
                    "type": target_type, "label": supp_vol.get("_edition_label") or "通常版",
                    "imprint": supp_vol["_imprint"] or "",
                    "year_started": None, "year_ended": None,
                    "volumes": [],
                }]
                by_type[target_key] = ed_group
            # 既存 ed_group の volumes に追加。 ★同 number が既に在れば skip
            #   (= MADBが後の更新で追いついた巻を 種4 と二重表示しない = 種2優先・自己retire)。
            #   単一edition は後段 by_num dedup が効かないため、 ここで番号重複を防ぐ。
            #   ★volume-exclude 予定のISBN巻・ISBN無し幽霊巻は番号占有と見なさない
            #     (こち亀vol1: ノベライズ混入→除去予定 + ISBN無し旧レコード が番号1を握り
            #      真巻の種4を二重に弾いた 2026-07-07是正)。ISBN付き種4は同番号のISBN無し幽霊を置換。
            clean_vol = {k: v for k, v in supp_vol.items() if not k.startswith("_")}
            _num = clean_vol.get("number")
            def _occupies(v):
                _i = v.get("isbn13")
                return _i is not None and _norm_isbn(_i) not in _all_excluded_isbns()
            existing_nums = {v.get("number") for v in ed_group[0]["volumes"] if _occupies(v)}
            if _num not in existing_nums:
                if clean_vol.get("isbn13"):
                    ed_group[0]["volumes"] = [v for v in ed_group[0]["volumes"]
                                              if not (v.get("number") == _num and not _occupies(v))]
                ed_group[0]["volumes"].append(clean_vol)
    # 全 edition_group の volumes を number 順 sort (= 単一 edition + 補完追加 で 順序崩れ防止)
    def _vol_sort_key(v):
        try: return (0, int(v.get("number") or 0))
        except (ValueError, TypeError): return (1, str(v.get("number") or ""))
    for ed_group in by_type.values():
        for ed in ed_group:
            ed["volumes"].sort(key=_vol_sort_key)
    out = []
    for type_key, ed_group in by_type.items():
        if len(ed_group) == 1:
            out.append(ed_group[0])
            continue
        # 同 type で 複数 edition → merge
        # 全 volumes を集めて number で dedup。 ★STEP5: _dedup_key で決定的選択
        #   (最古日→支配ISBN線→最小ISBN)。 同日competeの非決定を固定。
        by_num: dict[int, dict] = {}
        for ed in ed_group:
            for v in ed["volumes"]:
                n = v["number"]
                cur_v = by_num.get(n)
                if cur_v is None or _dedup_key(v.get("isbn13"), v.get("release_date")) < _dedup_key(cur_v.get("isbn13"), cur_v.get("release_date")):
                    by_num[n] = v
        merged_vols = [by_num[n] for n in sorted(by_num.keys())]
        # 代表 imprint / label 選定:
        #   1. 最古 first vol release_date を 持つ edition (= 元祖 imprint 優先)
        #   2. 同点なら 最多 vol 数
        # 例: ドラえもん で 中公 35 vols (1984~) と てんとう虫 34 vols (1974~) → てんとう虫
        def _ed_priority(e):
            dates = [v["release_date"] for v in e["volumes"] if v["release_date"]]
            first_date = min(dates) if dates else "9999-99"
            return (first_date, -len(e["volumes"]))
        primary_ed = sorted(ed_group, key=_ed_priority)[0]
        out.append(
            {
                "type": primary_ed["type"],  # ★composite group_key でなく実 edition type
                "label": primary_ed["label"],
                "imprint": primary_ed["imprint"],
                "year_started": primary_ed["year_started"],
                "year_ended": primary_ed["year_ended"],
                "volumes": merged_vols,
                "_src_sid": primary_ed.get("_src_sid"),
            }
        )
    # ★MADB誤番号是正: 上下/上中下/前後 が完全に揃っているのに番号が連番でない
    #   (= 「下」を上中下の3番目として number=3 にする系統的バグ。 上下2冊が[1,3]に水増し)
    #   → ラベル順(上<中<下)で 1..N に振り直す。 全DB ~1,677件 + カラーED型。
    #   ★完全な sequence のみ対象 (= 片側欠落の取りこぼしは触らない)。
    for ed_dict in out:
        _fix_complete_sequence_numbers(ed_dict["volumes"])
    # editions を 第1巻 (= 最古 volume) の release_date 昇順 で sort
    def first_vol_date(ed_dict):
        dates = [v["release_date"] for v in ed_dict["volumes"] if v["release_date"]]
        return min(dates) if dates else "9999-99"
    out.sort(key=first_vol_date)
    # ★separate_editions: 版ラベルを「版名（年範囲）」へ再構成(同imprint別年も区別可能に)。
    #   無印ページは従来 label("通常版"等)維持 = sep群のみ。 元title は _src_sid から引く。
    if sep_editions:
        src_sids = [e["_src_sid"] for e in out if e.get("_src_sid")]
        title_of: dict[int, str] = {}
        if src_sids:
            ph = ",".join("?" * len(src_sids))
            title_of = {r[0]: r[1] for r in con.execute(
                f"SELECT id, title FROM series WHERE id IN ({ph})", src_sids)}
        for e in out:
            e["label"] = _sep_edition_label(
                title_of.get(e.get("_src_sid"), ""), e.get("imprint"), e["type"], e["volumes"])
    for e in out:
        e.pop("_src_sid", None)  # ★schema外の内部キーは出力前に除去
    return out


# 上下/前後 ラベルの順位 (= 振り直し時の並び)。 上=前=先頭、 下=後=末尾。
_SEQ_RANK = {"上": 0, "前": 0, "中": 1, "下": 2, "後": 2}
# 認識する完全 sequence (= ラベル集合 → 期待巻数)
_COMPLETE_SEQS = {
    frozenset({"上", "下"}): 2, frozenset({"上", "中", "下"}): 3,
    frozenset({"前", "後"}): 2, frozenset({"前", "中", "後"}): 3,
}


def _fix_complete_sequence_numbers(volumes: list[dict]) -> None:
    """上下/上中下/前後 が完全に揃うのに番号が 1..N でない edition を in-place 振り直し。

    ★MADB系統バグ是正: 「下」が number=3 (上中下の3番目扱い) になり 上下2冊が [1,3] と
    水増し表示される。 ★片側欠落 (= 上 or 下 のみ) は対象外 (= 取りこぼし、 別処理)。
    """
    if not volumes:
        return
    norm = []
    for v in volumes:
        lab = (v.get("volume_label") or "").replace("巻", "").strip()
        norm.append(lab if lab in _SEQ_RANK else None)
    labset = {x for x in norm if x}
    expected = _COMPLETE_SEQS.get(frozenset(labset))
    # 全 volume が sequence ラベル付き かつ 完全集合 かつ 巻数一致
    if expected is None or None in norm or len(volumes) != expected:
        return
    cur_nums = [v.get("number") for v in volumes]
    if cur_nums == list(range(1, expected + 1)):
        return  # 既に正しい連番
    order = sorted(
        range(len(volumes)),
        key=lambda i: (_SEQ_RANK[norm[i]], volumes[i].get("release_date") or "9999-99",
                       volumes[i].get("isbn13") or ""),
    )
    for new_num, idx in enumerate(order, start=1):
        volumes[idx]["number"] = new_num
    volumes.sort(key=lambda v: v["number"])


def clean_vol(v: dict) -> dict:
    """yml に出力する volume dict を 作る (= null を 適切に省略)"""
    o = {"number": v["number"]}
    if v.get("volume_label"):
        o["volume_label"] = v["volume_label"]
    if v.get("title_display"):
        # ★巻個別題の搬送(renumber統合の元クラスタ題=ソーサリアン方式 2026-07-27)
        o["title_display"] = v["title_display"]
    o["asin"] = v.get("asin")
    if v.get("isbn13"):
        o["isbn13"] = str(v["isbn13"])
    else:
        o["isbn13"] = None
    # ★書影を promote 内で直接充填 (= 別 cover stage 廃止)。 override>既存値>seed fallback。
    o["cover_url"] = get_cover_override().get(_norm_isbn(o["isbn13"])) or v.get("cover_url") or _cover_for(o["isbn13"])
    o["release_date"] = _norm_date(v.get("release_date"))  # ★schema形式に正規化(404防止)
    # ★巻説明 = volume-desc seed(isbn13キー)から充填(既存値優先・純粋追加)。 skill volume-desc。
    _desc = v.get("description") or _desc_for(o["isbn13"])
    if _desc:
        o["description"] = _desc
    if v.get("publisher"):
        o["publisher"] = v["publisher"]      # ★版と異なる巻だけ(下の _mark_volume_publishers が付ける)
    if v.get("variants"):
        # ★edition-override等が明示したvariants(特装/限定併存)を保持(2026-07-03。出版社跨ぎ特装=シャイナ・ダルク型はseedペア不可なのでoverride直書き)
        o["variants"] = v["variants"]
    return o


def _mark_volume_publishers(ed: dict) -> None:
    """★版の途中で発行元が変わる作品に、**版と違う巻だけ** publisher を付ける。
    publisherは版に1つしか持てず、従来は巻ISBN群の多数決で1社に丸めていたため
    片方の社が消えていた(2026-07-26 ユーザ指摘。実測1,672版:
    鬼平犯科帳122巻=文藝春秋46+リイド社76 / 静かなるドン54巻=小学館→実業之日本社)。
    ★出所は種2 ISBN→metadata101 の当時社名。 推測はしない(引けない巻は付けない)。"""
    base = (ed.get("publisher") or "").strip()
    if not base:
        return
    for v in (ed.get("volumes") or []):
        ib = v.get("isbn13")
        if not ib:
            continue
        nm = _ISBN2PUB.get(_to_isbn13(str(ib)))
        if nm and nm != base:
            v["publisher"] = nm


def clean_edition(ed: dict) -> dict:
    out = {
        "type": ed["type"],
        "label": ed["label"],
    }
    # publisher = 版の当時社名 (= 種2 ISBN由来、 事実・タブ表示)。 imprint(レーベル)とは別。
    _pub = edition_pub_name(ed)
    if _pub:
        out["publisher"] = _pub
        ed["publisher"] = _pub          # ★巻差分の基準にする
    _mark_volume_publishers(ed)
    if ed.get("imprint"):
        out["imprint"] = ed["imprint"]
    if ed.get("year_started"):
        out["year_started"] = ed["year_started"]
    if ed.get("year_ended"):
        out["year_ended"] = ed["year_ended"]
    out["volumes"] = [clean_vol(v) for v in ed["volumes"]]
    # ★versions[] = 同巻数の別刷/別版を畳んだ刷タブ(タッチ完全復刻版/うる星初版カバー型)。保持。
    if ed.get("versions"):
        out["versions"] = [{
            **({"label": _ver["label"]} if _ver.get("label") else {}),
            **({"publisher": _ver["publisher"]} if _ver.get("publisher") else {}),
            **({"imprint": _ver["imprint"]} if _ver.get("imprint") else {}),
            "volumes": [clean_vol(v) for v in (_ver.get("volumes") or [])],
        } for _ver in ed["versions"]]
    return out


def _apply_cluster_best(con, row, related_ids):
    """merge cluster 内の title variant から最良を row(merged_series)に反映。

    ・中黒(・)是正のみ: 代表が・無で、 cluster に「・を入れただけ(=・除去で代表と一致)」の
      variant が在れば採用 (= シャングリラフロンティア→シャングリラ・フロンティア)。
      ★別 variant(綴り違い)へは変えない=保守的。
    ・★副題の cluster 自動回収は **行わない**: cluster に画集/巻セット/映画等の非本編が
      混じり、 その subtitle が漏れて誤付与される (= one-piece「尾田栄一郎画集」型)。
      副題は seed3.subtitle(手動 curate)/ 種2 代表行 由来のみとする。 代表行自身の
      末尾ゴミ(「.」等)だけは安全に除去。
    ★seed3 override(seed3.title / seed3.subtitle)は build_yml 側で優先されるため、
      ここは 種2 fallback 値の改善に限る (= 手動 curate を上書きしない)。
    """
    if not related_ids:
        return
    ph = ",".join("?" * len(related_ids))
    members = con.execute(
        f"SELECT title FROM series WHERE id IN ({ph})", list(related_ids)).fetchall()

    # --- title: 中黒(・)是正のみ ---
    at = row.get("title") or ""
    if at and "・" not in at:
        base = at.replace("・", "")
        cands = [t for (t,) in members if t and "・" in t and t.replace("・", "") == base]
        if cands:
            row["title"] = min(cands, key=len)  # 最短の・形(余計な・装飾を避ける)

    # --- subtitle: 代表行 自身の末尾ゴミ除去のみ(cluster 回収はしない) ---
    cur = row.get("subtitle")
    if cur:
        cleaned = cur.strip().rstrip(".．。 　")
        if cleaned and cleaned != cur:
            row["subtitle"] = cleaned


def build_yml(
    src_yml: dict,
    series_row: dict,
    authors: list[dict],
    editions: list[dict],
    seed3: dict | None,
    valid_pubs: set,
    valid_mags: set,
    valid_gens: set,
) -> dict:
    """db-v2 + 種3 + 旧 yml の slug / 一部 metadata から 新 yml dict を build。

    旧 yml から流用:
      - slug
      - title_romaji (= ローマ字化は ロジック移植せず 既存値 再利用)
      - anime_first_year / awards / wikipedia_url 等 既存補強
    """
    o: dict = {}
    o["slug"] = _slug_override(src_yml["slug"])
    # title: seed3.title(手動 override)優先 → series_row.title(cluster-best 反映済)。
    # ★_title_force(2026-07-04): 新頁stubが本編series rowを基盤にする時の題強制(激マン!Z&グレート編型)
    o["title"] = _strip_pua(src_yml.get("_title_force") or (seed3 or {}).get("title") or series_row["title"])
    # title_kana は スペース削除 (= MANGAL protocol: ふりがな に空白 入れない)
    # ★フリガナ補正 seed を最優先(種2[series_row]も種3[src_yml]も誤っていた key)。
    corr = load_furigana_corrections().get(series_row["series_key"])
    # 優先: NDL補正(corr) → 種2(db) → MADB補完(fill、 欠落埋め) → src
    fill = load_kana_fill().get(series_row["series_key"])
    raw_kana = ((corr or {}).get("title_kana") or series_row["title_kana"]
                or fill or src_yml.get("title_kana", ""))
    o["title_kana"] = _strip_pua(re.sub(r"[\s　]+", "", raw_kana)) if raw_kana else ""
    if src_yml.get("_kana_force"):  # ★_title_forceのkana版(影響半径=このsrcのみ。正規代入の後で上書き)
        o["title_kana"] = src_yml["_kana_force"]
    # title_romaji = 分かち書きかな(corr_segmented優先)からヘボン式生成。
    seg_kana = (corr or {}).get("title_kana_segmented") or raw_kana
    _rom = romanize_kana(_strip_pua(seg_kana))
    if not _rom and o["title"] and not re.search(r"[一-龠ぁ-んァ-ヶ]", o["title"]):
        # 漢字/かな を含まない=ラテン題(ZERO HOUR等)→ 題名小文字をromajiに
        _rom = o["title"].lower()
    # ★最終fallback: slug(常に存在・小文字romaji形)→ title_romaji を空にしない
    #   (kana末尾の小書き/kana内latin混入で romanize_kana が空を返す35件の床違反是正)
    o["title_romaji"] = _rom or src_yml.get("title_romaji", "") or o["slug"].replace("-", " ")
    # subtitle: ★種3 curate(seed3.subtitle)を最優先 → 種2(series_row.subtitle)fallback。
    #   種3取込=merge時に副題を持たない代表行が選ばれて脱落する問題の是正(2026-06-02)。
    #   edition 名 (= '新装再編版' 等) なら strip (= 全 edition 含む page には不適)。
    sub = (seed3 or {}).get("subtitle") or series_row["subtitle"]
    if sub:    # ★「X : アンコール出版」型は imprint suffix のみ剥がし本文Xは残す
        sub = re.sub(r"\s*[:：]\s*(アンコール出版|Nazomizu Comics?)\s*$", "", sub).strip() or None
    EDITION_NAME_SUBTITLES = {"新装再編版", "新装版", "完全版", "愛蔵版", "文庫版",
                              "ワイド版", "デラックス", "新装新版", "リニューアル版",
                              "廉価版", "新装版コミックス", "新装版", "復刻版"}
    if sub and sub in EDITION_NAME_SUBTITLES:
        sub = None
    if sub and _SUBTITLE_NOISE_RE.search(sub):    # ★出版社/レーベル/形式が副題欄に漏れた物を除去
        sub = None
    if sub:
        o["subtitle"] = _strip_pua(sub)
    sub_kana = (seed3 or {}).get("subtitle_kana") or series_row["subtitle_kana"]
    if sub_kana and sub:
        o["subtitle_kana"] = re.sub(r"[\s　]+", "", sub_kana)

    # 年代: editions の volumes.release_date から 計算
    # year_started = 最も古い edition の 最初の volume year
    # year_ended = 「最初の edition (= 本編初版)」 の 最後の volume year
    #              (= リニューアル版を 含めずに 原作連載終了年を出す)
    def year_of(d: str | None) -> int | None:
        if not d or len(d) < 4:
            return None
        try:
            return int(d[:4])
        except ValueError:
            return None

    all_years = []
    for ed in editions:
        for v in ed["volumes"]:
            y = year_of(v.get("release_date"))
            if y:
                all_years.append(y)
    o["year_started"] = min(all_years) if all_years else src_yml.get("year_started", 2000)

    # year_ended: standard edition の 「最大 vol number の 初版 date」 (= 真の 連載完結年)
    # standard edition が ない (= 文庫/愛蔵 のみ 等) 場合は 全 editions
    # vol 1 の 「reissue date 2000」 が 混入 する のを 避ける ため、 各 vol の MIN
    # (= 初版) を 取り、 最大 vol number の date を 採用
    if editions:
        standard_eds = [ed for ed in editions if ed.get("type") == "standard"]
        target_eds = standard_eds if standard_eds else editions
        per_vol_min_date: dict = {}
        for ed in target_eds:
            for v in ed["volumes"]:
                n = v.get("number")
                d = v.get("release_date")
                if not n or not d:
                    continue
                if n not in per_vol_min_date or d < per_vol_min_date[n]:
                    per_vol_min_date[n] = d
        if per_vol_min_date:
            max_vol = max(per_vol_min_date.keys())
            o["year_ended"] = year_of(per_vol_min_date[max_vol])
        else:
            o["year_ended"] = src_yml.get("year_ended")
    else:
        o["year_ended"] = src_yml.get("year_ended")
    # status は 種3 から。★status-corrections(Wiki検証済み完結是正 2026-07-09)を最優先(種3不変を汚さず可逆)
    _sc = _STATUS_CORR.get(o["slug"])
    if _sc and _sc.get("status"):
        o["status"] = _sc["status"]
        if _sc.get("year_ended"):
            o["year_ended"] = _sc["year_ended"]
    else:
        # ★「不明=完結」既定の廃止+種3status不信任(2026-07-16 ユーザGO・勇者さま型誤完結の是正):
        #   種3のstatusはfill期のAI推測が全件に入っており根拠にならない(76,435全entryがstatus持ち)。
        #   判定 = 「standard版の初版(per_vol_min_date)で新しい巻番号が直近12ヶ月内に出たか」。
        #   出ていれば連載中 / 出ていなければ完結。真の完結は status-corrections(Wiki検証+
        #   完結判定caption=証拠ベース)が最優先で上書きする。新装版/復刻は初版minを動かさないので誤爆しない。
        _st = (seed3 or {}).get("status") or src_yml.get("status")
        _latest_first = ""
        try:
            if per_vol_min_date:
                _latest_first = max(per_vol_min_date.values())
        except NameError:
            pass
        if not _latest_first:
            for _ed in editions:
                for _v in _ed["volumes"]:
                    _rd = str(_v.get("release_date") or "")
                    if _rd > _latest_first:
                        _latest_first = _rd
        _cut = (datetime.date.today() - datetime.timedelta(days=365)).isoformat()
        _recent = bool(_latest_first) and _latest_first[:10] >= _cut[: len(_latest_first[:10])]
        if not _st:
            _st = "ongoing" if _recent else "completed"
        elif _st == "completed" and _recent:
            _st = "ongoing"
        o["status"] = _st
    # status=ongoing なら year_ended は null
    if o["status"] == "ongoing":
        o["year_ended"] = None

    # authors / original_authors
    writers, originals = [], []
    for a in authors:
        if a["role"] == "original_author":
            originals.append({"name": a["name"], "role": "writer"})  # 旧 schema 互換
        else:
            writers.append({"name": a["name"], "role": a["role"]})
    if not writers:
        writers = src_yml.get("authors") or [{"name": "(unknown)", "role": "writer_artist"}]
    # ★正規化重複の除去(空白/中黒/ピリオド除去で同一なら先勝ち=「J.P.ホーガン」vs「J.P. ホーガン」)
    def _dedup_authors(lst):
        seen, out = set(), []
        for a in lst:
            nk = re.sub(r"[\s　・.,]", "", a.get("name") or "").lower()
            if nk in seen:
                continue
            seen.add(nk); out.append(a)
        return out
    writers = _dedup_authors(writers)
    originals = _dedup_authors(originals)
    # 著者ヨミ(50音索引用)+ romaji を付与 (= MADB 504 公式ヨミ。 無い著者は素のまま)
    o["authors"] = [enrich_author(w) for w in writers]
    o["original_authors"] = [enrich_author(x) for x in originals]
    # 副次クレジット(編集/監修/訳/装丁/解説/企画/協力 等)= 表示+検索用、 著者でない
    creds = get_author_credits(series_row.get("series_key", ""))
    if creds:
        o["credits"] = creds

    # ★著者override適用(slug単位・confident分のみ。 writer=原作→original_authors / artist・writer_artist→authors)
    _ov = _load_author_overrides().get(o["slug"])
    if _ov and _ov.get("authors"):
        _auth = [a for a in _ov["authors"] if a.get("role") in ("artist", "writer_artist", "editor")]
        _orig = [{"name": a["name"], "role": "writer"} for a in _ov["authors"] if a.get("role") == "writer"]
        if not _auth:   # 原作のみ等 = authors空回避(現role保持)
            _auth = [{"name": a["name"], "role": a.get("role", "writer_artist")} for a in _ov["authors"]]
            _orig = []
        o["authors"] = [enrich_author(a) for a in _dedup_authors(_auth)]
        o["original_authors"] = [enrich_author(a) for a in _dedup_authors(_orig)]
        if _ov.get("credits"):
            o["credits"] = [{"name": c["name"], "role": c.get("role", "編集")} for c in _ov["credits"] if c.get("name")]

    # publisher: 種3 → 旧 yml の 優先で 取得、 master 未定義なら 旧 yml に fallback
    pub_cand = (seed3 or {}).get("publisher") or src_yml.get("publisher")
    if pub_cand and valid_pubs and pub_cand not in valid_pubs:
        pub_cand = src_yml.get("publisher", pub_cand)
    o["publisher"] = pub_cand or "(unknown)"

    # magazine: 種3 由来は AI fill で 旧 master key と 揃ってない 可能性
    # master 未定義時は 旧 yml に fallback、 それでも未定義なら brand から推定、
    # 最後に null
    mag_cand = (seed3 or {}).get("magazine") or src_yml.get("magazine")
    if mag_cand and valid_mags and mag_cand not in valid_mags:
        old_mag = src_yml.get("magazine")
        mag_cand = old_mag if old_mag and old_mag in valid_mags else None
    # brand → magazine 推定 (= 種3 fill 漏れ 補完)
    if not mag_cand:
        mag_cand = infer_magazine_from_brand(editions, valid_mags)
    o["magazine"] = mag_cand

    # ★"other"は出荷しない(2026-07-13 ユーザ裁定: 意味がないカテゴリ。不明=キー自体を出さない=UI非表示)
    _demo = (seed3 or {}).get("demographic") or src_yml.get("demographic", "shounen")
    if _demo and _demo != "other":
        o["demographic"] = _demo
    else:
        o.pop("demographic", None)

    # genres: 種3 由来 keys を validate
    # ★"other"は出荷しない(2026-07-13 ユーザ裁定: 意味がないカテゴリ。不明=空=索引ガードも空を許容)
    genres_cand = (seed3 or {}).get("genres") or src_yml.get("genres") or []
    genres_cand = [g for g in genres_cand if g != "other"]
    if valid_gens:
        filtered = [g for g in genres_cand if g in valid_gens]
        if not filtered:
            filtered = [g for g in (src_yml.get("genres") or []) if g != "other" and g in valid_gens]
        genres_cand = filtered
    o["genres"] = genres_cand

    # synopsis: ★種3 の AI 生成文は使わない(ユーザ指示 2026-05-31)。
    #   種a description の和訳を enrich(anilist_id)経由で join。 無ければ空(=消去)。
    o["synopsis"] = ""

    # anime / alternative_titles
    anime_adapted = (seed3 or {}).get("anime_adapted")
    if anime_adapted is None:
        anime_adapted = src_yml.get("anime_adapted")
    if anime_adapted is not None:
        o["anime_adapted"] = anime_adapted
    if "anime_first_year" in src_yml:
        o["anime_first_year"] = src_yml["anime_first_year"]

    # alt_en 優先順: 種3 (= ユーザ手動修正) > 種3 で明示削除 (= en: null) > db-v2 (= 種1直) > src_yml
    # L3 計画 Phase C: 旧 logic は 種3 を 全く参照せず、 _fix-seed3-en-values.py 修正が 永久 未反映 bug。
    seed3_alt = (seed3 or {}).get("alternative_titles") or {}
    src_alt = src_yml.get("alternative_titles") or {}
    db_alt_en = series_row["title_official_en"]

    # 種3 で 「en: null」 明示 = 削除意思 (= ranma 等)
    if "en" in seed3_alt and seed3_alt.get("en") is None:
        merged_alt = {k: v for k, v in seed3_alt.items() if v is not None}
    else:
        merged_alt = dict(src_alt)
        # 種3 値で 上書き (= ユーザ手動修正 を 最優先)
        for k, v in seed3_alt.items():
            if v is not None:
                merged_alt[k] = v
        # db-v2 alt_en fallback (= 種3/旧 yml に en なければ)
        if db_alt_en and "en" not in merged_alt:
            merged_alt["en"] = db_alt_en

    if merged_alt:
        o["alternative_titles"] = merged_alt

    if "awards" in src_yml:
        o["awards"] = src_yml["awards"]
    if series_row["qid"]:
        o["wikidata_qid"] = series_row["qid"]
    if "wikipedia_url" in src_yml:
        o["wikipedia_url"] = src_yml["wikipedia_url"]

    o["editions"] = [clean_edition(ed) for ed in editions]

    # work-level publisher (設計b): 全版の社キー distinct + 代表(最多巻の社キー)。
    # 種2 ISBN由来を最優先。 1社も解決できない時のみ L1597 の seed3/src fallback を残す。
    from collections import Counter as _C
    _pv = _C()
    for ce in o["editions"]:
        k = pub_key_of(ce.get("publisher"))
        if k:
            _pv[k] += len(ce.get("volumes", []))
    if _pv:
        o["publishers"] = sorted(_pv)
        o["publisher"] = _pv.most_common(1)[0][0]  # 代表 = 最多巻のキー
    else:
        o["publishers"] = []
    # ★edition-override (= 教育系の年代版分離/NDL補完の本番durability。 最終確定 editions/著者を置換)
    _eov = _load_edition_overrides().get(o["slug"])
    if _eov:
        if _eov.get("editions"):
            o["editions"] = [clean_edition(ed) for ed in _eov["editions"]]
        # ★年の明示指定(override直書き)最優先=再版edition混在で連載期間が化ける時の確定手段。
        #   ★editions有無を問わず適用(2026-07-09: あしたのジョー=1968連載だがMANGALは1972再版のみ保有→year単独overrideで是正)。
        #   (ヤマトひおあきら版: 原作連載1974-83だがMF文庫再版2005が混じり年が化けた 2026-07-08)
        if _eov.get("year_started") is not None:
            o["year_started"] = _eov["year_started"]
            o["year_ended"] = _eov.get("year_ended")
        # ★出版年の是正: editions確定時かつ年明示無し時のみ、交差しないなら再計算
        #   (上杉謙信: 種2由来1969-2004 vs 確定巻2005-2006=交差なし→再計算。
        #    タッチ: 1981-1987は確定巻1981-2013と交差→連載年を保持=復刻年で延ばさない 2026-07-07)
        if _eov.get("editions") and _eov.get("year_started") is None:
            _yrs = [int(str(v["release_date"])[:4]) for ed in o["editions"] for v in (ed.get("volumes") or [])
                    if v.get("release_date") and str(v["release_date"])[:4].isdigit()]
            if _yrs:
                _ys, _ye = o.get("year_started"), o.get("year_ended")
                _cur = (_ys or 9999, _ye or _ys or 9999)
                if _cur[1] < min(_yrs) or _cur[0] > max(_yrs):
                    o["year_started"] = min(_yrs)
                    if _ye is not None or o.get("status") == "completed":
                        o["year_ended"] = max(_yrs)
        # ★title/kana override(2026-07-10 ToHeart2族: latin書誌題クラスタの頁を正題で建てる。
        #   kanaは必ずNDL/楽天ヨミ確証を添えること=捏造禁止)
        if _eov.get("title"):
            o["title"] = _eov["title"]
        if _eov.get("title_kana"):
            o["title_kana"] = _eov["title_kana"]
        if _eov.get("title_romaji"):
            o["title_romaji"] = _eov["title_romaji"]
        if _eov.get("publisher"):
            o["publisher"] = _eov["publisher"]
            o["publishers"] = _eov.get("publishers") or [_eov["publisher"]]
        if _eov.get("authors"):
            o["authors"] = [enrich_author(a) for a in _eov["authors"]]
        if _eov.get("original_authors") is not None:
            # ★空リスト[]=原作クレジット全消去も有効(2026-07-10 高橋K: 混入クラスタ由来のGoRA等を剥がす)
            o["original_authors"] = [enrich_author(a) for a in _eov["original_authors"]]
        if _eov.get("credits"):
            o["credits"] = [{"name": c["name"], "role": c.get("role", "編集")} for c in _eov["credits"] if c.get("name")]
        if _eov.get("related_pin"):
            o["related_pin"] = list(_eov["related_pin"])
    # ★isbn-fill (= ガラスの仮面型: ISBN欠け巻へ確証済み現行刷ISBNを補充。空欄のみ・上書き禁止)
    _fills = _load_isbn_fill().get(o["slug"])
    if _fills:
        _fmap = {(f["edition"], f["number"]): f for f in _fills}
        for _ed in o.get("editions") or []:
            for _v in _ed.get("volumes") or []:
                _f = _fmap.get((_ed.get("type"), _v.get("number")))
                if _f and not _v.get("isbn13"):
                    _v["isbn13"] = str(_f["isbn13"])
                    if _f.get("release_date"):
                        _v["release_date"] = _norm_date(_f["release_date"])
                    if not _v.get("cover_url"):
                        _v["cover_url"] = (get_cover_override().get(_norm_isbn(_v["isbn13"]))
                                           or _cover_for(_v["isbn13"]))
    return o


def build_artbook(
    con: sqlite3.Connection,
    series_key: str,
    meta: dict,
    sid: int,
    group_sids: list[int],
    seed3: dict,
) -> dict | None:
    """画集 (ArtBook) dict を build (= 設計 §1-3)。 漫画と別軽量型: editions を持たず
    volumes 直下。 volumes は通常 Volume と同形 = 書影・アフィリンクが同じ仕組みで効く。

    ★slug は暫定 `artbook-<sid>` (= 一意・決定的)。 ローマ字 slug 生成器が未実装(GO待ち=
      pending_slug_generator)なため。 art-books.v2 は再生成中間物で production を固定しない。
    ★linked_works は build/表示段 (step5) で計算 (= 作画家→漫画 slug 群)。 ここでは空。
    """
    editions = get_editions_with_volumes(con, group_sids)
    # ★種4補完(画集にも取込もれ巻がある=INTRON DEPOT等。manga経路と同じsupp_mapを合流 2026-07-07)
    supp_map = get_supplement_vols(con)
    supp_flat = []
    for _sid in group_sids:
        for sv in supp_map.get(_sid, []):
            supp_flat.append({k: v for k, v in sv.items() if not k.startswith("_")})
    if not editions and not supp_flat:
        return None
    # 全 edition の volumes を集約 → ISBN dedup → 発売日順 → 1..N 連番 (画集は版分岐が薄い)
    seen_isbn: set[str] = set()
    flat: list[dict] = []
    for ed in (editions or []):
        for v in ed["volumes"]:
            isbn = _norm_isbn(v.get("isbn13"))
            if isbn and isbn in seen_isbn:
                continue
            if isbn:
                seen_isbn.add(isbn)
            flat.append(v)
    for v in supp_flat:  # 種4巻(既存ISBNはdedupで弾く)
        isbn = _norm_isbn(v.get("isbn13"))
        if isbn and isbn in seen_isbn:
            continue
        if isbn:
            seen_isbn.add(isbn)
        flat.append(v)
    if not flat:
        return None
    flat.sort(key=lambda v: (v.get("release_date") or "9999-99", v.get("number") or 0,
                             _norm_isbn(v.get("isbn13"))))
    volumes = []
    for i, v in enumerate(flat, start=1):
        cv = clean_vol(v)
        cv["number"] = i
        volumes.append(cv)

    row = con.execute("SELECT * FROM series WHERE id=?", (sid,)).fetchone()
    cols = [d[0] for d in con.execute("SELECT * FROM series WHERE id=?", (sid,)).description]
    series_row = dict(zip(cols, row)) if row else {}

    s3 = seed3.get(series_key) or {}
    # ★art-books.yml の title 上書き(MADB誤parse是正)を最優先 → seed3 → 種2。
    title = _strip_pua((meta.get("title") or s3.get("title") or series_row.get("title") or "").strip())
    corr = load_furigana_corrections().get(series_key) or {}
    raw_kana = meta.get("title_kana") or corr.get("title_kana") or series_row.get("title_kana") or ""
    title_kana = _strip_pua(re.sub(r"[\s　]+", "", raw_kana)) if raw_kana else ""

    years = [int(v["release_date"][:4]) for v in volumes
             if v.get("release_date") and len(v["release_date"]) >= 4 and v["release_date"][:4].isdigit()]
    qid = series_row.get("qid")

    # 分かち書きフリガナ (= slug生成用)。 NDL spaced 由来 seed。 整合性(nospace==title_kana)確認済。
    seg = get_art_book_segmented().get(series_key)
    o: dict = {
        "slug": f"artbook-{sid}",   # ★暫定 (= 一意決定的、 最終 slug 規則は §6 未決)
        "category": "画集",
        "title": title,
        "title_kana": title_kana,
        "title_romaji": "",          # ★ローマ字化生成器 未実装 (GO待ち)
        "artist": meta.get("artist") or "",
        "adult": bool(meta.get("adult")),
        "linked_works": [],          # ★step5 で計算
        "publisher": series_row.get("publisher_key") or None,
        "year": min(years) if years else None,
        "volumes": volumes,
    }
    if seg:
        o["title_kana_segmented"] = seg
    if meta.get("multi_artist"):
        o["multi_artist"] = True
    if qid and re.fullmatch(r"Q\d+", str(qid)):
        o["wikidata_qid"] = str(qid)
    return o


def load_master_keys() -> tuple[set, set, set]:
    """data/magazines.yml + publishers.yml + genres.yml の 有効 key set を返す。"""
    pub_yml = ROOT / "data" / "publishers.yml"
    mag_yml = ROOT / "data" / "magazines.yml"
    gen_yml = ROOT / "data" / "genres.yml"
    pubs, mags, gens = set(), set(), set()
    if pub_yml.exists():
        with pub_yml.open("r", encoding="utf-8") as f:
            d = _yload(f) or {}
        pubs = set(d.keys())
    if mag_yml.exists():
        with mag_yml.open("r", encoding="utf-8") as f:
            d = _yload(f) or {}
        mags = set(d.keys())
    if gen_yml.exists():
        with gen_yml.open("r", encoding="utf-8") as f:
            d = _yload(f) or {}
        gens = set(d.keys())
    return pubs, mags, gens


def main():
    print(f"loading {SEED3} ...", file=sys.stderr)
    seed3 = load_seed3()
    print(f"  entries: {len(seed3)}", file=sys.stderr)

    valid_pubs, valid_mags, valid_gens = load_master_keys()
    print(
        f"  master keys: pubs={len(valid_pubs)} mags={len(valid_mags)} gens={len(valid_gens)}",
        file=sys.stderr,
    )

    con = sqlite3.connect(DB)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # 既存 v2 dir clean (= --only 時は 全削除せず 該当ページのみ後で上書き)
    # ★Windows: Defender 即時スキャン等で一時ロック(WinError 32)→ リトライ
    if not ONLY_SLUGS:
        import time as _t
        for p in OUT_DIR.glob("*.yml"):
            for _attempt in range(5):
                try:
                    p.unlink()
                    break
                except FileNotFoundError:
                    break          # 既に削除済 = OK
                except PermissionError:
                    _t.sleep(0.3)
            else:
                print(f"  [warn] unlink失敗(ロック継続) skip: {p.name}", file=sys.stderr)
    else:
        print(f"[--only] 対象 slug: {sorted(ONLY_SLUGS)} (= 他ページ温存)", file=sys.stderr)

    # step A: 親 series 検出 map
    print("[step A] 親 series 検出 中 ...", file=sys.stderr)
    parent_map = build_parent_map(con)
    print(f"  検出 spinoff series 数: {len(parent_map)}", file=sys.stderr)
    # ★series-keep: spinoff誤判定で消える独立作をslugで救済(=独立ページ化)。data/seeds/series-keep.yml
    _SPINOFF_KEEP = set()
    _skp = ROOT / "data" / "seeds" / "series-keep.yml"
    if _skp.exists():
        for _e in (yaml.safe_load(_skp.read_text(encoding="utf-8")) or {}).get("keep", []):
            if isinstance(_e, str): _SPINOFF_KEEP.add(_e)
            elif isinstance(_e, dict) and _e.get("slug"): _SPINOFF_KEEP.add(_e["slug"])
    print(f"  series-keep(spinoff救済): {len(_SPINOFF_KEEP)} slug", file=sys.stderr)

    # adult_us(米基準フラグ)= 種a isAdult な series_key + sid→series_key 逆引き
    adult_us_keys = _load_adult_us_map()
    sid2key = {sid: sk for sid, sk in con.execute("SELECT id, series_key FROM series")}
    adult_us_pages = 0
    print(f"  adult_us(種a isAdult)map: {len(adult_us_keys):,} series_key", file=sys.stderr)
    # AniList enrich(productionization)= series_key → {anilist_id, synonyms, genres_anilist, tags}
    enrich_map = _load_anilist_enrich_map()
    enrich_pages = 0
    print(f"  anilist enrich map: {len(enrich_map):,} series_key", file=sys.stderr)
    # synopsis 和訳 map = {anilist_id(str): ja}。 種a description の日本語要約。
    # ★git追跡 seed(高価なAI生成物=種3と同格で永続化。 旧.cache から移行 2026-06-02)。
    _syn_path = ROOT / "data" / "seeds" / "synopsis-ja.json"
    synopsis_ja = json.loads(_syn_path.read_text(encoding="utf-8")) if _syn_path.exists() else {}
    synopsis_pages = 0
    print(f"  synopsis 和訳 map: {len(synopsis_ja):,} anilist_id", file=sys.stderr)
    # ★新刊用 slug-key synopsis(distill AI要約)= anilist_id未マッチの新作に効かせる
    _synslug_path = ROOT / "data" / "seeds" / "distill-synopsis-2026.json"
    synopsis_slug = json.loads(_synslug_path.read_text(encoding="utf-8")) if _synslug_path.exists() else {}
    if "out" in synopsis_slug:
        synopsis_slug["out-mizutamakoto"] = synopsis_slug["out"]  # 同名別作の別slug
    print(f"  synopsis slug map(新刊): {len(synopsis_slug):,} slug", file=sys.stderr)
    # ★新刊著者の統合修正 seed = 再パース済authors(連結著者の分割・役割分離・&デコード)で上書き(再promote durability。 種2不変のまま表示是正)
    _arp_path = ROOT / "data" / "seeds" / "author-reparse-2026.json"
    author_reparse = json.loads(_arp_path.read_text(encoding="utf-8")) if _arp_path.exists() else {}
    author_reparse_pages = 0
    print(f"  著者修正 map(新刊): {len(author_reparse):,} slug", file=sys.stderr)
    # ★巻ISBN除去 = slug単位で過剰統合により混入した別作の巻を除去(docs/overmerge-6-investigation.md)。
    #   ★グローバル除外と違いslug単位=同ISBNが正しい別ページには残る([[feedback_dont_repeat_regrouping_error]])。
    _vex_path = ROOT / "data" / "seeds" / "volume-exclude.yml"
    volume_exclude = {}
    if _vex_path.exists():
        for _e in (yaml.safe_load(_vex_path.read_text(encoding="utf-8")) or {}).get("excludes", []):
            if _e.get("slug") and _e.get("isbn13"):
                volume_exclude.setdefault(_e["slug"], set()).add(_norm_isbn(_e["isbn13"]))
    volume_exclude_pages = 0
    print(f"  巻ISBN除去 map: {len(volume_exclude)} slug", file=sys.stderr)
    # ★版分離 canonical seed (golgo/釣りバカ等の版混在を Wikipedia確定版で上書き)
    edition_canonical = get_edition_canonical()
    edition_canonical_pages = 0
    print(f"  版canonical map: {len(edition_canonical)} slug", file=sys.stderr)
    # ★版付加 seed (extra-editions.yml = 既存版に触れず版を末尾追加。手塚全集タブ等)
    extra_editions_map = get_extra_editions()
    extra_editions_pages = 0
    print(f"  版付加 map: {len(extra_editions_map)} slug", file=sys.stderr)
    # ★数値/bool風の文字列(著者「029」等)を強制引用(JS yaml誤読=schema違反404を封鎖)
    import re as _re_q
    _NUMLIKE_Q = _re_q.compile(r"^[-+]?(\d[\d_]*|\d*\.\d+([eE][-+]?\d+)?|0x[0-9a-fA-F]+|0o[0-7]+)$")
    def _str_rep_q(dumper, data):
        if _NUMLIKE_Q.match(data) or data.lower() in ("true", "false", "null", "yes", "no", "on", "off", "~"):
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)
    yaml.add_representer(str, _str_rep_q)
    # ★キャッチコピー map = {slug: copy}。 高価なAI生成物(別案トーン)=種3同格でgit永続化。
    #   slug キー(=作品ページ単位)。 あらすじ素材から生成、 「わからないものは埋めない」。
    _catch_path = ROOT / "data" / "seeds" / "catch-ja.json"
    catch_map = json.loads(_catch_path.read_text(encoding="utf-8")) if _catch_path.exists() else {}
    catch_pages = 0
    # ★synopsis(slugキー)seed = enrich-catch-synopsis skill用(2026-07-06。anilist synopsis-jaとは別系=非AniList作品向け)
    _synslug_path = ROOT / "data" / "seeds" / "synopsis-slug-ja.json"
    synslug_map = json.loads(_synslug_path.read_text(encoding="utf-8")) if _synslug_path.exists() else {}
    synslug_pages = 0
    print(f"  catch コピー map: {len(catch_map):,} slug", file=sys.stderr)

    # 作品(work)Wikidata QID map = {anilist_id(str): {"qid","label"}}。
    #   ★AniList漫画ID(P8731)経由で一意取得=誤joinゼロ。 著者QID(series.qid)とは別物。
    _wq_path = ROOT / ".cache" / "work-qid-map.json"
    work_qid = json.loads(_wq_path.read_text(encoding="utf-8")) if _wq_path.exists() else {}
    work_qid_pages = 0
    print(f"  作品QID map: {sum(1 for v in work_qid.values() if v):,} anilist_id", file=sys.stderr)

    # 著者ゼロ補完 map = {anilist_id(str): {authors:[{name,role}], original_authors:[name]}}。
    #   ★AniList staff から原作/作画を厳密分離(_build-author-fill-map.py)。
    _af_path = ROOT / ".cache" / "author-fill-map.json"
    author_fill = json.loads(_af_path.read_text(encoding="utf-8")) if _af_path.exists() else {}
    author_fill_pages = 0
    print(f"  著者補完 map(AniList): {len(author_fill):,} anilist_id", file=sys.stderr)

    # MADB再導出の安全fallback = {series_key: {authors,original_authors}}。
    #   ★AniList無しの著者ゼロ用。 外国名除去後の単独日本語著者のみ(原作者誤主著/汚染を回避)。
    _afm_path = ROOT / ".cache" / "madb-author-fill-safe.json"
    author_fill_madb = json.loads(_afm_path.read_text(encoding="utf-8")) if _afm_path.exists() else {}
    author_fill_madb_pages = 0
    print(f"  著者補完 map(MADB安全): {len(author_fill_madb):,} series_key", file=sys.stderr)

    # 雑誌 drop(cm105 雑誌マスター準拠)= series_key 集合。 雑誌は作品でないため除外。
    _mag_path = ROOT / "data" / "seeds" / "magazines-drop.yml"
    mag_drop_keys = set()
    if _mag_path.exists():
        for e in (yaml.safe_load(_mag_path.read_text(encoding="utf-8")) or {}).get("magazines", []):
            if e.get("series_key"):
                mag_drop_keys.add(e["series_key"])
    print(f"  雑誌drop(cm105): {len(mag_drop_keys):,} series_key", file=sys.stderr)

    # 非漫画 drop(= 外国語版/壊れ書誌。 series_key で除外。 種2/種3 不変。 2026-06-02)。
    _nm_path = ROOT / "data" / "seeds" / "non-manga-drop.yml"
    non_manga_keys = set()
    if _nm_path.exists():
        for e in (yaml.safe_load(_nm_path.read_text(encoding="utf-8")) or {}).get("non_manga", []):
            if e.get("series_key"):
                non_manga_keys.add(e["series_key"])
    print(f"  非漫画drop(外国版/壊れ): {len(non_manga_keys):,} series_key", file=sys.stderr)

    # ★画集 = 漫画と別カテゴリ・別ストリーム。 manga.v2 から除外し art-books.v2 へ別出力。
    art_books = load_art_books()
    art_book_keys = set(art_books.keys())
    print(f"  画集(別ストリーム): {len(art_book_keys):,} series_key / 混在ISBN除外 {len(get_art_book_exclude_isbn())} 件", file=sys.stderr)

    # ★成年ネット(defense-in-depth、 2026-06-13)。 成年判定は slug-apply-prep の
    #   ゲートが第一線だが、 promote は data/manga を信頼して emit するだけで独立チェックが
    #   無かった = 5月の漏れ(2,233頁)の構造的根因。 data/manga がゲート未通過で再生成
    #   されたり promote 単体実行でも漏れないよう、 ここでも adult_score>=3 を弾く
    #   (override force非adult は除外)。 現データはクリーンなので実質no-op = 安全網。
    _adult_net_ovr = _load_adult_overrides()
    _adult_net_force = _load_adult_force()

    stats = {"total": 0, "regenerated": 0, "not_found_in_db": 0,
             "no_editions": 0, "dropped_spinoff_old": 0,
             "dropped_non_manga": 0, "dropped_art_book": 0}
    written_slugs: set = set()  # 今回のrunで種2側から実際に書いた頁(preorder自己retire判定用)
    not_found = []
    dropped = []
    dropped_non_manga = []

    # ★源頁は2箇所: data/manga(gitignore=このPC限り) + data/seeds/source-pages(★git追跡=恒久)。
    #   2026-07-25: 取りこぼし頁化で作った源頁が data/manga だと git clean/別PCで消える
    #   ([[orphan_series_promote_is_srcpage_driven]])。 新規生成分は必ず後者に置く。
    _src_files = sorted(SRC_DIR.glob("*.yml"))
    _extra_src = ROOT / "data" / "seeds" / "source-pages"
    if _extra_src.is_dir():
        _seen_stems = {p.stem for p in _src_files}
        _src_files += [p for p in sorted(_extra_src.glob("*.yml")) if p.stem not in _seen_stems]
    for ypath in _src_files:
        if ONLY_SLUGS and ypath.stem not in ONLY_SLUGS:
            continue
        stats["total"] += 1
        with ypath.open("r", encoding="utf-8") as f:
            src = _yload(f)
        slug = src["slug"]
        if not slug or not str(slug).strip():
            stats["empty_slug"] = stats.get("empty_slug", 0) + 1
            continue                       # 空slug = 出力ファイル名不正(.yml) → skip
        if slug in _PAGE_DEDUP_DROPS:
            stats["dedup_skip"] = stats.get("dedup_skip", 0) + 1
            continue                       # 重複ページ(page-dedup.yml) = canonical 側だけ出力
        if slug in _COMPANY_DROPS:
            stats["dropped_non_manga"] += 1
            dropped_non_manga.append(f"{ypath.name}  会社著者の非漫画(編集部編纂)")
            continue                       # 会社/編集部著者の編集部編纂物(アンソロ/ガイド) = 非漫画
        title = src["title"]
        qid = src.get("wikidata_qid")
        # 漫画以外 (= テレビアニメ版 / 映画 / 劇場版 等) は MANGAL 対象外
        if any(title.startswith(pat) for pat in DROP_TITLE_PREFIX_PATTERNS):
            stats["dropped_non_manga"] += 1
            dropped_non_manga.append(f"{ypath.name}  title={title}")
            continue
        # 関連書 (= ガイドブック / 設定資料集 / アンソロジー / 攻略本 等) は対象外
        if any(pat in title for pat in DROP_TITLE_CONTAINS_PATTERNS):
            stats["dropped_non_manga"] += 1
            dropped_non_manga.append(f"{ypath.name}  title={title}  (= 関連書)")
            continue
        series = find_series(con, slug, title, qid, _skey_override(slug, src.get("_skey")))
        if not series:
            stats["not_found_in_db"] += 1
            not_found.append(f"{ypath.name}  title={title}")
            continue
        # ★成年ネット(defense-in-depth): 成年(adult_score>=3)は本番に出さない。
        #   slug-apply-prep ゲートの第二線(data/manga 汚染・promote単体実行でも漏らさない)。
        if ((series.get("adult_score") or 0) >= 3 and series.get("series_key") not in _adult_net_ovr) \
                or series.get("series_key") in _adult_net_force:
            stats["dropped_adult"] = stats.get("dropped_adult", 0) + 1
            continue
        # 雑誌(cm105マスター準拠)は作品でないため除外
        if series.get("series_key") in mag_drop_keys:
            stats["dropped_non_manga"] += 1
            dropped_non_manga.append(f"{ypath.name}  title={title}  (= 雑誌cm105)")
            continue
        # 非漫画(外国語版/壊れ書誌)を series_key で除外
        if series.get("series_key") in non_manga_keys:
            stats["dropped_non_manga"] += 1
            dropped_non_manga.append(f"{ypath.name}  title={title}  (= 非漫画/外国版)")
            continue
        # ★画集 = 漫画と別カテゴリ。 manga.v2 には絶対出さない (= 別ストリーム art-books.v2 へ)。
        if series.get("series_key") in art_book_keys:
            stats["dropped_art_book"] += 1
            dropped_non_manga.append(f"{ypath.name}  title={title}  (= 画集→art-books.v2)")
            continue
        # 種2 subtitle に隠れた 抜粋本 (= title が本編名 + sub=「○○傑作集」 等) を drop
        sub = series.get("subtitle") or ""
        if any(pat in sub for pat in DROP_SUBTITLE_PATTERNS):
            stats["dropped_non_manga"] += 1
            dropped_non_manga.append(f"{ypath.name}  title={title}  sub={sub}  (= 抜粋本 sub)")
            continue
        # step A: spinoff 判定 (= 親があれば 子 = spinoff)
        is_spinoff = series["id"] in parent_map
        # ★series-keep: spinoff誤判定で消える独立作(カムイ伝第二部等)をslugで救済(=独立ページ化)
        if is_spinoff and slug in _SPINOFF_KEEP:
            is_spinoff = False
        # ★2026-07-26 ユーザ裁定「未発見の2015年以前は排除は条件としておかしい」:
        #   掲載方針は【版違い=統合 / 続編など独立作品=ページ作成 / コンビニ本=排除】であって、
        #   **発売年で独立作品を落とすのは筋が通らない**。 旧 CUTOFF_YEAR(2015) 判定を撤廃。
        #   実害: ドラゴンボールZ 39巻 / ドカベン スーパースターズ編 53巻 /
        #   シュート!新たなる伝説 35巻 等 **1,499 series** が非掲載だった。
        #   ★親子(parent_map)判定そのものは残す = 将来 巻数比などで真の派生本を弾く土台。
        #   コンビニ本/抜粋本の排除は imprint・題patternが別途担っているのでここでは不要。
        if False:  # 旧: is_spinoff and max_year < CUTOFF_YEAR で drop していた
            pass
        # 同一作品 cluster 分裂 を 検出 (= main + 同qid + 同title orphan)、 全部 merge
        # yml の title_kana を fallback (= db series row の kana が NULL の cases、
        # e.g. id=128570 'ハンター×ハンター' kana=NULL では kana match 効かない)
        merged_series = dict(series)
        if not merged_series.get("title_kana") and src.get("title_kana"):
            merged_series["title_kana"] = src["title_kana"]
        related_ids = find_related_series_ids(con, merged_series)
        editions = get_editions_with_volumes(con, related_ids)
        if not editions:
            # ★edition-override が editions を持つ頁は skip しない(2026-07-10 忍空2nd stage:
            #   種2実体がリミックス(ムック=filter落ち)のみでも override の確定版で頁を建てる。
            #   override は build_yml 終盤で editions を全置換するので空のまま进めてよい)
            if not (_load_edition_overrides().get(_slug_override(src.get("slug", ""))) or {}).get("editions"):
                stats["no_editions"] += 1
                continue
        # ★cluster-best: merge cluster の title/subtitle variant から最良を merged_series へ
        #   反映(中黒是正 + 代表脱落副題の回収)。 seed3 override は build_yml で優先。
        _apply_cluster_best(con, merged_series, related_ids)
        authors = get_authors(con, series["id"])
        authors = apply_author_corrections(authors, series["series_key"])
        # ★表示名は「その本のクレジット」(ユーザ方針 2026-07-26)。 典拠解決の代表名で上書きしない。
        authors = _apply_book_credit(
            authors, [v.get("isbn13") for ed in editions for v in (ed.get("volumes") or []) if v.get("isbn13")],
            _mangaka_alias(con))
        seed_entry = seed3.get(series["series_key"])
        new_yml = build_yml(src, merged_series, authors, editions, seed_entry,
                            valid_pubs, valid_mags, valid_gens)
        # ★新刊著者の統合修正: 再パース済authorsで上書き(連結→分割・役割分離)。 enrich_authorでヨミ/romaji再付与。
        if slug in author_reparse:
            arp = author_reparse[slug]
            if arp.get("authors"):  # 安全: 著者ゼロの seed は触らない
                new_yml["authors"] = [enrich_author(a) for a in arp["authors"]]
                new_yml["original_authors"] = [enrich_author(a) for a in (arp.get("original_authors") or [])]
                if arp.get("credits"):
                    new_yml["credits"] = arp["credits"]
                author_reparse_pages += 1
        # ★巻ISBN除去: 過剰統合で混入した別作の巻を slug 単位で除去(正しい別ページには残る)
        _vex = volume_exclude.get(slug)
        if _vex:
            for _ed in (new_yml.get("editions") or []):
                _ed["volumes"] = [v for v in (_ed.get("volumes") or []) if _norm_isbn(v.get("isbn13")) not in _vex]
                for _ver in (_ed.get("versions") or []):
                    _ver["volumes"] = [v for v in (_ver.get("volumes") or []) if _norm_isbn(v.get("isbn13")) not in _vex]
            new_yml["editions"] = [e for e in (new_yml.get("editions") or []) if (e.get("volumes") or e.get("versions"))]
            # ★除去で最終巻が消えたら出版年を残存巻から再計算(1(イチ)=アーク9混入除去後も年1993-2014に化けた 2026-07-08)
            _vy = [int(str(v["release_date"])[:4]) for e in new_yml["editions"]
                   for vs in [e.get("volumes") or []] + [vv.get("volumes") or [] for vv in (e.get("versions") or [])]
                   for v in vs if v.get("release_date") and str(v["release_date"])[:4].isdigit()]
            if _vy:
                new_yml["year_started"] = min(_vy)
                if new_yml.get("year_ended") is not None:
                    new_yml["year_ended"] = max(_vy)
            volume_exclude_pages += 1
        # ★版分離: canonical seed があれば standard/compact 版を権威データで再構築(版混在汚染の是正)
        if slug in edition_canonical:
            new_yml["editions"] = apply_edition_canonical(slug, new_yml.get("editions") or [], edition_canonical)
            edition_canonical_pages += 1
            # ★出版年を最終editionsから再導出(2026-07-13 関東平野型: canonicalで足した初刊1978が
            #   年計算(canonical適用より前)に反映されず1989のままだった)。導出規則は本計算と同じ:
            #   started=全巻min / ended=standard系の巻別初版dateの最大巻番号の年。
            #   status-corrections頁(Wiki検証済み完結年)とongoingのendedは触らない。
            _eds = new_yml.get("editions") or []
            _all_y = [int(str(v["release_date"])[:4]) for e in _eds
                      for vs in [e.get("volumes") or []] + [vv.get("volumes") or [] for vv in (e.get("versions") or [])]
                      for v in vs if v.get("release_date") and str(v["release_date"])[:4].isdigit()]
            if _all_y:
                new_yml["year_started"] = min(_all_y)
            if new_yml.get("year_ended") is not None and slug not in _STATUS_CORR:
                _stds = [e for e in _eds if e.get("type") == "standard"] or _eds
                _pvm: dict = {}
                for e in _stds:
                    for v in (e.get("volumes") or []):
                        n, d = v.get("number"), v.get("release_date")
                        if n and d and (n not in _pvm or str(d) < str(_pvm[n])):
                            _pvm[n] = str(d)
                if _pvm and _pvm[max(_pvm)][:4].isdigit():
                    new_yml["year_ended"] = int(_pvm[max(_pvm)][:4])
        # ★版付加(extra-editions.yml): 既存版はそのまま、指定版を末尾に追加(手塚全集タブ等 2026-07-21)
        if slug in extra_editions_map:
            new_yml["editions"], _xadded = apply_extra_editions(
                slug, new_yml.get("editions") or [], extra_editions_map)
            if _xadded:
                extra_editions_pages += 1
        # ★キャッチコピーを slug 経由で join(無ければ未設定=カードは出版社表示にfallback)
        if slug in catch_map and catch_map[slug]:
            new_yml["catch"] = catch_map[slug]
            catch_pages += 1
        if not new_yml.get("synopsis") and slug in synslug_map and synslug_map[slug]:
            new_yml["synopsis"] = synslug_map[slug]
            synslug_pages += 1
        # (ジャンルは下の trusted優先マージで確定 = AniList+Wiki+手動を採用、 AIはfallback)
        # ★adult_us(米基準): ページの series_key(merge込)が種a isAdult なら付与。
        #   非日本geoで非表示用(日本は表示)。 採用作品集合は不変=表示制御のみ追加。
        page_keys = [sid2key.get(sid) for sid in related_ids]
        page_keyset = {k for k in page_keys if k}
        if adult_us_keys and (page_keyset & adult_us_keys):
            new_yml["adult_us"] = True
            adult_us_pages += 1
        # ★AniList enrich(productionization): main series_key 優先で anilist_id/synonyms/
        #   genres_anilist/tags を本番に付与(箱を埋める)。 種3不変・match-v14 由来。
        en = None
        if enrich_map:
            en = enrich_map.get(series["series_key"])
            if not en:  # main 未マッチなら merge 内の他 series_key から
                for k in page_keys:
                    if k and k in enrich_map:
                        en = enrich_map[k]; break
            if en:
                new_yml["anilist_id"] = en["anilist_id"]
                if en.get("synonyms"):
                    new_yml["synonyms"] = en["synonyms"]
                if en.get("genres_anilist"):
                    new_yml["genres_anilist"] = en["genres_anilist"]  # 表示/比較用(genres本体は下のtrusted優先)
                if en.get("tags"):
                    new_yml["tags"] = en["tags"]
                # ★人気/評価(discovery用・コミュニティ不要)
                if en.get("popularity"):
                    new_yml["popularity"] = en["popularity"]
                if en.get("score"):
                    new_yml["score"] = en["score"]
                enrich_pages += 1
                # ★種a和訳 synopsis を anilist_id 経由で join(無ければ空のまま)
                ja = synopsis_ja.get(str(en["anilist_id"]))
                if ja:
                    new_yml["synopsis"] = ja
                    synopsis_pages += 1
                # ★作品Wikidata QID を anilist_id 経由で付与(著者QIDとは別フィールド)
                wq = work_qid.get(str(en["anilist_id"]))
                if wq and wq.get("qid"):
                    new_yml["work_wikidata_qid"] = wq["qid"]
                    work_qid_pages += 1
                # ★著者ゼロ((unknown))ページのみ AniList staff から著者補完。
                #   原作(Original Story)→original_authors、 作画(Story&Art/Art/Story)→authors で厳密分離。
                #   既存の正しい著者は上書きしない(unknown の時だけ)。
                cur_au = new_yml.get("authors") or []
                is_unknown = (not cur_au) or (len(cur_au) == 1 and cur_au[0].get("name") == "(unknown)")
                af = author_fill.get(str(en["anilist_id"]))
                if is_unknown and af and af.get("authors"):
                    new_yml["authors"] = [enrich_author(dict(a)) for a in af["authors"]]
                    if af.get("original_authors") and not new_yml.get("original_authors"):
                        new_yml["original_authors"] = [{"name": n, "role": "writer"} for n in af["original_authors"]]
                    author_fill_pages += 1
        # ★ジャンル trusted優先マージ(2026-06-13、 [[genre_quality_improvement]]):
        #   trusted = AniList(genres+themes=genres_trusted) ∪ Wiki/手動(genre-additions+genre-wiki)。
        #   trusted有→それを採用(AIノイズ=drama乱発を落とす)。 trusted空→AI fallback+provisional印。
        trusted = set(en["genres_trusted"]) if (en and en.get("genres_trusted")) else set()
        for k in [series["series_key"], *page_keys]:
            if not k:
                continue
            e2 = enrich_map.get(k) if enrich_map else None
            if e2 and e2.get("genres_trusted"):
                trusted |= set(e2["genres_trusted"])
            trusted |= set(_GENRE_ADDITIONS.get(k, []))
        trusted = {g for g in trusted if g in valid_gens}
        if trusted & {"baseball", "soccer"}:
            trusted.add("sports")  # 階層検索: 野球/サッカーは sports 併記(CLAUDE.md)
        if trusted:
            new_yml["genres"] = sorted(trusted)
            new_yml.pop("genres_provisional", None)
        else:
            # ★楽天あらすじ由来ジャンル(Phase③) = trusted空(=provisional/未ラベル)のみ採用。
            #   較正済の高精度ラベル。 trusted があれば上で確定済なので ここには来ない=trusted不変。
            rk = [g for g in _RAKUTEN_GENRES.get(slug, []) if g in valid_gens]
            if rk:
                rks = set(rk)
                if rks & {"baseball", "soccer"}:
                    rks.add("sports")
                new_yml["genres"] = sorted(rks)
                new_yml["genres_rakuten"] = True
                new_yml.pop("genres_provisional", None)
            else:
                # ★enrich作り直し(vol1 caption基点・closed vocab・較正済)= 旧AIより高品質 → trusted/rakuten無時に優先
                ge = [g for g in _GENRE_ENRICH.get(slug, []) if g in valid_gens and g != "other"]
                if ge:
                    geset = set(ge)
                    if geset & {"baseball", "soccer"}:
                        geset.add("sports")
                    new_yml["genres"] = sorted(geset)
                    new_yml["genres_provisional"] = True
                else:
                    ai_g = [g for g in (new_yml.get("genres") or []) if g in valid_gens and g != "other"]
                    # ★信頼源ゼロは空のまま出荷(2026-07-13裁定=otherを出さない。旧['other']fallbackは
                    #   索引ガードのmaster外拒否でページごと一覧から消える実害=2026-07-18に84頁で発覚)
                    new_yml["genres"] = ai_g
                    new_yml["genres_provisional"] = True  # 信頼源ゼロ=AI暫定(信頼源が来たら上書き)
        # ★楽天あらすじ由来 要素タグ(Phase③) = theme tag未保有 work へ追加(category=Rakuten)。
        #   既存 tag 名は dedup。 表示は要素欄(tag-i18n 和訳)。
        rkt = _RAKUTEN_TAGS.get(slug)
        if rkt:
            existing = {t.get("name") for t in (new_yml.get("tags") or [])}
            add = [{"name": n, "category": "Rakuten", "rank": 60}
                   for n in rkt if n not in existing]
            if add:
                new_yml["tags"] = (new_yml.get("tags") or []) + add
        # ★enrich作り直しの要素タグ(異世界転生/悪役令嬢/復讐/グルメ等)= 未保有 work へ追加
        ent = _TAGS_ENRICH.get(slug)
        if ent:
            existing2 = {t.get("name") for t in (new_yml.get("tags") or [])}
            add2 = [{"name": n, "category": "AI", "rank": 55}
                    for n in ent if n and n not in existing2]
            if add2:
                new_yml["tags"] = (new_yml.get("tags") or []) + add2
        # ★MADB安全fallback: AniListで埋まらなかった著者ゼロを series_key で補完
        #   (外国名除去後の単独日本語著者のみ=原作者誤主著/汚染を回避)。
        cur_au2 = new_yml.get("authors") or []
        if (not cur_au2) or (len(cur_au2) == 1 and cur_au2[0].get("name") == "(unknown)"):
            for k in [series["series_key"], *(page_keys or [])]:
                if k and k in author_fill_madb:
                    e2 = author_fill_madb[k]
                    new_yml["authors"] = [enrich_author(dict(a)) for a in e2["authors"]]
                    if e2.get("original_authors") and not new_yml.get("original_authors"):
                        new_yml["original_authors"] = [{"name": n, "role": "writer"} for n in e2["original_authors"]]
                    author_fill_madb_pages += 1
                    break
        # ★新刊: anilist synopsis 無 かつ slug-key distill synopsis 有 → 補完(既存上書きしない)
        if not new_yml.get("synopsis") and slug in synopsis_slug:
            new_yml["synopsis"] = synopsis_slug[slug]
            synopsis_pages += 1
        # ★著者ヨミ最終pass(2026-07-04 join漏れ659名/974頁の根治): どの経路で入った著者でも
        #   kana欠け×seed有りなら充填(冪等)。個別経路のenrich漏れを構造的にカバー
        for _ak in ("authors", "original_authors"):
            for _a in (new_yml.get(_ak) or []):
                if not _a.get("kana"):
                    enrich_author(_a)
        # ★特装版是正 最終pass(standardのみ): special ISBN→通常版差替+variants併存(書影無し補正はskip=空タイル回避)
        _sfm = _special_fix_map()
        for _ce in (new_yml.get("editions") or []):
            if _ce.get("type") != "standard":
                continue
            for _v in (_ce.get("volumes") or []):
                _c = _sfm.get(str(_v.get("isbn13") or ""))
                if not _c or not _c.get("normal_cover"):
                    continue
                _v["isbn13"] = _c["normal_isbn"]
                _v["cover_url"] = _c["normal_cover"]
                if _c.get("normal_date"):
                    _v["release_date"] = _c["normal_date"]
                _var = _c.get("variant") or {}
                _v["variants"] = [{k: _var.get(k) for k in ("label", "isbn13", "cover_url", "price")}]
        # ★通常版が既に主枠の巻にも特装variantを添付(2026-07-03拡張: 落語心中/ろこどる型)
        _sbn = _special_by_normal()
        for _ce in (new_yml.get("editions") or []):
            if _ce.get("type") != "standard":
                continue
            for _v in (_ce.get("volumes") or []):
                if _v.get("variants"):
                    continue
                _c = _sbn.get(str(_v.get("isbn13") or ""))
                if _c and _c.get("variant"):
                    _var = _c["variant"]
                    _v["variants"] = [{k: _var.get(k) for k in ("label", "isbn13", "cover_url", "price")}]
        # ★volume-exclude 再適用(2026-07-26): 上の特装版是正は special_isbn を normal_isbn に**置換**するため、
        #   先に除外したISBNが**ここで復活し得る**(僕のヒーローアカデミア14で実害: 除外しても消えなかった)。
        #   除外は「この頁に出すな」の最終意思なので、置換系passの後でもう一度効かせる。
        if _vex:
            for _ce in (new_yml.get("editions") or []):
                _ce["volumes"] = [v for v in (_ce.get("volumes") or [])
                                  if _norm_isbn(v.get("isbn13")) not in _vex]
                for _ver in (_ce.get("versions") or []):
                    _ver["volumes"] = [v for v in (_ver.get("volumes") or [])
                                       if _norm_isbn(v.get("isbn13")) not in _vex]
            new_yml["editions"] = [e for e in (new_yml.get("editions") or [])
                                   if (e.get("volumes") or e.get("versions"))]
        # ★書影 最終充填 (= 全edition操作後=edition-canonical/override/exclude/version の後。
        #   clean_vol充填が canonical再構築で消える件を確実に埋める。 旧 _apply-covers-stage 廃止)。
        # ★発売日 精密化も同じ最終passで(2026-07-18): 現在値が空 or 新値のprefix(年月→年月日)の時だけ。
        for _ce in (new_yml.get("editions") or []):
            for _vs in [_ce.get("volumes") or []] + [_vv.get("volumes") or [] for _vv in (_ce.get("versions") or [])]:
                for _v in _vs:
                    if not _v.get("cover_url"):
                        _cu = _cover_for(_v.get("isbn13"))
                        if _cu:
                            _v["cover_url"] = _cu
                    # ★巻説明も同じ最終passで充填(canonical再構築でclean_vol充填が消えるため。書影と同型)
                    if not _v.get("description"):
                        _dd = _desc_for(_v.get("isbn13"))
                        if _dd:
                            _v["description"] = _dd
                    _nd = _date_fill_for(_v.get("isbn13"))
                    if _nd:
                        _cur = str(_v.get("release_date") or "")
                        if not _cur or (_nd.startswith(_cur) and len(_nd) > len(_cur)):
                            _v["release_date"] = _nd
                            stats["date_filled"] = stats.get("date_filled", 0) + 1
                        elif _cur != _nd:
                            stats["date_conflict_skip"] = stats.get("date_conflict_skip", 0) + 1
        out_path = OUT_DIR / f"{slug}.yml"
        with out_path.open("w", encoding="utf-8") as f:
            f.write("# Regenerated by scripts/_promote-bulk-v2.py (= path B' step G)\n")
            yaml.dump(new_yml, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        stats["regenerated"] += 1
        written_slugs.add(str(slug))

    # ===== 画集 = 別ストリーム (art-books.v2)。 ★manga.v2 とは別出力 = 構造的に混ざらない =====
    art_stats = {"written": 0, "adult_held": 0, "no_editions": 0, "not_in_db": 0, "dup_group": 0}
    if not ONLY_SLUGS:
        ART_OUT_DIR = ROOT / "data" / ("art-books.dryrun" if "--dry-run" in sys.argv else "art-books.v2")
        ART_OUT_DIR.mkdir(parents=True, exist_ok=True)
        for p in ART_OUT_DIR.glob("*.yml"):
            p.unlink()
        for p in ART_OUT_DIR.glob("*.yml.adult"):
            p.unlink()
        key2sid = {v: k for k, v in sid2key.items()}
        merge_groups = get_merge_sids(con)
        seen_groups: set[frozenset] = set()
        for sk, meta in sorted(art_books.items()):
            sid = key2sid.get(sk)
            if sid is None:
                art_stats["not_in_db"] += 1
                continue
            group = merge_groups.get(sid, [sid])
            gkey = frozenset(group)
            if gkey in seen_groups:
                art_stats["dup_group"] += 1
                continue
            seen_groups.add(gkey)
            ab = build_artbook(con, sk, meta, sid, group, seed3)
            if ab is None:
                art_stats["no_editions"] += 1
                continue
            # ★成人画集: データは保持しつつ本番カタログには出さない (= .adult 退避、 loader 非読込)。
            if ab["adult"]:
                art_stats["adult_held"] += 1
                ap = ART_OUT_DIR / f"{ab['slug']}.yml.adult"
            else:
                art_stats["written"] += 1
                ap = ART_OUT_DIR / f"{ab['slug']}.yml"
            with ap.open("w", encoding="utf-8") as f:
                f.write("# Regenerated by scripts/_promote-bulk-v2.py (= art book stream)\n")
                yaml.dump(ab, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        print(f"\n=== art-books (別ストリーム) ===", file=sys.stderr)
        for k, v in art_stats.items():
            print(f"  {k}: {v}", file=sys.stderr)
        print(f"  → {ART_OUT_DIR}", file=sys.stderr)

        # ★「漫画一覧に画集が1件も無い」機械検査 (= 混ざらない保証の最終確認、 設計 §5-3)
        excl_isbn = get_art_book_exclude_isbn()
        leaks = []
        for p in OUT_DIR.glob("*.yml"):
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            for ed in d.get("editions", []) or []:
                for v in ed.get("volumes", []) or []:
                    if _norm_isbn(v.get("isbn13")) in excl_isbn:
                        leaks.append(f"{p.name}: {v.get('isbn13')}")
        if leaks:
            print(f"  ❌ 混在検査 FAIL: 漫画.v2 に画集ISBN {len(leaks)} 件残存", file=sys.stderr)
            for lk in leaks:
                print(f"     {lk}", file=sys.stderr)
        else:
            print(f"  ✅ 混在検査 PASS: 漫画.v2 に画集混在ISBN 0 件", file=sys.stderr)

    print(f"\n=== stats ===", file=sys.stderr)
    for k, v in stats.items():
        print(f"  {k}: {v}", file=sys.stderr)
    print(f"  adult_us(米基準=非日本geoで非表示): {adult_us_pages}", file=sys.stderr)
    print(f"  anilist enrich(id/synonyms/genres/tags 付与): {enrich_pages}", file=sys.stderr)
    print(f"  synopsis 種a和訳 付与: {synopsis_pages}(残りは空=種3 AI文不使用)", file=sys.stderr)
    print(f"  catch コピー付与: {catch_pages}", file=sys.stderr)
    print(f"  synopsis(slug seed)付与: {synslug_pages}", file=sys.stderr)
    print(f"  著者修正(新刊・連結是正): {author_reparse_pages}", file=sys.stderr)
    print(f"  巻ISBN除去(過剰統合是正): {volume_exclude_pages}", file=sys.stderr)
    print(f"  作品Wikidata QID 付与: {work_qid_pages}", file=sys.stderr)
    print(f"  著者ゼロ→AniList補完: {author_fill_pages}", file=sys.stderr)
    print(f"  著者ゼロ→MADB安全補完: {author_fill_madb_pages}", file=sys.stderr)
    if not_found:
        print(f"\n=== not found in db-v2 ===", file=sys.stderr)
        for n in not_found:
            print(f"  ❌ {n}", file=sys.stderr)
    if dropped:
        print(f"\n=== dropped (= spinoff & old) ===", file=sys.stderr)
        for d in dropped:
            print(f"  🗑️  {d}", file=sys.stderr)
    if dropped_non_manga:
        print(f"\n=== dropped (= non-manga: anime/movie/novel) ===", file=sys.stderr)
        for d in dropped_non_manga:
            print(f"  🚫 {d}", file=sys.stderr)

    # ★予約新規頁の恒久合流(2026-07-06 → 2026-07-25 seed適用機構): data/seeds/preorder-pages/*.yml
    #   (git追跡=消えない保管庫)を出力へ合流。種2側が今回のrunで実際に書いた頁は種2優先=自己retire。
    #   ★逐語コピーを廃止し、slugキーseed(catch/synopsis/書影)を通してから書く(2026-07-25:
    #     新292 seriesでpreorder頁にseedが一切届かない実害。--only指定時はpreorder頁も再生成される)。
    #   種2への正式INSERTは月次蒸留時に別途(それまでの恒久化がこのseed)。
    _pp_dir = ROOT / "data" / "seeds" / "preorder-pages"
    if _pp_dir.is_dir():
        _pp_n = _pp_skip = _pp_seeded = 0
        for _f in sorted(_pp_dir.glob("*.yml")):
            _dst = OUT_DIR / _f.name
            _stem = _f.stem
            if _stem in written_slugs:
                _pp_skip += 1          # 種2側が今回書いた=自己retire
                continue
            if ONLY_SLUGS and _stem not in ONLY_SLUGS:
                if not _dst.exists():  # targeted時の対象外は従来どおり温存(無ければ補充コピー)
                    _dst.write_bytes(_f.read_bytes())
                    _pp_n += 1
                continue
            if not ONLY_SLUGS and _dst.exists():
                _pp_skip += 1          # フル時に種2 srcが先に書いた頁(旧ロジック互換の保険)
                continue
            try:
                with _f.open("r", encoding="utf-8") as _fh:
                    _pd = _yload(_fh)
            except Exception:
                _dst.write_bytes(_f.read_bytes())  # 読めない時は従来コピー(安全側)
                _pp_n += 1
                continue
            _touched = False
            if not _pd.get("catch") and catch_map.get(_stem):
                _pd["catch"] = catch_map[_stem]
                _touched = True
            if not _pd.get("synopsis") and synslug_map.get(_stem):
                _pd["synopsis"] = synslug_map[_stem]
                _touched = True
            for _e in _pd.get("editions") or []:
                # ★edition.publisher が **内部キー**(kadokawa/kodansha…)のままだと表示に漏れる。
                #   予約頁は種2を通らないので edition_pub_name が効かず、実測1,248版が生キー表示だった
                #   (2026-07-26)。 巻ISBNの**出版者記号**から当時社名に解決する。
                _pb = str(_e.get("publisher") or "")
                if _pb and re.fullmatch(r"[a-z0-9-]+", _pb):
                    # ★ISBN記号 → 無ければ publishers.yml の表示名(キーの正式な表示形)
                    _nm = edition_pub_name(_e) or _pub_display_name(_pb)
                    if _nm:
                        _e["publisher"] = _nm
                        _touched = True
                for _pool in [_e.get("volumes") or []] + [vv.get("volumes") or [] for vv in (_e.get("versions") or [])]:
                    for _v in _pool:
                        if not _v.get("cover_url") and _v.get("isbn13"):
                            _cu = _cover_for(_v["isbn13"])
                            if _cu:
                                _v["cover_url"] = _cu
                                _touched = True
            with _dst.open("w", encoding="utf-8") as _fh:
                _fh.write("# Regenerated by scripts/_promote-bulk-v2.py (= preorder-pages合流+seed適用)\n")
                yaml.dump(_pd, _fh, allow_unicode=True, sort_keys=False, default_flow_style=False)
            _pp_n += 1
            if _touched:
                _pp_seeded += 1
        print(f"  preorder-pages合流: {_pp_n} (seed適用={_pp_seeded} / 種2側優先skip={_pp_skip})", file=sys.stderr)

    print(f"\nwrote {stats['regenerated']} yml to {OUT_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
