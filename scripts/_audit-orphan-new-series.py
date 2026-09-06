"""★孤児series監査: 種2(db-v2)に在るのに **元頁が無い** = 永久に本番へ出ないseriesを検出。

背景(2026-07-25 発見): promote は **元頁駆動**(`for ypath in SRC_DIR.glob('*.yml')` =
  data/manga + data/seeds/preorder-pages)であって DB駆動ではない。
  月次蒸留は種2にレコードを足すだけで「新規seriesの元頁を作る」工程が無いため、
  MADB由来の新規シリーズは **元頁がある分(=予約ルートで先に作られた分)しか出ない**。
  1.2.18 実測: 新292 series 中 頁化 85(うち preorder由来75) / 未頁化 207。

★★2026-09-06 裁定(Fable 5 の判断を Opus 5 が実測で検算): **ここに出る大半は「出すべき取りこぼし」ではない**。
  98%が単巻(BL/TL/レディコミ/ハーレクインの単発読切が主体)で、その6割は楽天caption(ジャンル/あらすじの
  材料)すら無く新規登録protocolの必須メタが揃わない。 3巻以上は僅かで、中身は
  **既存頁の分裂クラスタ**(ラテン表記/新装版/別レーベル= ONE PIECE・幽遊白書・シティーハンター…)、
  **コンビニ廉価再録**、**外国語版**、**アンソロ/ムック**、**裁定済みdropの再出現**。
  → 頁化案件ではなく「除外」+「既存頁への統合」。 頁化は二重頁の量産(HxH型/ARMS型の再生産)。
  ★そこで本監査は class列で「既に本番に在るか」を機械照合し、 芯(= core)だけ別TSVに出す。
  素の件数(数万)を「未掲載の取りこぼし」として読むな。 詳細=記憶 orphan_series_promote_is_srcpage_driven。

判定: ★**本番出力 data/manga.v2 に そのseriesのISBNが1本も出てこない** = 孤児。
  元頁側の title/_skey 一致で見ると merge経路(qid/kana/題ゆれ)を拾えず過大に出るため、
  「実際にサイトに出ているか」という結果基準にする(= 誤検出しない代わりに1回66k走査)。
  ★promote が正当に落とす分(成年/非漫画/画集/雑誌/外国版/題patterns)は除外して報告する
  (= 除外理由は promote 本体から import して二重管理を避ける)。

出力(read-only。 本番/種2 不変):
  docs/production-diagnostics/orphan-new-series.tsv      = 全件(情報は落とさない)
  docs/production-diagnostics/orphan-new-series-core.tsv = ★芯 = 人が見るのはこっち
    芯 = N巻以上 かつ 既存頁に照合できない かつ 外国語版でない かつ 裁定済みdrop題でない
usage: python scripts/_audit-orphan-new-series.py [--since YYYY-MM] [--rebuild] [--core-min-vols N]
  --since = その発売日以降の巻を持つseriesに限る(既定=全件)
  --rebuild = 本番掲載ISBN索引(.cache/live-isbn-index.json)を強制的に作り直す
              ★付け忘れても、 本番ymlが索引より新しければ**自動で**作り直す(古い索引は
                解決済みの案件を孤児として復活させるため。 2026-09-06 トリニティセブンで実踏)
  --core-min-vols = 芯の最小巻数(既定2。 単巻は材料が無く登録protocolを通せないので既定で芯から外す)
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
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SRC_DIRS = [ROOT / "data" / "manga", ROOT / "data" / "seeds" / "preorder-pages"]
IDX = ROOT / ".cache" / "live-isbn-index.json"
OUT = ROOT / "docs" / "production-diagnostics" / "orphan-new-series.tsv"
ISBN = re.compile(r"97[89]\d{10}")
OUT_CORE = ROOT / "docs" / "production-diagnostics" / "orphan-new-series-core.tsv"
HARVEST = ROOT / ".cache" / "torikoboshi" / "harvest.jsonl"
FOREIGN_TITLE = re.compile(r"\[(韓国語|中国語|英語|仏語|独語|西語)\]")
# ★突合用の題正規化: ルビ/記号/空白/版種語を落とす(新装版・別レーベルの分身を拾うため)。 表示には使わない。
#   ルビ = 「特攻(ぶっこみ)の拓」「六道の悪女(おんな)たち」型。 括弧の中身が仮名だけ = ルビと見なして丸ごと捨てる
#   (記号だけ剥がすと「悪女おんなたち」になり本番の「六道の悪女たち」と一致しない)。
_NORM_RUBY = re.compile(r"[（(][ぁ-んァ-ヶーゝゞ・･]+[)）]")
_NORM_DROP_WORDS = re.compile(r"(新装版|完全版|愛蔵版|文庫版|決定版|新版|コミック版|オールカラー版)")
_NORM_SYMBOLS = re.compile("[" + re.escape("".join(
    " \u3000・･:：;；,，.。!！?？'\"“”‘’-–—ー~〜/／\\|(){}[]【】〈〉《》「」『』*＊+＋#＃&＆@☆★♥♡=×")) + "]")


def _pre(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    return _NORM_DROP_WORDS.sub("", _NORM_RUBY.sub("", s))


def norm_title(s):
    """NFKC→小文字→ルビ除去→版種語除去→記号除去。 突合専用(表示に使わない)。"""
    return _NORM_SYMBOLS.sub("", _pre(s))


def latin_key(s):
    """★ラテン表記の題を slug と突合するためのキー(英数字だけ)。

    カナ⇔ラテンは正規化では届かない(「City hunter」と「シティーハンター」)。
    slug規則が外来語をラテン綴りにするので **題がほぼ全部ラテン** の時だけ slug と直接突き合わせる。
    実例= City hunter→city-hunter / CROWS→crows / Monkey Turn→monkey-turn / master keaton→master-keaton。
    """
    t = _pre(s)
    k = re.sub(r"[^a-z0-9]", "", t)
    body = re.sub(r"[^0-9a-z\u3040-\u30ff\u4e00-\u9fff]", "", t)
    # 題の9割以上が英数字 = ラテン題。 3文字未満は誤爆するので採らない。
    return k if body and len(k) >= 3 and len(k) / len(body) >= 0.9 else ""


def load_material():
    """取りこぼしハーベスト(楽天)の材料有無を ISBN→(紹介文有, 書影有) で返す。 無ければ空dict。

    ★材料 = ジャンル/あらすじを書くための一次情報。 これが無い作品は新規登録protocolの
      必須メタ(genre>=1 等)を確定できない = 登録保留(載せない)。 捏造して埋めるのは禁止。
    """
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


def _promote():
    """promote 本体を import (= drop条件の単一ソース。 main は走らない)。"""
    spec = importlib.util.spec_from_file_location("promote_v2", ROOT / "scripts" / "_promote-bulk-v2.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def build_index():
    """本番出力 data/manga.v2 に実在する ISBN の集合(= サイトに出ている巻)。"""
    seen = set()
    n = 0
    for p in glob.glob(str(ROOT / "data" / "manga.v2" / "*.yml")):
        n += 1
        if n % 20000 == 0:
            print(f"    ...{n:,}頁", flush=True)
        try:
            seen.update(ISBN.findall(open(p, encoding="utf-8").read()))
        except Exception:
            continue
    print(f"  本番 {n:,}頁 / 掲載ISBN {len(seen):,}", flush=True)
    IDX.write_text(json.dumps(sorted(seen)), encoding="utf-8")
    return seen


def newest_src_mtime():
    """本番出力 data/manga.v2 の最新更新時刻(中身は読まない= 速い)。"""
    newest, n = 0.0, 0
    with os.scandir(ROOT / "data" / "manga.v2") as it:
        for e in it:
            if e.name.endswith(".yml"):
                m = e.stat().st_mtime
                n += 1
                if m > newest:
                    newest = m
    return newest, n


def _imprint_dropped(P, imp):
    """promote の imprint drop 条件(= L1216付近と同一)を1つの版について判定。"""
    imp = imp or ""
    imp_l = imp.lower()
    if any(p in imp for p in P.DROP_IMPRINT_PATTERNS):
        return True
    if any(p in imp_l for p in P.DROP_IMPRINT_LOWER_PATTERNS):
        return True
    if "=" not in imp and any(p in imp_l for p in P.DROP_IMPRINT_LOWER_PATTERNS_NO_EQ):
        return True
    return False


def _all_imprints_dropped(P, imps):
    """全版が drop対象 = このseriesは promote が正当に落とす(1版でも残れば孤児候補)。"""
    imps = {i for i in (imps or set())}
    return bool(imps) and all(_imprint_dropped(P, i) for i in imps)


def main():
    since = None
    if "--since" in sys.argv:
        since = sys.argv[sys.argv.index("--since") + 1]
    core_min_vols = 2
    if "--core-min-vols" in sys.argv:
        core_min_vols = int(sys.argv[sys.argv.index("--core-min-vols") + 1])
    _today = datetime.date.today()
    recent_cut = "%04d-%02d" % (_today.year - 1, _today.month)
    # ★索引の陳腐化を自動検知する。 古い索引は **解決済みの案件を孤児として復活させる**
    #   (2026-09-06 実害: 09-02の索引のまま回して、 09-03に本編頁へ結線済みの
    #    トリニティセブン19〜34巻を「まだ出ていない」と誤って上げた = ユーザ発見)。
    #   注意書き「promote後は --rebuild」だけでは付け忘れが静かに数字を膨らませるので機械で見る。
    stale = False
    if IDX.exists():
        newest, npages = newest_src_mtime()
        if newest > IDX.stat().st_mtime:
            stale = True
            age = (newest - IDX.stat().st_mtime) / 3600
            print(f"[1/3] ★索引が古い(本番ymlの方が {age:.1f}h 新しい / {npages:,}頁) → 自動で作り直す",
                  flush=True)
    if "--rebuild" in sys.argv or not IDX.exists() or stale:
        print("[1/3] 本番掲載ISBN索引を構築 ...", flush=True)
        live = build_index()
    else:
        live = set(json.loads(IDX.read_text(encoding="utf-8")))
        print(f"[1/3] 本番掲載ISBN索引(既存・鮮度OK) {len(live):,}", flush=True)

    print("[2/3] promote の drop条件を読み込み ...", flush=True)
    P = _promote()
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    rows_all = con.execute(
        "SELECT s.id, s.series_key, s.title, s.subtitle, s.adult_score, s.qid FROM series s").fetchall()
    non_manga = {e["series_key"] for e in
                 (P.yaml.safe_load((ROOT / "data/seeds/non-manga-drop.yml").read_text(encoding="utf-8")) or {})
                 .get("non_manga", []) if isinstance(e, dict) and e.get("series_key")}
    art_books = set(P.load_art_books().keys())
    drop_keys = set(P._load_drop_series_keys() or set())

    # ★分裂クラスタ切り分け(2026-09-06 強化): 素の題の完全一致だけでは
    #   ラテン表記(City hunter / CROWS / COJI-COJI)・新装版・別レーベルの分身を全部「未掲載」に落としていた。
    #   → 「正規化題の一致」 + 「著者一致 × 題の包含」 の2段で照合する。
    #   ★imprint文字列で「コンビニ廉価再録」を機械判定するのは **やらない**
    #     (promote本体の注記どおり Gコミックス/SPコミックス/マンサン等は正規レーベルで一括不可)。
    #     再録・別版・分裂は全部「著者が同じ」に乗るので、著者軸で拾って人が裁く。
    _ix = json.loads((ROOT / "data" / "manga-list-index.json").read_text(encoding="utf-8"))
    _ti = _ix["f"].index("title")
    _si = _ix["f"].index("slug")
    _ai = _ix["f"].index("authors")

    def _aulist(v):
        # 索引v2は authors を "name\tkana" のパック文字列で持つ(旧dict形式も互換)
        out = []
        for a in (v or []):
            nm = a.split("\t")[0] if isinstance(a, str) else a.get("name", "")
            if nm:
                out.append(nm)
        return out

    def _au0(v):
        lst = _aulist(v)
        return lst[0] if lst else ""

    live_titles = {}      # 正規化題 -> slug
    live_slugs = {}       # slugの英数字キー -> slug (ラテン題の突合先)
    live_by_author = {}   # 正規化著者 -> [(正規化題, slug)]
    live_authors = set()  # 正規化著者(= その作家は既にサイトに出ている)
    page_authors = {}     # slug -> {正規化著者}  ★同名別作品を弾く著者ゲート用
    for _r in _ix["d"]:
        page_authors.setdefault(_r[_si], set()).update(
            norm_title(x) for x in _aulist(_r[_ai]) if norm_title(x))
        _nt = norm_title(_r[_ti])
        if _nt:
            live_titles.setdefault(_nt, _r[_si])
        live_slugs.setdefault(re.sub(r"[^a-z0-9]", "", _r[_si].lower()), _r[_si])
        _a = norm_title(_au0(_r[_ai]))
        if _a:
            live_authors.add(_a)
            live_by_author.setdefault(_a, []).append((_nt, _r[_si]))
    print(f"  本番索引 {len(_ix['d']):,}頁 / 正規化題 {len(live_titles):,} / slug {len(live_slugs):,}"
          f" / 著者 {len(live_authors):,}", flush=True)

    # ★裁定済みdropの再出現: non-manga-drop / drop_keys は **series_key** で持つが、
    #   孤児側は同じ作品の**別クラスタ**なので key が違い素通りしていた
    #   (実例= ユーザが drop 裁定した「スゴ盛!本当にあった…」が毎回「未掲載」で上がっていた)。
    #   → 裁定済みseriesの **題** も突合対象にする。
    dropped_titles = set()
    for _sid2, _key2, _t2, _s2, _a2, _q2 in rows_all:
        if _key2 in non_manga or _key2 in drop_keys:
            _n2 = norm_title(_t2)
            if _n2:
                dropped_titles.add(_n2)
    print(f"  裁定済みdrop題 {len(dropped_titles):,}", flush=True)

    material = load_material()
    print(f"  楽天ハーベスト材料 {len(material):,} ISBN"
          + ("" if material else "  (未取得= 材料列は空になる)"), flush=True)

    print("[3/3] series を走査 ...", flush=True)
    rows = rows_all
    vols = {}
    for sid, ib, rd in con.execute(
        "SELECT e.series_id, v.isbn13, v.release_date FROM volumes v "
            "JOIN editions e ON e.id=v.edition_id WHERE v.isbn13 IS NOT NULL AND v.isbn13!=''"):
        vols.setdefault(sid, []).append((ib, rd or ""))
    imprints, edtypes = {}, {}
    for sid, ip, ty in con.execute("SELECT series_id, imprint, type FROM editions"):
        imprints.setdefault(sid, set()).add(ip or "")
        edtypes.setdefault(sid, set()).add(ty or "")
    authors = {}
    for sid, nm in con.execute(
            "SELECT sa.series_id, m.name FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id"):
        authors.setdefault(sid, []).append(nm)

    orphans, reasons = [], {}
    for sid, key, title, sub, adult, qid in rows:
        vv = vols.get(sid) or []
        if not vv:
            continue                                    # ISBN無し = 判定不能(別監査の領域)
        if since and max(rd for _, rd in vv) < since:
            continue
        title = title or ""
        if any(ib in live for ib, _ in vv):
            continue                                    # 1巻でもサイトに出ている = 孤児でない
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
        elif _all_imprints_dropped(P, imprints.get(sid, set())):
            why = "imprint"          # ★全版がコンビニ本/増刊/bilingual等 = promoteが正当に落とす
        elif edtypes.get(sid) and not (edtypes[sid] & P.KEEP_EDITION_TYPES):
            why = "edition_type"     # ★全版が anime/other/renewal 等 = 掲載対象外の版種
        if why:
            reasons[why] = reasons.get(why, 0) + 1
            continue
        dates = sorted(rd for _, rd in vv if rd)
        auths = authors.get(sid, [])
        nt = norm_title(title)
        na = [norm_title(a) for a in auths if a]

        # ---- 分類。 ★行は消さない = 「何であるか」のラベル付け。
        #   芯から外してよいのは **同一作品だと機械的に言い切れる一致だけ**(題の完全一致 / ラテン題=slug)。
        #   ★著者ゲート: 題が一致しても著者が1人も重ならないなら同名別作品の可能性を残す
        #     (本番 kenkaku-shoubai-saitou2003=さいとう・たかを版 / 孤児=大島やすいち版 は別の漫画)。
        #     どちらかの著者が空の時は判定材料が無いので「一致」に倒す(過検出を避ける)。
        def _same_work(ps):
            pa = page_authors.get(ps) or set()
            oa = {x for x in na if x}
            return (not pa) or (not oa) or bool(pa & oa)

        cls, hit_slug = "未掲載", ""
        lk = latin_key(title)
        if nt and nt in live_titles:
            _s = live_titles[nt]
            cls, hit_slug = ("既存頁(題一致)", _s) if _same_work(_s) else ("同題別著者(要確認)", "")
        elif lk and lk in live_slugs:
            _s = live_slugs[lk]
            cls, hit_slug = ("既存頁(slug一致)", _s) if _same_work(_s) else ("同題別著者(要確認)", "")
        elif FOREIGN_TITLE.search(title) or all(not ib.startswith("9784") for ib, _ in vv):
            cls = "外国語版(scope外)"            # ★ISBN国コード 978-4 = 日本
        elif nt and nt in dropped_titles:
            cls = "裁定済みdrop題"

        # ---- 類似頁(注記のみ・★classも芯も動かさない)
        #   「著者一致 × 題の包含」は 別版/分裂/再録を当てる一方、 呪術廻戦≡ / 東京卍リベンジャーズ
        #   〜場地圭介からの手紙〜 / デッドマウント・デスプレイ外伝 のような **本物の別作品** も
        #   親作品に吸ってしまう。 芯から消すと仕事を隠すので、 人が裁くための手掛かりに留める。
        near = ""
        if not hit_slug:
            for a in na:
                for pt, ps in live_by_author.get(a, ()):
                    if pt and nt and min(len(pt), len(nt)) >= 3 and (pt.startswith(nt) or nt.startswith(pt)):
                        near = ps
                        break
                if near:
                    break

        # ---- 材料(= 登録protocolの必須メタを確定できるか)
        mats = [material[ib] for ib, _ in vv if ib in material]
        if not mats:
            mat = "未取得"
        elif any(c and i for c, i in mats):
            mat = "紹介文+書影"
        elif any(c for c, _ in mats):
            mat = "紹介文のみ"
        elif any(i for _, i in mats):
            mat = "書影のみ"
        else:
            mat = "なし"

        orphans.append((key, title, cls, sub or "", len(vv),
                        dates[0] if dates else "", dates[-1] if dates else "",
                        " / ".join(sorted(imprints.get(sid, set()))[:3]),
                        " / ".join(auths[:3]), vv[0][0],
                        hit_slug, near, mat, "済" if any(a in live_authors for a in na) else ""))

    orphans.sort(key=lambda r: (r[6], r[1]), reverse=True)
    HEAD = ("series_key\ttitle\tclass\tsubtitle\tvols\tfirst_date\tlast_date\timprints\tauthors\tisbn"
            "\t既存頁slug\t類似頁\t材料\t著者既掲載\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        f.write(HEAD)
        for r in orphans:
            f.write("\t".join(str(x) for x in r) + "\n")

    # ★芯 = 人が見るのはここだけ。 単巻は材料が無く登録protocolを通せないので既定で外す。
    CORE_CLS = ("未掲載", "同題別著者(要確認)")   # ★同名別作品952件が正当に併存する = 隠さない
    core = [r for r in orphans if r[2] in CORE_CLS and r[4] >= core_min_vols]
    with OUT_CORE.open("w", encoding="utf-8", newline="") as f:
        f.write(HEAD)
        for r in core:
            f.write("\t".join(str(x) for x in r) + "\n")

    from collections import Counter
    print("\n=== 孤児series (種2に在るが元頁が無い) ===")
    print(f"  全件 {len(orphans):,}   (promoteが正当に落とす分は除外済 {reasons})")
    print("  class内訳:")
    for k, v in Counter(r[2] for r in orphans).most_common():
        print(f"    {k:<16} {v:>7,}")
    solo = sum(1 for r in orphans if r[2] == "未掲載" and r[4] == 1)
    print(f"  ※「未掲載」のうち単巻 {solo:,} = BL/TL/レディコミ等の単発読切が主体。")
    print("     材料(楽天紹介文)なしは必須メタを確定できない = 載せない(捏造して埋めない)。")
    print(f"\n  ★芯({core_min_vols}巻以上 × class∈{CORE_CLS}): {len(core):,}")
    if core:
        c12 = [r for r in core if r[6] >= recent_cut]
        print(f"     うち直近12か月({recent_cut}以降) {len(c12):,}   ← ★月次で見るのはこの数")
        print(f"     材料: {dict(Counter(r[12] for r in core).most_common())}")
        print(f"     類似頁の手掛かりあり: {sum(1 for r in core if r[11]):,}"
              "  (= 別版/外伝/分裂の疑い → 頁化でなく統合を先に検討)")
        print(f"     著者が既にサイトに在る: {sum(1 for r in core if r[13]):,} / {len(core):,}")
    print(f"\n  → 全件 {OUT}")
    print(f"  → ★芯 {OUT_CORE}")
    print("  ★全件の数字を「未掲載の取りこぼし」として読むな(2026-09-06 裁定)。 芯だけ見る。")


if __name__ == "__main__":
    main()
