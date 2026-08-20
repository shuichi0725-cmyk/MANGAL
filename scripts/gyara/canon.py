# -*- coding: utf-8 -*-
"""ギャラ型是正用: 種2(db-v2)の edition から canonical seed を組み立てるヘルパ。

promote が既に解決済みの本番ymlから「ISBN出版者記号 → 出版社名」表を1回だけ作り、
ISBNを持つrunの版元はそこから引く(推測しない)。ISBNが無いrunは publisher を
与えなければ '不明' になる。

使い方(呼び出し側の例):
    import canon
    canon.build('kaze-no-saburou',
                main=dict(ed=464, label='通常版', imprint='マンガくんコミックス'),
                extras=[dict(ed=465, type='shinsoban', label='ビッグコミックス版')],
                source='...')
"""
import io
import json
import os
import re
import sqlite3
import collections
import glob

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB = os.path.join(ROOT, ".cache", "db-v2.sqlite")
CANON_DIR = os.path.join(ROOT, "data", "seeds", "edition-canonical")
# ★記号表は git 追跡 seed が一次資産(2026-08-20)。本番66k頁から学習した
#   「ISBN出版者記号→出版社名」1,629記号は再学習に~数分かかる上、.cache 置きだと
#   gitignore で消える・別PCで使えない。無ければ従来どおり学習して seed へ書き出す。
PREFIX_CACHE = os.path.join(ROOT, "data", "seeds", "isbn-publisher-prefix.json")

_db = sqlite3.connect(DB)
_db.row_factory = sqlite3.Row


def _prefixes(isbn13):
    """9784XXXXX… から出版者記号候補を長い順に返す。
    ★"9784" を落とした残り8桁の先頭 5/4/3/2 桁。VERIFIED のキーもこの形で書く
      (先頭の 4 は付けない。付けると一生ヒットしない = 実踏)。"""
    if not isbn13 or not isbn13.startswith("9784"):
        return []
    body = isbn13[4:12]
    return [body[:n] for n in (5, 4, 3, 2)]


def prefix_table():
    """本番ymlのeditionから ISBN記号→出版社名 を学習(初回のみ・以後キャッシュ)。"""
    if os.path.exists(PREFIX_CACHE):
        with io.open(PREFIX_CACHE, encoding="utf-8") as f:
            return json.load(f)
    import yaml
    votes = collections.defaultdict(collections.Counter)
    for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
        try:
            with io.open(p, encoding="utf-8") as f:
                d = yaml.safe_load(f)
        except Exception:
            continue
        for e in (d or {}).get("editions") or []:
            pub = e.get("publisher")
            if not pub:
                continue
            for v in e.get("volumes") or []:
                i = v.get("isbn13")
                if i:
                    # ★記号長は社ごとに違う(2〜5桁)。全長で票を取り、引く時に
                    #   「純度が高い最長の記号」を選ぶ。5桁固定だと1件も引けない。
                    for pf in _prefixes(i):
                        votes[pf][pub] += 1
    table = {}
    for pf, c in votes.items():
        top, n = c.most_common(1)[0]
        tot = sum(c.values())
        if tot >= 8 and n / tot >= 0.9:
            table[pf] = top
    with io.open(PREFIX_CACHE, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(table, ensure_ascii=False, indent=0, sort_keys=True) + "\n")
    return table


# ★本セッションで NDL / 楽天 により版元を直接確認できた出版者記号(学習表が
#   票数不足・純度不足で拾えなかった分だけを手当て)。だろう運転はしない。
VERIFIED = {
    "775": "マンガショップ",       # NDL マンガショップシリーズ
    "834": "ホーム社",             # NDL キャプテン/ちばてつや全集
    "862": "小池書院",             # NDL 首斬り朝 愛蔵版
    "883": "小池書院",             # 道草文庫/劇画キングシリーズ(本番の解決値と一致)
    "795": "アース出版局",         # NDL 漫画名作館
    "8727": "アース出版局",        # NDL 漫画名作館スペシャル(872帯は大空社と共有なので4桁で切る)
    "8723": "大空社",              # NDL 一平全集 大空社復刻
    "778": "小学館クリエイティブ",  # NDL 限定版BOX ほか
    "073": "はちどり",             # NDL 主婦の友ヒットシリーズ Comic魂別冊
    "074": "はちどり",             # 同上
    "814": "ごま書房新社",         # Goma books
    "845": "リイド社",             # NDL SPコミックス
    "418": "世界文化社",           # NDL アリババコミックス/セブン文庫
    "835": "復刊ドットコム",       # NDL 復刻決定版 ほか
}

_TABLE = None


def pub_of(isbns):
    """runのISBN群から出版社名を多数決で引く。引けなければ None。"""
    global _TABLE
    if _TABLE is None:
        _TABLE = prefix_table()
    c = collections.Counter()
    for i in isbns:
        for pf in _prefixes(i):
            if pf in VERIFIED:
                c[VERIFIED[pf]] += 1
                break
            if pf in _TABLE:
                c[_TABLE[pf]] += 1
                break
    return c.most_common(1)[0][0] if c else None


def rows(ed):
    return [(r["number"], r["isbn13"], r["release_date"], r["volume_label"])
            for r in _db.execute(
                "SELECT number,isbn13,release_date,volume_label FROM volumes "
                "WHERE edition_id=?", (ed,)).fetchall()]


def imprint_of(ed):
    r = _db.execute("SELECT imprint FROM editions WHERE id=?", (ed,)).fetchone()
    return r["imprint"] if r else None


def dedup(lst):
    """同じ巻番号が複数行あるときは最も古い日付の行を採る(重版を落とす)。"""
    best = {}
    for n, i, d, lab in lst:
        cur = best.get(n)
        if cur is None:
            best[n] = (n, i, d, lab)
            continue
        cd = cur[2] or "9999"
        nd = d or "9999"
        if nd < cd or (cur[1] is None and i):
            best[n] = (n, i, d or cur[2], lab or cur[3])
    return [best[k] for k in sorted(best)]


def renum(lst):
    """巻番号が壊れている(全部0や1)runを発売日→ISBN順に1..nへ振り直す。"""
    lst = sorted(lst, key=lambda r: (r[2] or "", r[1] or ""))
    return [(k + 1, i, d, lab) for k, (n, i, d, lab) in enumerate(lst)]


def _emit(lst, ind):
    o = []
    for n, i, d, lab in lst:
        o.append("%s- number: %s" % (ind, n))
        if i:
            o.append("%s  isbn13: '%s'" % (ind, i))
        o.append("%s  release_date: %s" % (ind, ("'%s'" % d) if d else "null"))
        if lab:
            o.append("%s  volume_label: '%s'" % (ind, str(lab).replace("'", "''")))
    return "\n".join(o)


def _lost(n_in, spec, kept):
    allrows = []
    for ed in ([spec["ed"]] if "ed" in spec else spec.get("eds", [])):
        allrows += rows(ed)
    if spec.get("date_lt"):
        allrows = [r for r in allrows if (r[2] or "0") < spec["date_lt"]]
    if spec.get("date_ge"):
        allrows = [r for r in allrows if (r[2] or "9") >= spec["date_ge"]]
    keptset = {(r[0], r[1]) for r in kept}
    # ★ISBN無しの行も報告する。ISBN持ちだけ見ていると、ISBNの無い古いrunで
    #   実在の巻がdedupに巻き込まれても気づけない(live-machine/名たんていカゲマンで実踏)。
    return [r for r in allrows if (r[0], r[1]) not in keptset]


def _prep(spec):
    vs = []
    for ed in ([spec["ed"]] if "ed" in spec else spec.get("eds", [])):
        vs += rows(ed)
    # ★1つのeditionに初版runと後年の重版runが同居していることがある。
    #   date_lt / date_ge / isbn_pre で切り分ける(切った側は別specで拾うこと)。
    if spec.get("date_lt"):
        vs = [r for r in vs if (r[2] or "0") < spec["date_lt"]]
    if spec.get("date_ge"):
        vs = [r for r in vs if (r[2] or "9") >= spec["date_ge"]]
    if spec.get("isbn_pre"):
        vs = [r for r in vs if r[1] and r[1].startswith(spec["isbn_pre"])]
    if spec.get("drop_isbn_pre"):
        vs = [r for r in vs if not (r[1] and r[1].startswith(spec["drop_isbn_pre"]))]
    n_in = len(vs)
    vs = renum(vs) if spec.get("renum") else dedup(vs)
    # ★dedupは「同じ巻番号の重版」を落とす前提。巻番号が壊れている(全部1や2の)runだと
    #   実在の別の巻まで巻き込んで消す。落ちた行にISBNが在るなら renum=True を疑う。
    lost = [r for r in ([] if spec.get("renum") else _lost(n_in, spec, vs))]
    if lost:
        print("  !! %s: dedupで %d行 消えた(ISBN持ち %d) 消えた巻=%s。重版の重複なら正常、"
              "実在の別巻なら renum=True か手当てが要る"
              % (spec.get("ed") or spec.get("eds"), len(lost),
                 sum(1 for r in lost if r[1]),
                 sorted({r[0] for r in lost})[:12]))
    isbns = [i for _, i, _, _ in vs if i]
    pub = spec.get("publisher") or pub_of(isbns) or "不明"
    imp = spec.get("imprint")
    if imp is None:
        imp = imprint_of(spec.get("ed") or (spec.get("eds") or [None])[0])
    return vs, pub, imp


def build(slug, main, extras=(), source="", suppress=()):
    mv, mpub, mimp = _prep(main)
    head = ["slug: %s" % slug]
    if main.get("label"):
        head.append("canonical_label: %s" % main["label"])
    head.append("canonical_publisher: %s" % mpub)
    if mimp:
        head.append("canonical_imprint: %s" % mimp)
    if suppress:
        head.append("suppress_types:")
        head += ["- %s" % s for s in suppress]
    head.append("source: '%s'" % source.replace("'", "''"))
    body = ["volumes:", _emit(mv, "")]
    if extras:
        body.append("extra_editions:")
        for x in extras:
            xv, xpub, ximp = _prep(x)
            if not xv:
                continue
            body.append("- type: %s" % x.get("type", "shinsoban"))
            body.append("  label: %s" % x["label"])
            if ximp:
                body.append("  imprint: %s" % ximp)
            body.append("  publisher: %s" % xpub)
            body.append("  volumes:")
            body.append(_emit(xv, "  "))
    y = "\n".join(head + body) + "\n"
    path = os.path.join(CANON_DIR, slug + ".yml")
    io.open(path, "w", encoding="utf-8", newline="\n").write(y)
    import yaml
    d = yaml.safe_load(io.open(path, encoding="utf-8"))
    return "%-34s main %2d冊(%s) extra %d" % (
        slug, len(d["volumes"]), mpub, len(d.get("extra_editions") or []))
