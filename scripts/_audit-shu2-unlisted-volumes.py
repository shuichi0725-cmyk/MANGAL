"""★頁は在るのに巻だけ本番に出ていない層(= トリニティセブン 15.5 型)を種2駆動で検出。

署名(2026-09-06 ユーザ発見の実例):
  トリニティセブン『七人の魔道士と日常風景 15.5』(9784040721446) は
  **種2に在り**、本編頁 trinity-7-shichinin-no-masho-tsukai も**在る**のに、
  種2側で別クラスタ(qid:Q11444957|name:トリニティセブン)に number=15 で入っていたため
  本編15巻と番号衝突し、どの頁にも出ていなかった。

既存監査の死角(だからこの検出器が要る):
  - 孤児series監査(_audit-orphan-new-series.py)= 「そのseriesの巻が **1本も** 出ていない」が条件。
    部分的に出ているクラスタの取りこぼし巻は対象外。 単巻クラスタの場合は出るが、
    単巻孤児44,000行の海に埋まって人が見つけられない。
  - Sugar&Spice型(_audit-subtitle-orphan-volume.py)= ★**楽天キャッシュの題**が
    「親題+巻番号」を名乗ることが条件。 楽天に無い本・題の形が違う本は拾えない。
  - 巻抜け仮想 = 番号の**穴**を見るので、15と16が連続している所に挟まる 15.5 は穴にならない。
  → 本検出器は **楽天非依存・種2駆動**で「本番に出ていないISBN」を全部見て、
    その作品の頁が既に在るものだけを残す。

判定:
  1. 種2の巻ISBNのうち **本番(data/manga.v2)に1つも現れないもの**を集める
  2. promote が正当に落とす分を除外(成年/非漫画/画集/雑誌/imprint/版種/題patterns)
     = 除外条件は **promote本体を import** して二重管理を避ける
  3. volume-exclude.yml で **意図的に頁から外したISBN**を除外(再提案しない)
  4. その巻の「持ち主の頁」を機械照合し、見つかったものだけ残す(下の match 列)
       SIBLING  = 同じseriesの別の巻が本番に出ている(= 最強。 部分掲載の取りこぼし)
       TITLE    = 正規化題が本番頁と一致(ルビ括弧除去つき) × 著者が重なる
       SLUG     = ラテン題が本番slugと一致 × 著者が重なる
       NEAR     = 題の包含(片方が他方の接頭辞) × 著者が重なる ← 弱い。 外伝/続編の誤当ても混ざる
  ★著者ゲート= 同名別作品(952件が正当に併存)へ巻を吸わせないため。 どちらかの著者が空なら通す。

★さらに「番号状態」で4つに割る(= 芯を人が裁ける大きさにするため。 初回実測):
  MISSING  その巻番号が持ち主の頁に**無い** = 本当に欠けている巻   ← ★芯。 104巻/69頁
  DUP      同番号が別ISBNで既に頁に在る                          17,350巻。 特装版/重版/別クラスタの同巻。
           ★トリニティセブン15.5 もここに居た(種2が number=15 で持っていたため)。
           日付が頁の同番号巻と大きく違う行が怪しい(列 date_gap_days)。
  VOL0     number=0 の番外/無番号巻   1,930巻 → `_audit-vol0-hidden-first.py` と `vol0-show.yml` の領域
  YEARNUM  番号に西暦が化けている       18巻 → MADB誤番号の領域

★第2の鉱脈 = 「x.5 の番外巻」直撃パス:
  種2駆動では トリニティ15.5 は DUP に落ちて 17,847巻の海に埋まる(種2が number=15 で持つため)。
  番外巻は **題に「x.5」と書いてある**のが決定的なので、 ISBN題マップ(.cache/isbn-title-map.json)を
  1パス掃いて 「x.5 を名乗るのに本番に無い本」 を直接出す。 ガイドブック/ファンブック/公式ガイド/
  設定資料/特装版・同梱/「2.5次元」(題の一部で誤検出) は除外し、 親題から持ち主の頁を機械照合する。
  実測: 題に x.5 を持つ本 166 → 本番に無い 90 → 除外後 44 → 親頁が特定できた 34。

出力(read-only。 本番/種2 不変):
  docs/production-diagnostics/shu2-unlisted-volumes.tsv       全件
  docs/production-diagnostics/shu2-unlisted-volumes-core.tsv  ★芯 = MISSING × 強照合
  docs/production-diagnostics/half-volume-candidates.tsv      ★x.5 の番外巻(第2の鉱脈)
usage: python scripts/_audit-shu2-unlisted-volumes.py [--since YYYY-MM] [--rebuild]
  --since   = その発売日以降の巻だけ見る
  --rebuild = 本番掲載ISBN索引を強制再構築(★索引が古いと解決済みの巻が復活する。
              付け忘れても本番ymlの方が新しければ自動で作り直す)
"""
import datetime
import glob
import importlib.util
import json
import os
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
IDX = ROOT / ".cache" / "live-isbn-index.json"
PAGEVOLS = ROOT / ".cache" / "live-page-vols.json"   # 公開slug -> {nums:[…], dates:{num:date}}
LIST_IDX = ROOT / "data" / "manga-list-index.json"
HARVEST = ROOT / ".cache" / "torikoboshi" / "harvest.jsonl"
OUT = ROOT / "docs" / "production-diagnostics" / "shu2-unlisted-volumes.tsv"
OUT_CORE = ROOT / "docs" / "production-diagnostics" / "shu2-unlisted-volumes-core.tsv"
OUT_X5 = ROOT / "docs" / "production-diagnostics" / "half-volume-candidates.tsv"
TITLE_MAP = ROOT / ".cache" / "isbn-title-map.json"
# 題に「x.5」を名乗る本(= 番外巻)。 「2.5次元」は題の一部なので別で弾く。
_X5 = re.compile(r"(?<![0-9])([0-9]{1,3})[.．]5(?![0-9])")
# ★掲載対象外(CLAUDE.md の関連書patternと同趣旨)。 x.5 の本は資料本の比率が高いので厚めに弾く。
_X5_NG = re.compile(
    r"(ガイドブック|ファンブック|ふぁんぶっく|公式ガイド|コミックガイド|official ?guide|official ?fanbook|キャラクターブック|設定資料|図鑑|攻略|特装版|限定版|小冊子|同梱|DESIGN FIGURE|Ver．|Ver\\.)", re.I)
_X5_NG2 = re.compile(r"2[.．]5次元")
ISBN_RE = re.compile(r"97[89]\d{10}")

# ★突合用の題正規化(表示に使わない)。 規則は _audit-orphan-new-series.py と同一に保つこと。
_NORM_RUBY = re.compile(r"[（(][ぁ-んァ-ヶーゝゞ・･]+[)）]")
_NORM_DROP_WORDS = re.compile(r"(新装版|完全版|愛蔵版|文庫版|決定版|新版|コミック版|オールカラー版)")
_NORM_SYMBOLS = re.compile("[" + re.escape(
    " 　・･:：;；,，.。!！?？'\"“”‘’-–—ー~〜/／\\|(){}[]【】〈〉《》「」『』*＊+＋#＃&＆@☆★♥♡=×") + "]")


def _pre(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    return _NORM_DROP_WORDS.sub("", _NORM_RUBY.sub("", s))


def norm(s):
    return _NORM_SYMBOLS.sub("", _pre(s))


def latin_key(s):
    """題がほぼ全部ラテン文字の時だけ、 slug と直接突き合わせるキーを返す。"""
    t = _pre(s)
    k = re.sub(r"[^a-z0-9]", "", t)
    body = re.sub(r"[^0-9a-z぀-ヿ一-鿿]", "", t)
    return k if body and len(k) >= 3 and len(k) / len(body) >= 0.9 else ""


def _promote():
    """promote 本体を import(= drop条件の単一ソース。 main は走らない)。"""
    spec = importlib.util.spec_from_file_location("promote_v2", ROOT / "scripts" / "_promote-bulk-v2.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def newest_src_mtime():
    newest, n = 0.0, 0
    with os.scandir(ROOT / "data" / "manga.v2") as it:
        for e in it:
            if e.name.endswith(".yml"):
                m = e.stat().st_mtime
                n += 1
                if m > newest:
                    newest = m
    return newest, n


_VOL_LINE = re.compile(r"^\s*-?\s*number:\s*([0-9]+(?:\.[0-9]+)?)\s*$", re.M)
_SLUG_LINE = re.compile(r"^slug:\s*(.+)$", re.M)
# 巻ブロック = "number:" と、その後に続く "isbn13:" / "release_date:" を素朴に対応付ける
_VOL_BLOCK = re.compile(
    r"number:\s*(?P<n>[0-9]+(?:\.[0-9]+)?)(?P<body>(?:(?!number:).)*?)(?=number:|\Z)", re.S)
_ISBN_IN = re.compile(r"isbn13:\s*'?(97[89][0-9]{10})'?")
_DATE_IN = re.compile(r"release_date:\s*'?([0-9]{4}(?:-[0-9]{2}){0,2})'?")


def build_index():
    """本番 data/manga.v2 を1パスし、 掲載ISBN集合 と 頁ごとの巻情報 を同時に作る。

    ★頁の巻情報(公開slug / 巻番号集合 / 番号→発売日) は「番号状態」の判定に要る。
      ISBN索引と別パスにすると 66k走査が2回になるので **同じパスで集める**。
    """
    seen = set()
    pages = {}
    n = 0
    for p in glob.glob(str(ROOT / "data" / "manga.v2" / "*.yml")):
        n += 1
        if n % 20000 == 0:
            print(f"    ...{n:,}頁", flush=True)
        try:
            raw = open(p, encoding="utf-8").read()
        except Exception:
            continue
        seen.update(ISBN_RE.findall(raw))
        m = _SLUG_LINE.search(raw)
        slug = m.group(1).strip().strip("'\"") if m else os.path.basename(p)[:-4]
        nums, ndate = {}, {}
        for b in _VOL_BLOCK.finditer(raw):
            num = float(b.group("n"))
            body = b.group("body")
            d = _DATE_IN.search(body)
            nums[num] = nums.get(num, 0) + 1
            if d and num not in ndate:
                ndate[num] = d.group(1)
        pages[slug] = {"nums": sorted(nums), "dates": ndate}
    print(f"  本番 {n:,}頁 / 掲載ISBN {len(seen):,} / 巻情報 {len(pages):,}頁", flush=True)
    IDX.write_text(json.dumps(sorted(seen)), encoding="utf-8")
    PAGEVOLS.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    return seen


def load_material():
    """楽天ハーベストの材料有無(紹介文/書影)。 無ければ空。"""
    if not HARVEST.exists():
        return {}
    m = {}
    with HARVEST.open(encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            it = d.get("item") or {}
            u = it.get("largeImageUrl") or it.get("mediumImageUrl") or ""
            m[str(d.get("isbn"))] = (bool((it.get("itemCaption") or "").strip()),
                                     bool(u and "noimage" not in u))
    return m


def _imprint_dropped(P, imp):
    imp = imp or ""
    imp_l = imp.lower()
    if any(p in imp for p in P.DROP_IMPRINT_PATTERNS):
        return True
    if any(p in imp_l for p in P.DROP_IMPRINT_LOWER_PATTERNS):
        return True
    if "=" not in imp and any(p in imp_l for p in P.DROP_IMPRINT_LOWER_PATTERNS_NO_EQ):
        return True
    return False


def main():
    since = None
    if "--since" in sys.argv:
        since = sys.argv[sys.argv.index("--since") + 1]

    # ---- 本番掲載ISBN索引(★陳腐化を自動検知。 古いと解決済みの巻が復活する)
    stale = False
    if IDX.exists():
        newest, npages = newest_src_mtime()
        if newest > IDX.stat().st_mtime:
            stale = True
            print(f"[1/4] ★索引が古い(本番ymlの方が新しい / {npages:,}頁) → 自動で作り直す", flush=True)
    if "--rebuild" in sys.argv or not IDX.exists() or stale or not PAGEVOLS.exists():
        print("[1/4] 本番掲載ISBN索引 + 頁の巻情報を構築 ...", flush=True)
        live = build_index()
    else:
        live = set(json.loads(IDX.read_text(encoding="utf-8")))
        print(f"[1/4] 本番掲載ISBN索引(既存・鮮度OK) {len(live):,}", flush=True)
    pagevols = json.loads(PAGEVOLS.read_text(encoding="utf-8")) if PAGEVOLS.exists() else {}

    print("[2/4] promote の drop条件 + 本番索引を読み込み ...", flush=True)
    P = _promote()
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    non_manga = {e["series_key"] for e in
                 (P.yaml.safe_load((ROOT / "data/seeds/non-manga-drop.yml").read_text(encoding="utf-8")) or {})
                 .get("non_manga", []) if isinstance(e, dict) and e.get("series_key")}
    art_books = set(P.load_art_books().keys())
    drop_keys = set(P._load_drop_series_keys() or set())
    # ★意図的に頁から外したISBN = 二度と提案しない
    excluded = set()
    _ve = ROOT / "data" / "seeds" / "volume-exclude.yml"
    if _ve.exists():
        for e in (P.yaml.safe_load(_ve.read_text(encoding="utf-8")) or {}).get("excludes", []) or []:
            if isinstance(e, dict) and e.get("isbn13"):
                excluded.add(str(e["isbn13"]))
    print(f"  volume-exclude {len(excluded):,} ISBN", flush=True)

    ix = json.loads(LIST_IDX.read_text(encoding="utf-8"))
    f = ix["f"]
    si, ti, ai = f.index("slug"), f.index("title"), f.index("authors")

    def aulist(v):
        out = []
        for a in (v or []):
            nm = a.split("\t")[0] if isinstance(a, str) else a.get("name", "")
            if nm:
                out.append(nm)
        return out

    live_titles, live_slugs, live_by_author, page_authors = {}, {}, {}, {}
    for r in ix["d"]:
        nt = norm(r[ti])
        if nt:
            live_titles.setdefault(nt, r[si])
        live_slugs.setdefault(re.sub(r"[^a-z0-9]", "", r[si].lower()), r[si])
        pa = {norm(x) for x in aulist(r[ai]) if norm(x)}
        page_authors[r[si]] = pa
        for a in pa:
            live_by_author.setdefault(a, []).append((nt, r[si]))
    print(f"  本番索引 {len(ix['d']):,}頁", flush=True)

    material = load_material()
    print(f"  楽天ハーベスト材料 {len(material):,} ISBN", flush=True)

    print("[3/4] 種2を走査 ...", flush=True)
    series = {r[0]: r for r in con.execute(
        "SELECT s.id, s.series_key, s.title, s.subtitle, s.adult_score FROM series s")}
    authors = defaultdict(list)
    for sid, nm in con.execute(
            "SELECT sa.series_id, m.name FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id"):
        authors[sid].append(nm)
    ed_of = {}
    for eid, sid, ip, ty in con.execute("SELECT id, series_id, imprint, type FROM editions"):
        ed_of[eid] = (sid, ip or "", ty or "")

    # ---- series 単位で「本番に出ている巻が1本でもあるか」= 部分掲載の判定
    live_slug_of_series = defaultdict(Counter)
    vols_by_series = defaultdict(list)
    for eid, ib, num, rd in con.execute(
            "SELECT edition_id, isbn13, number, release_date FROM volumes "
            "WHERE isbn13 IS NOT NULL AND isbn13!=''"):
        e = ed_of.get(eid)
        if not e:
            continue
        sid, imp, ty = e
        vols_by_series[sid].append((str(ib), num, rd or "", imp, ty))

    isbn_page = {}
    _ipi = ROOT / ".cache" / "isbn-page-index.json"
    if _ipi.exists():
        isbn_page = json.loads(_ipi.read_text(encoding="utf-8"))
    for sid, vv in vols_by_series.items():
        for ib, *_ in vv:
            hit = isbn_page.get(ib)
            if hit:
                for s in hit:
                    live_slug_of_series[sid][s] += 1

    reasons = Counter()
    rows = []
    for sid, vv in vols_by_series.items():
        s = series.get(sid)
        if not s:
            continue
        _, key, title, sub, adult = s
        title = title or ""
        missing = [v for v in vv if v[0] not in live and v[0] not in excluded]
        if not missing:
            continue
        # ---- promote が正当に落とす分(series単位の条件)
        why = None
        if (adult or 0) >= 3:
            why = "adult"
        elif key in non_manga:
            why = "non_manga_drop"
        elif key in art_books:
            why = "art_book"
        elif key in drop_keys:
            why = "drop_key"
        elif any(title.startswith(p) for p in P.DROP_TITLE_PREFIX_PATTERNS):
            why = "title_prefix"
        elif any(p in title for p in P.DROP_TITLE_CONTAINS_PATTERNS):
            why = "title_contains"
        elif any(p in (sub or "") for p in P.DROP_SUBTITLE_PATTERNS):
            why = "subtitle"
        if why:
            reasons[why] += len(missing)
            continue

        auths = authors.get(sid, [])
        na = {norm(a) for a in auths if norm(a)}
        nt = norm(title)
        lk = latin_key(title)

        # ---- 持ち主の頁を決める
        owner, match = "", ""
        sib = live_slug_of_series.get(sid)
        if sib:
            owner, match = sib.most_common(1)[0][0], "SIBLING"
        else:
            def gate(slug):
                pa = page_authors.get(slug) or set()
                return (not pa) or (not na) or bool(pa & na)
            if nt and nt in live_titles and gate(live_titles[nt]):
                owner, match = live_titles[nt], "TITLE"
            elif lk and lk in live_slugs and gate(live_slugs[lk]):
                owner, match = live_slugs[lk], "SLUG"
            else:
                for a in na:
                    for pt, ps in live_by_author.get(a, ()):
                        if pt and nt and min(len(pt), len(nt)) >= 3 and (pt.startswith(nt) or nt.startswith(pt)):
                            owner, match = ps, "NEAR"
                            break
                    if owner:
                        break
        if not owner:
            reasons["頁が見つからない(孤児側=別監査の領域)"] += len(missing)
            continue

        for ib, num, rd, imp, ty in missing:
            if since and (rd or "") < since:
                continue
            # ---- 版種は巻単位で見る(その版だけ対象外のことがある)
            if ty not in P.KEEP_EDITION_TYPES:
                reasons["edition_type"] += 1
                continue
            if _imprint_dropped(P, imp):
                reasons["imprint"] += 1
                continue
            m = material.get(ib)
            mat = ("未取得" if not m else
                   "紹介文+書影" if (m[0] and m[1]) else
                   "紹介文のみ" if m[0] else "書影のみ" if m[1] else "なし")
            # ---- 番号状態(★芯を人が裁ける大きさにする切り分け)
            pv = pagevols.get(owner) or {}
            pnums = set(pv.get("nums") or [])
            gap = ""
            if num is None:
                state = "NONUM"
            elif float(num) == 0:
                state = "VOL0"          # 番外/無番号 = _audit-vol0-hidden-first.py の領域
            elif float(num) >= 1900:
                state = "YEARNUM"       # 西暦が巻番号に化けた誤番号
            elif not pnums:
                state = "PAGE_UNREAD"   # 頁の巻情報が取れない(--rebuild で解消)
            elif float(num) in pnums:
                state = "DUP"           # 同番号が別ISBNで既に在る(特装版/重版/別クラスタの同巻)
                pd = (pv.get("dates") or {}).get(str(float(num))) or \
                     (pv.get("dates") or {}).get(str(int(num)) if float(num).is_integer() else "")
                if pd and rd:
                    try:
                        a = datetime.date(*(int(x) for x in (str(pd) + "-01-01").split("-")[:3]))
                        b = datetime.date(*(int(x) for x in (str(rd) + "-01-01").split("-")[:3]))
                        gap = str(abs((a - b).days))
                    except Exception:
                        gap = ""
            else:
                state = "MISSING"       # ★本当に欠けている巻
            rows.append((state, match, owner, key, title, sub or "", num if num is not None else "",
                         ib, rd, gap, imp, ty, " / ".join(auths[:3]), mat))

    # ---- ★第2の鉱脈: 題が「x.5」を名乗るのに本番に無い本(= 番外巻の直撃)
    x5 = []
    if TITLE_MAP.exists():
        tmap = json.loads(TITLE_MAP.read_text(encoding="utf-8"))
        for ib, t in tmap.items():
            if not isinstance(t, str) or not t or ib in live or ib in excluded:
                continue
            m = _X5.search(t)
            if not m or _X5_NG.search(t) or _X5_NG2.search(t):
                continue
            head = norm(t[:m.start()])
            owner = live_titles.get(head) or live_titles.get(head.rstrip("0123456789")) or ""
            if not owner and len(head) >= 3:
                for k, v in live_titles.items():
                    if (k.startswith(head) or head.startswith(k)) and abs(len(k) - len(head)) <= 6:
                        owner = v
                        break
            mm = material.get(ib)
            mat = ("未取得" if not mm else
                   "紹介文+書影" if (mm[0] and mm[1]) else
                   "紹介文のみ" if mm[0] else "書影のみ" if mm[1] else "なし")
            x5.append((owner, f"{m.group(1)}.5", ib, t.strip(), mat))
        x5.sort(key=lambda r: (not r[0], r[0]))
    with OUT_X5.open("w", encoding="utf-8", newline="") as fh:
        fh.write("owner_slug\thalf_number\tisbn\ttitle\t材料\n")
        for r in x5:
            fh.write("\t".join(str(x) for x in r) + "\n")

    print("[4/4] 出力 ...", flush=True)
    rows.sort(key=lambda r: (r[0], r[2], str(r[6])))
    HEAD = ("状態\tmatch\towner_slug\tseries_key\ttitle\tsubtitle\tnumber\tisbn\trelease_date"
            "\tdate_gap_days\timprint\tedition_type\tauthors\t材料\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        fh.write(HEAD)
        for r in rows:
            fh.write("\t".join(str(x) for x in r) + "\n")
    # ★芯 = 実巻番号が頁に無い(= 本当に欠けている) かつ 照合が強い(NEAR は外伝の誤当てが混ざる)
    core = [r for r in rows if r[0] == "MISSING" and r[1] in ("SIBLING", "TITLE", "SLUG")]
    with OUT_CORE.open("w", encoding="utf-8", newline="") as fh:
        fh.write(HEAD)
        for r in core:
            fh.write("\t".join(str(x) for x in r) + "\n")

    print("\n=== 頁は在るのに出ていない巻(種2駆動・楽天非依存) ===")
    print(f"  候補 {len(rows):,}巻 / {len({r[2] for r in rows}):,}頁")
    print("  番号状態:")
    _note = {"DUP": "同番号が別ISBNで既在(特装版/重版/別クラスタの同巻)。★トリニティ15.5型もここ",
             "VOL0": "number=0 → _audit-vol0-hidden-first.py の領域",
             "YEARNUM": "西暦が巻番号に化けた誤番号",
             "MISSING": "★本当に欠けている巻",
             "NONUM": "番号なし", "PAGE_UNREAD": "頁の巻情報が取れない(--rebuild)"}
    for k, v in Counter(r[0] for r in rows).most_common():
        print(f"    {k:<12} {v:>7,}巻 ({len({r[2] for r in rows if r[0] == k}):,}頁)  {_note.get(k, '')}")
    print("  照合の強さ:")
    for k, v in Counter(r[1] for r in rows).most_common():
        print(f"    {k:<8} {v:>7,}巻")
    print(f"\n  ★芯(MISSING × SIBLING/TITLE/SLUG) {len(core):,}巻 / {len({r[2] for r in core}):,}頁")
    print(f"     材料: {dict(Counter(r[13] for r in core).most_common())}")
    print(f"  除外内訳: {dict(reasons.most_common())}")
    print(f"\n  → 全件 {OUT}")
    print(f"  → ★芯 {OUT_CORE}")
    print("  ★NEAR は外伝/続編の誤当てが混ざるので芯から外してある(人が見る時の手掛かり)。")
    print("  ★DUP は date_gap_days が大きい行が怪しいが、 実測では **別版(新装版/文庫)の1巻** が主で薄い。")
    _x5o = [r for r in x5 if r[0]]
    print(f"\n  ★x.5 の番外巻(第2の鉱脈): {len(x5):,}件 / うち親頁が特定できた {len(_x5o):,}件")
    print(f"     材料: {dict(Counter(r[4] for r in x5).most_common())}")
    print(f"  → {OUT_X5}")
    print("  ★トリニティ15.5 と同型はこちらで直撃する(種2駆動だと DUP に埋まる)。")


if __name__ == "__main__":
    main()
