# -*- coding: utf-8 -*-
"""edition-canonical/*.yml の健全性チェック (= 無警告で読み飛ばされる事故の番人)。

★なぜ要るか: promote の get_edition_canonical() は
    try: s = _yload(f)  ... except Exception: continue
で seed を読むため、**YAMLが壊れていても何も言わずにその1本だけ無視される**。
reflect は「再生成N / 検証ゲートOK」と成功を返すので、頁が直っていないことに
気づけない(2026-08-17 実験人形ダミー・オスカーで実踏 = volumes配下のインデントが
2スペースと0スペースの混在でパース失敗していた)。

見るもの:
  1. YAML としてパースできるか
  2. slug フィールドがあり、ファイル名(= SRC slug)と一致するか
     (キーは slug フィールドなので、不一致だと別頁に効くか、どこにも効かない)
  3. data/manga.v2/<slug>.yml が実在するか (= 死にキー検出)
  4. volumes が空でないか / number が重複していないか
  5. release_date が文字列か (裸の日付は YAML が date 型にしてしまう)
  6. ★種4(volumes-supplement)の巻を取りこぼしていないか
     canonical は standard 版を丸ごと差し替えるので、NDL/楽天で裏取り済みの
     取込もれ巻(種4)が黙って頁から消える(2026-08-17 エデンの東北ほか5頁で実踏)。
  7. ★連載中の続巻を取りこぼしていないか(2026-08-20 新設)
     canonical は巻を列挙して固定するため、連載中作品は蒸留で種2に続巻が入っても
     頁には永久に出ない(鬼平犯科帳/釣りバカ日誌/ゴルゴ13ほか5頁で実踏)。
     判定 = seed主版(volumes)のISBNで種2 editionを逆引きし(同一imprintに限定)、
     seed最大巻より後の巻番号 かつ seed最終日以降の発売日 の巻が種2に在れば NG。
     ※.cache/db-v2.sqlite が無い環境ではこの検査だけ skip(他は従来どおり)。

使い方:
  python scripts/_check-edition-canonical.py                # 全seed検査(異常があれば終了コード1)
  python scripts/_check-edition-canonical.py --slugs a,b,c  # 指定slug(=SRC slug/ファイル名)だけ検査
                                                            # (reflect の canonical ゲートが使う高速経路)
"""
import argparse
import io
import sys
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "data" / "seeds" / "edition-canonical"
SRC_DIR = ROOT / "data" / "manga.v2"
SUPP = ROOT / "data" / "seeds" / "volumes-supplement.yml"
DB = ROOT / ".cache" / "db-v2.sqlite"


def _seed4_by_title():
    """種4を『作品名 → [(isbn13, 巻)]』に畳む(series_keys の name: 部分で引く)。"""
    out = {}
    if not SUPP.exists():
        return out
    with SUPP.open(encoding="utf-8") as f:
        d = yaml.safe_load(f) or {}
    for v in d.get("volumes") or []:
        i = v.get("isbn13")
        if not i:
            continue
        for k in v.get("series_keys") or []:
            nm = str(k).split("name:")[-1].split("|")[0]
            out.setdefault(nm, set()).add((str(i), v.get("number")))
    return out


_S4 = None
_DB = None  # sqlite3.Connection | False(=無し)
_CLAIMED = None  # 全canonical seed + volume-exclude が既に帰属を確定しているISBN集合


def _claimed_isbns():
    """全seedが主張するISBN + volume-exclude(除外確定)のISBN。
    ★続巻検査の偽陽性対策: franchise分割頁(人狼ゲーム型)では、種2の汚染クラスタに
    「別頁の巻」が高番号で同居する。そのISBNが別のcanonicalに収載済みなら
    帰属は確定している=この頁の続巻ではない。"""
    global _CLAIMED
    if _CLAIMED is not None:
        return _CLAIMED
    s = set()

    def _walk(o):
        if isinstance(o, dict):
            i = o.get("isbn13")
            if i:
                s.add(str(i))
            for v in o.values():
                _walk(v)
        elif isinstance(o, list):
            for v in o:
                _walk(v)

    for p in SEED_DIR.glob("*.yml"):
        try:
            with p.open(encoding="utf-8") as f:
                _walk(yaml.safe_load(f))
        except Exception:
            continue
    for name in ("volume-exclude.yml", "volume-exclude-isbn.yml"):
        p = ROOT / "data" / "seeds" / name
        if p.exists():
            try:
                with p.open(encoding="utf-8") as f:
                    _walk(yaml.safe_load(f))
            except Exception:
                pass
    _CLAIMED = s
    return s


_IDX = None  # ISBN→頁slug索引(.cache/isbn-page-index.json) | False(=無し)


def _isbn_page_index():
    """本番ISBN索引(あれば)。無ければ None = 索引による除外はしない(保守側=flagを残す)。"""
    global _IDX
    if _IDX is None:
        p = ROOT / ".cache" / "isbn-page-index.json"
        if p.exists():
            import json
            with p.open(encoding="utf-8") as f:
                _IDX = json.load(f)
        else:
            _IDX = False
    return _IDX if _IDX is not False else None


def _db():
    """種2への接続(1回だけ)。無ければ False = 続巻検査をskip。"""
    global _DB
    if _DB is None:
        if DB.exists():
            import sqlite3
            _DB = sqlite3.connect(str(DB))
        else:
            _DB = False
    return _DB


def check_open_tail(seed, problems):
    """★検査7: 連載中canonicalの続巻取りこぼし。
    seed主版(volumes)のISBNで種2 editionを逆引きし、最多一致editionと同じimprintの
    edition群に「seed最大巻より後 かつ seed最終発売日以降」の巻が在れば NG。
    imprint一致に限定するのは、種2クラスタには別版/別時代のrunが同居するため
    (=そもそも canonical が要る理由)。日付条件で旧runの接ぎ木も弾く。"""
    con = _db()
    if not con:
        return
    main = [v for v in (seed.get("volumes") or []) if isinstance(v, dict)]
    main_isbns = [str(v["isbn13"]) for v in main if v.get("isbn13")]
    nums = [v["number"] for v in main if isinstance(v.get("number"), int)]
    dates = [str(v["release_date"]) for v in main if v.get("release_date")]
    if not main_isbns or not nums or not dates:
        return  # ISBN/巻番号/日付の無いseedは逆引き不能=対象外(古典など)
    max_num, max_date = max(nums), max(dates)
    # seed全体(versions/extra/compact含む)の既収載ISBN
    have = set(main_isbns)
    def _grab(vols):
        for v in vols or []:
            if isinstance(v, dict) and v.get("isbn13"):
                have.add(str(v["isbn13"]))
    for vv in seed.get("versions") or []:
        _grab(vv.get("volumes"))
    for xe in seed.get("extra_editions") or []:
        _grab(xe.get("volumes"))
    _grab((seed.get("compact_edition") or {}).get("volumes"))
    # 逆引き: seed ISBN → 種2 edition(重なりの多い順)
    from collections import Counter
    hits = Counter()
    CH = 400
    for i in range(0, len(main_isbns), CH):
        chunk = main_isbns[i:i + CH]
        q = ("SELECT edition_id FROM volumes WHERE isbn13 IN (%s)"
             % ",".join("?" * len(chunk)))
        for (eid,) in con.execute(q, chunk):
            hits[eid] += 1
    if not hits:
        return
    best_eid, best_n = hits.most_common(1)[0]
    if best_n < min(2, len(main_isbns)):
        return  # アンカー弱すぎ(1冊一致のみ)=誤editionを掴む危険
    row = con.execute("SELECT imprint FROM editions WHERE id=?", (best_eid,)).fetchone()
    imp = (row[0] or "") if row else ""
    # 同imprintの一致edition群から続巻候補を拾う
    cand = []
    for eid, n in hits.items():
        r = con.execute("SELECT imprint FROM editions WHERE id=?", (eid,)).fetchone()
        if not r or (r[0] or "") != imp:
            continue
        for num, isbn, rd in con.execute(
                "SELECT number, isbn13, release_date FROM volumes WHERE edition_id=?", (eid,)):
            if not isinstance(num, int) or num <= max_num:
                continue
            if not isbn or str(isbn) in have:
                continue
            if str(isbn) in _claimed_isbns():
                continue  # 別頁のcanonical/volume-excludeが帰属確定済(人狼ゲーム型の番号衝突)
            if not rd or str(rd) < max_date:
                continue  # 旧run(接ぎ木)の高番号は日付で弾く
            cand.append((num, str(isbn), str(rd)))
    if cand:
        cand = sorted(set(cand))
        problems.append(
            "★連載中の続巻が種2に在るのにseed未収載(imprint=%s) %s%s"
            " = canonicalが巻を固定し頁に出ない → seedへ種2の値で追記する"
            % (imp or "?", cand[:8], " …計%d巻" % len(cand) if len(cand) > 8 else ""))


def check_volumes(where, vols, problems):
    if not vols:
        problems.append("%s: volumes が空" % where)
        return
    nums = []
    for v in vols:
        if not isinstance(v, dict):
            problems.append("%s: volume が dict でない (%r)" % (where, v))
            continue
        if "number" not in v:
            problems.append("%s: number 無しの volume" % where)
        else:
            nums.append(v["number"])
        d = v.get("release_date")
        if d is not None and not isinstance(d, str):
            problems.append("%s: release_date が文字列でない (%r) = 引用符が要る" % (where, d))
        i = v.get("isbn13")
        if i is not None and not (isinstance(i, str) and len(i) == 13 and i.isdigit()):
            problems.append("%s: isbn13 が13桁文字列でない (%r)" % (where, i))
    dup = {n for n in nums if nums.count(n) > 1}
    if dup:
        problems.append("%s: 巻番号の重複 %s" % (where, sorted(dup)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", default="",
                    help="検査対象を絞る(カンマ区切りのSRC slug=seedファイル名)。reflect用高速経路")
    a = ap.parse_args()
    files = sorted(SEED_DIR.glob("*.yml"))
    if a.slugs:
        want = {s.strip() for s in a.slugs.split(",") if s.strip()}
        files = [p for p in files if p.stem in want]
    bad = 0
    for p in files:
        problems = []
        try:
            with p.open(encoding="utf-8") as f:
                seed = yaml.safe_load(f)
        except Exception as ex:
            print("NG %s\n   YAMLパース失敗(= promoteが無警告でskipする): %s"
                  % (p.name, str(ex).replace("\n", " ")[:200]))
            bad += 1
            continue
        if not isinstance(seed, dict) or not seed.get("slug"):
            problems.append("slug フィールドが無い(= promoteが読み込まない)")
        else:
            slug = str(seed["slug"])
            if slug != p.stem:
                problems.append("slug=%r がファイル名 %r と不一致" % (slug, p.stem))
            if not (SRC_DIR / (slug + ".yml")).exists():
                problems.append("data/manga.v2/%s.yml が無い(= 死にキー)" % slug)
            check_volumes("volumes", seed.get("volumes"), problems)
            # ★種4の取りこぼし
            global _S4
            if _S4 is None:
                _S4 = _seed4_by_title()
            title = None
            f2 = SRC_DIR / (slug + ".yml")
            if f2.exists():
                try:
                    with f2.open(encoding="utf-8") as fh:
                        title = (yaml.safe_load(fh) or {}).get("title")
                except Exception:
                    pass
            if title and title in _S4:
                have = set()
                for v in seed.get("volumes") or []:
                    if v.get("isbn13"):
                        have.add(str(v["isbn13"]))
                for xe in seed.get("extra_editions") or []:
                    for v in xe.get("volumes") or []:
                        if v.get("isbn13"):
                            have.add(str(v["isbn13"]))
                miss = [(i, n) for i, n in _S4[title] if i not in have]
                # ★偽陽性2型を頁実体で除外(2026-08-20):
                #   ①種4は同名別頁(kinpeibai-watanabe-1995/ultraman-kazumine-1968型)を
                #     狙っていることがある(title照合はslugを区別できない)→ISBN索引で
                #     どこかの頁に生きていればOK
                #   ②seedに無くても頁には載る経路がある(golgo v173=compact/routing型、
                #     種4のshinsoban等はcanonicalが触らない)→自頁ファイルに在ればOK
                if miss:
                    page_txt = ""
                    if f2.exists():
                        try:
                            page_txt = f2.read_text(encoding="utf-8")
                        except Exception:
                            pass
                    idx = _isbn_page_index()
                    miss = [(i, n) for i, n in miss
                            if i not in page_txt
                            and i not in _claimed_isbns()  # 別seedが収載済(索引stale対策)
                            and (idx is None or i not in idx)]
                if miss:
                    problems.append(
                        "種4(取込もれ巻)がどの頁にも出ていない %s = canonicalが上書きして消している疑い"
                        "(索引が古い可能性もある→ python scripts/_exists.py --build で再確認)"
                        % sorted(miss)[:6])
            for i, xe in enumerate(seed.get("extra_editions") or []):
                check_volumes("extra_editions[%d](%s)" % (i, xe.get("label")),
                              xe.get("volumes"), problems)
            # ★検査7: 連載中の続巻取りこぼし(種2が無い環境ではskip)
            check_open_tail(seed, problems)
        if problems:
            print("NG %s" % p.name)
            for m in problems:
                print("   " + m)
            bad += 1
    print("\nedition-canonical: %d 本 / 異常 %d 本" % (len(files), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
