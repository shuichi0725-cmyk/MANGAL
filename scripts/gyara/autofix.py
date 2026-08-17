# -*- coding: utf-8 -*-
"""ギャラ型(巻×発売日の大逆行)の一括是正。

方針:
  種2(db-v2)が持つ edition = 実際の「版(run)」なので、頁の standard タブに
  複数 run が畳み込まれて日付が逆行しているものを、run ごとの版タブに戻す。
  ★情報は作らない。MADB の edition/imprint/巻番号/日付 をそのまま使い、
    版元だけ ISBN出版者記号(本番66k頁から学習)+NDL確認済みのレーベル表から解決する。
    解決できなければ「不明」と明示する。

安全弁:
  - 判断が要る形(候補が拮抗/巻番号が壊れていて採番の根拠が無い等)は **作らずに
    anomaly として記録**する。
  - 生成後に「頁のISBNが減っていないか」「検出器がまだ鳴るか」を確認し、
    駄目なら seed を捨てて anomaly に落とす(呼び出し側の verify で行う)。
"""
import io
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(__file__))
import canon  # noqa: E402

# NDL で版元を直接確認済みのレーベル(本セッションの照会結果)。これ以外は推測しない。
IMPRINT_PUB = {
    "少年サンデーコミックス": "小学館", "サンデーコミックス": "秋田書店",
    "SUNDAY COMICS": "秋田書店", "少年チャンピオン・コミックス": "秋田書店",
    "少年チャンピオンコミックス": "秋田書店", "少年チャンピオンコミック": "秋田書店",
    "てんとう虫コミックス": "小学館", "ジャンプ・コミックス": "集英社",
    "ジャンプコミックス": "集英社", "マーガレットコミックス": "集英社",
    "マーガレット・コミックス": "集英社", "サン・コミックス": "朝日ソノラマ",
    "サンコミックス": "朝日ソノラマ", "SUN COMICS": "朝日ソノラマ",
    "パワァコミックス": "双葉社", "アクション・コミックス": "双葉社",
    "アクションコミックス": "双葉社", "ACTION COMICS": "双葉社",
    "Comic mate": "若木書房", "COMIC MATE": "若木書房", "コミック・メイト": "若木書房",
    "虫コミックス": "虫プロ商事", "MUSHI COMICS": "虫プロ商事",
    "講談社コミックス": "講談社", "KCスペシャル": "講談社", "KCDX": "講談社",
    "ワイドKC": "講談社", "ワイドKCボンボン": "講談社", "講談社漫画文庫": "講談社",
    "秋田文庫": "秋田書店", "秋田漫画文庫": "秋田書店", "小学館文庫": "小学館",
    "集英社文庫": "集英社", "集英社漫画文庫": "集英社", "白泉社文庫": "白泉社",
    "花とゆめコミックス": "白泉社", "りぼんマスコットコミックス": "集英社",
    "ビッグコミックス": "小学館", "プリンセス・コミックス": "秋田書店",
    "プリンセスコミックス": "秋田書店", "芳文社コミックス": "芳文社",
    "ヒット・コミックス": "少年画報社", "キング・コミックス": "少年画報社",
    "ホーム・コミックス": "汐文社", "ゴールデン・コミックス": "小学館",
    "コンパクト・コミックス": "集英社", "コンパクトコミックス": "集英社",
    "手塚治虫漫画全集": "講談社", "手塚治虫文庫全集": "講談社",
}

# 掲載対象外(コンビニ本・アニメ版)。タブとして起こさない。
SKIP_IMPRINT = ("My first big", "My first wide", "My first Big", "ジャンプremix",
                "Shueisha jump remix", "アニメ版", "コンビニ")


def _norm(s):
    return (s or "").strip()


_SLUG2FILE = None


def src_path(slug):
    """公開slug → 本番ymlのパス。
    ★ファイル名は SRC stem で、公開slug(yml内の slug: フィールド)とは違うことがある
      (slug衝突の -姓+西暦 suffix 等)。検出器が出すのは公開slugなので必ず引き直す。"""
    global _SLUG2FILE
    direct = os.path.join(canon.ROOT, "data", "manga.v2", slug + ".yml")
    if os.path.exists(direct):
        return direct, slug
    if _SLUG2FILE is None:
        import glob as _g
        import re as _re
        _SLUG2FILE = {}
        pat = _re.compile(r"(?m)^slug:\s*(\S+)\s*$")
        for f in _g.glob(os.path.join(canon.ROOT, "data", "manga.v2", "*.yml")):
            try:
                head = io.open(f, encoding="utf-8").read(400)
            except Exception:
                continue
            m = pat.search(head)
            if m:
                _SLUG2FILE[m.group(1)] = f
    f = _SLUG2FILE.get(slug)
    return (f, os.path.basename(f)[:-4]) if f else (None, None)


def editions_of(slug):
    """本番頁のISBNと題から種2 sid を引き、その全 edition を返す。"""
    import yaml
    p, stem = src_path(slug)
    if not p:
        return None, []
    with io.open(p, encoding="utf-8") as f:
        page = yaml.safe_load(f)
    page["_stem"] = stem
    isbns, sids = [], set()
    for e in page.get("editions") or []:
        for v in e.get("volumes") or []:
            if v.get("isbn13"):
                isbns.append(v["isbn13"])
    for i in isbns[:80]:
        for r in canon._db.execute(
                "SELECT e.series_id FROM volumes v JOIN editions e ON e.id=v.edition_id "
                "WHERE v.isbn13=?", (i,)).fetchall():
            sids.add(r[0])
    for r in canon._db.execute("SELECT id FROM series WHERE title=?",
                               (page.get("title"),)).fetchall():
        sids.add(r[0])
    eds = []
    for sid in sorted(sids):
        for e in canon._db.execute("SELECT * FROM editions WHERE series_id=?",
                                   (sid,)).fetchall():
            vs = canon.rows(e["id"])
            if vs:
                eds.append((e["id"], e["type"], _norm(e["imprint"]), vs))
    return page, eds


def _span(vs):
    ds = sorted(d for _, _, d, _ in vs if d)
    return (ds[0] if ds else None, ds[-1] if ds else None)


def _regress_years(vs):
    """巻番号順に並べたとき最大何年逆行するか。"""
    seq = [(n, d) for n, _, d, _ in vs if d]
    seq.sort(key=lambda x: x[0])
    worst, peak = 0, ""
    for n, d in seq:
        if d < peak:
            try:
                worst = max(worst, int(peak[:4]) - int(d[:4]))
            except ValueError:
                pass
        peak = max(peak, d)
    return worst


def merge_runs(eds):
    """同じ imprint の edition を束ねる(sid分裂/表記ゆらぎの吸収)。
    ★ただし巻番号が重なる相手とは束ねない。同じレーベル名でも刊行年の違う別セットが
      あり(講談社漫画文庫の1990年代版と2001年版など)、束ねると dedup が実在の巻を
      潰してISBNごと消える(2026-08-17 愛と誠ほか14頁で実踏)。"""
    buckets = []
    for eid, etype, imp, vs in eds:
        if any(s.lower() in (imp or "").lower() for s in SKIP_IMPRINT):
            continue
        nums = {n for n, _, _, _ in vs}
        placed = False
        for b in buckets:
            if b["type"] == etype and b["imp"] == imp and not (b["nums"] & nums):
                b["vs"] += vs
                b["nums"] |= nums
                placed = True
                break
        if not placed:
            buckets.append(dict(type=etype, imp=imp, vs=list(vs), nums=set(nums),
                                seq=len(buckets)))
    # ★1つの edition の中に年代の違う2つのrunが同居していることがある
    #   (小学館文庫の1978年版と1999年版など)。巻番号順に5年以上逆行するrunは
    #   発売日のギャップ(8年超)で切り分ける。切れないものは触らず、後段の検証で弾く。
    split = []
    for b in buckets:
        vs = canon.dedup(b["vs"])
        if _regress_years(vs) >= 5:
            ds = sorted({d for _, _, d, _ in vs if d})
            cut = None
            for a, z in zip(ds, ds[1:]):
                try:
                    if int(z[:4]) - int(a[:4]) > 8:
                        cut = z
                        break
                except ValueError:
                    pass
            if cut:
                early = [v for v in b["vs"] if (v[2] or "0000") < cut]
                late = [v for v in b["vs"] if (v[2] or "0000") >= cut]
                if early and late:
                    split.append(dict(b, vs=early))
                    split.append(dict(b, vs=late))
                    continue
        split.append(b)
    buckets = split
    out = []
    seen_label = collections.Counter()
    for b in buckets:
        lab = b["imp"] or ""
        seen_label[lab] += 1
        # 同名タブが複数になる時は年で区別できるようにする
        suffix = ""
        if seen_label[lab] > 1 or any(o is not b and o["imp"] == b["imp"] and o["type"] == b["type"]
                                      for o in buckets):
            ds = sorted(d for _, _, d, _ in b["vs"] if d)
            if ds:
                suffix = "(%s)" % ds[0][:4]
        out.append((b["type"], b["imp"], canon.dedup(b["vs"]), suffix))
    return out


def pick_main(runs):
    """主版を選ぶ。standard の中で『巻数が最も多いもの』、同数圏(8割以上)なら最も古いもの。
    決め手が無ければ None を返して呼び出し側に anomaly を積ませる。"""
    cand = [r for r in runs if r[0] in ("standard", "aizoban")]
    if not cand:
        return None
    mx = max(len(r[2]) for r in cand)
    # ★max(2, ...) にすると全runが1冊の頁で候補ゼロになる(実踏)。閾値は mx を超えない。
    near = [r for r in cand if len(r[2]) >= min(mx, max(2, mx * 0.8))]
    if not near:
        near = cand
    def first_date(r):
        d = [x[2] for x in r[2] if x[2]]
        return min(d) if d else "9999"
    near.sort(key=lambda r: (first_date(r), -len(r[2])))
    return near[0]


def build(slug, dry=False):
    """1頁分の canonical を組み立てる。返り値 (ok, msg)。"""
    page, eds = editions_of(slug)
    if page is None:
        return False, "本番ymlが無い"
    # ★連載中(直近18ヶ月に新刊が出ている)頁に canonical を当てると巻が固定され、
    #   続刊が二度と出なくなる。触らずに記録に回す(キン肉マンで実証した罠)。
    alld = [d for e in eds for _, _, d, _ in e[3] if d]
    if alld and max(alld) >= "2025-02":
        return False, "連載中の可能性(最新巻 %s)=canonicalは巻を固定するので触らない" % max(alld)
    runs = merge_runs(eds)
    if len(runs) < 2:
        return False, "種2のrunが1本以下(頁の混線が種2起因でない=別seedが作っている)"
    main = pick_main(runs)
    if main is None:
        return False, "standard run が無い"
    if _regress_years(main[2]) >= 5:
        return False, "主版候補の中で既に%d年逆行(1 edition内が混成=要人手)" % _regress_years(main[2])

    def spec(r, is_main):
        nums = [n for n, _, _, _ in r[2]]
        broken = len(set(nums)) < len(nums) * 0.6 or (len(nums) > 2 and max(nums) == min(nums))
        pub = IMPRINT_PUB.get(r[1]) or canon.pub_of([i for _, i, _, _ in r[2] if i]) or "不明"
        d = dict(rows=r[2], publisher=pub, imprint=r[1] or None, renum=broken)
        return d

    others = [r for r in runs if r is not main]
    # 版タブが多すぎる頁は人の目が要る
    if len(others) > 12:
        return False, "版が%d本(多すぎ=要人手)" % (len(others) + 1)

    src = ("ギャラ型是正 2026-08-17(一括): 頁の版タブに複数の版(run)が畳み込まれて発売日が逆行していた。"
           "種2(MADB)が edition として持っている版の区切りをそのまま使って版タブに戻し、"
           "巻数が最も多く最も古い run を主版に据えた。版元はISBN出版者記号(本番から学習した記号表)と"
           "NDLで確認済みのレーベル対応から解決し、どちらでも引けない run は「不明」と明示している。"
           "巻番号がMADB側で潰れている run は発売日→ISBN順に採番し直した。情報は追加していない。")

    ms = spec(main, True)
    xs = []
    for r in others:
        s = spec(r, False)
        s["label"] = (r[1] or ("%s版" % r[0])) + (r[3] if len(r) > 3 else "")
        s["type"] = r[0] if r[0] != "standard" else "shinsoban"
        xs.append(s)
    if dry:
        return True, "main=%s(%d冊/%s) extras=%d" % (main[1], len(main[2]), ms["publisher"], len(xs))
    # ★edition-canonical のキーは **SRC slug**(ファイル名)。公開slugで書くと効かない。
    _write(page["_stem"], ms, xs, src)
    return True, "main=%s(%d冊/%s) extras=%d" % (main[1], len(main[2]), ms["publisher"], len(xs))


def _write(slug, ms, xs, src):
    """slug は必ず SRC stem(data/manga.v2 のファイル名)を渡すこと。"""
    def emit(rows, ind, renum):
        rs = canon.renum(rows) if renum else rows
        return canon._emit(rs, ind)
    head = ["slug: %s" % slug, "canonical_label: 通常版",
            "canonical_publisher: %s" % ms["publisher"]]
    if ms["imprint"]:
        head.append("canonical_imprint: %s" % ms["imprint"])
    sup = sorted({x["type"] for x in xs if x["type"] in ("bunkobon", "deluxe", "wideban")})
    if sup:
        head.append("suppress_types:")
        head += ["- %s" % s for s in sup]
    head.append("source: '%s'" % src.replace("'", "''"))
    body = ["volumes:", emit(ms["rows"], "", ms["renum"])]
    if xs:
        body.append("extra_editions:")
        for x in xs:
            body.append("- type: %s" % x["type"])
            body.append("  label: %s" % x["label"])
            if x["imprint"]:
                body.append("  imprint: %s" % x["imprint"])
            body.append("  publisher: %s" % x["publisher"])
            body.append("  volumes:")
            body.append(emit(x["rows"], "  ", x["renum"]))
    io.open(os.path.join(canon.CANON_DIR, slug + ".yml"), "w",
            encoding="utf-8", newline="\n").write("\n".join(head + body) + "\n")
