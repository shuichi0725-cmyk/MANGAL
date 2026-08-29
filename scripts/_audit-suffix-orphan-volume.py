# -*- coding: utf-8 -*-
"""巻番号を持たない続巻が「別シリーズ」に切り出されて頁に出ない型の検出 (2026-08-29 新設)。

きっかけ: ユーザ指摘「2巻ではなくWなので抜けたと思われ」(マショウのあほすたさん)。
  2巻にあたる本の題が「マショウのあほすたさんW (ういんぐ)」で**巻番号を持たない**ため、
  種2(MADB)が別 series として切り出し(number=0・日付なし)、親頁に合流しなかった。
  結果、頁は 1巻と3巻だけになり「2巻が欠番」に見えていた。

  同じことは 続 / 新 / 完結編 / 外伝 / EX / R / Z / 零 / 真 …のような
  **短い接尾**で起きる。巻番号のパースに引っかからないので、巻抜け監査でも
  取りこぼし監査でも構造的に見えない。

判定 (= ローカルのみ。外部APIは叩かない):
  ① 種2の series のうち、**その全ISBNが本番のどの頁にも出ていない**もの(=orphan series)
  ② その title が **既存頁の title + 短い接尾**(前方一致・残り1〜8文字)になっている
  ③ 親候補と **同じ qid** または **同じ imprint** または **同じISBN出版者記号(帯)**
  ④ orphan の巻数が少ない(≤3)= 続巻1冊程度。大きいものは独立作品の可能性が高い

  ★これは「候補」であって確定ではない。**スピンオフ/別作品が正当に別頁**なことは普通にある
  (例「◯◯ 外伝」は別作品として扱うのが正しい場合がある)。必ず1件ずつ裏取りしてから
  種4(volumes-supplement)へ入れること。自動適用は禁止。

★初回(2026-08-29)の FIT_GAP 3件を全部 per-case で裏取りした結果 = **2件が本物 / 1件が偽陽性**:
  ○ mashou-no-ahosuta-san +「W(ういんぐ)」= 本物。2巻として種4に追加済
  ○ dogs-sato-2023 +「infight」= 本物。しかも裏取りで**もう1巻(dog eat dog 上)の欠落**まで判明し、
    NDLの叢書番号 81→105→135→136 で4巻構成に再構築した(canonical新設)
  ✕ hontoni-atta-kowai-hanashi +「作家編」= **偽陽性**。NDLで確認したところ
    『ほんとにあった怖い話作家編』は**著者が別人**(三原千恵利・親頁は山本まゆり)で
    叢書も別(ハロウィン少女コミック館)、自前の1〜8巻を持つ**独立した別シリーズ**だった。
    ★教訓 = 題の前方一致とISBN帯だけでは足りない。**著者の一致**を必ず確認すること
    (この検出器は著者を見ていない。TSVを裁く時に必ず人が見る)。

出力: docs/production-diagnostics/suffix-orphan-volume.tsv
是正: 親頁の続巻と確認できたら 種4 に series_keys=[親のseries_key] で追加し、
      volume_label に実際の接尾(「W(ういんぐ)」等)を入れる。

  python scripts/_audit-suffix-orphan-volume.py
"""
import io, json, os, re, sqlite3, sys, unicodedata
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, ".cache", "db-v2.sqlite")
IDX = os.path.join(ROOT, ".cache", "isbn-page-index.json")
FLAT = os.path.join(ROOT, ".cache", "volume-flat.tsv")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "suffix-orphan-volume.tsv")
MAXSUF = 8          # 接尾の最大長(これ以上長いと別作品の可能性が高い)
MAXVOL = 3          # orphan側の巻数上限

# ★接尾で**別作品/掲載対象外**と分かるもの。候補から除く(CLAUDE.mdの掲載scope・drop規則に対応)。
#   アンソロジー・傑作選・画集の類は「巻が抜けている」のではなく**そもそも載せない**もの。
#   外伝・編・season の類は**正当に別頁**でよい作品。
DROP_SUF = re.compile(
    r"アンソロジ|傑作選|傑作集|総集編|画集|原画集|ファンブック|ガイド|大全|読本|設定資料|"
    r"公式|名鑑|解体新書|大百科|大事典|攻略|年度版|カレンダ")
SPINOFF_SUF = re.compile(r"外伝|番外|スピンオフ|season|シーズン|第[0-9一二三四五六七八九十]+部")


def _d(x):
    """'YYYY' / 'YYYY-MM' / 'YYYY-MM-DD' を比較可能な 'YYYY-MM' に丸める(空は None)。"""
    x = str(x or "")
    return x[:7] if len(x) >= 7 else (x[:4] + "-00" if len(x) >= 4 else None)


def nm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return re.sub(r"[\s　・･!！?？:：〜~ー\-。、．.「」『』()（）\[\]【】,，/／]", "", s)


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    idx = json.load(io.open(IDX, encoding="utf-8"))

    # 本番の頁: 正規化titleと、その頁が持つISBN帯/imprint
    page_title, page_band, page_impr, page_nums = {}, defaultdict(set), defaultdict(set), defaultdict(set)
    page_vdate = defaultdict(dict)          # slug -> {巻番号: 発売日}
    page_isbn = defaultdict(dict)           # slug -> {巻番号: isbn13}
    with io.open(FLAT, encoding="utf-8") as f:
        h = next(f).rstrip("\n").split("\t")
        SL, TI, IB, EI, NU, RD = (h.index(x) for x in
                                  ("slug", "title", "isbn13", "ed_imprint", "number", "release_date"))
        for line in f:
            c = line.rstrip("\n").split("\t")
            page_title[c[SL]] = c[TI]
            if c[IB]:
                page_band[c[SL]].add(c[IB][:8])
            if c[EI]:
                page_impr[c[SL]].add(c[EI])
            if c[NU].isdigit():
                page_nums[c[SL]].add(int(c[NU]))
                if c[RD]:
                    page_vdate[c[SL]][int(c[NU])] = c[RD]
                if c[IB]:
                    page_isbn[c[SL]][int(c[NU])] = c[IB]
    by_ntitle = defaultdict(list)
    for slug, t in page_title.items():
        by_ntitle[nm(t)].append(slug)
    print("本番頁 %d / 正規化題 %d" % (len(page_title), len(by_ntitle)), flush=True)

    # 種2の series → 巻・imprint・qid
    rows = cur.execute("""
        SELECT s.id, s.series_key, s.title, s.qid, e.imprint,
               v.number, v.isbn13, v.release_date
        FROM series s JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
    """).fetchall()
    ser = defaultdict(lambda: {"key": "", "title": "", "qid": None, "impr": set(), "vols": []})
    for sid, key, title, qid, impr, num, isbn, rd in rows:
        d = ser[sid]
        d["key"], d["title"], d["qid"] = key, title, qid
        if impr:
            d["impr"].add(impr)
        d["vols"].append((num, isbn, rd))
    print("種2 series %d" % len(ser), flush=True)

    out = []
    for sid, d in ser.items():
        vols = d["vols"]
        if not vols or len(vols) > MAXVOL:
            continue
        isbns = [i for _, i, _ in vols if i]
        if not isbns:
            continue
        if any(idx.get(i) for i in isbns):
            continue                                   # 本番に出ている = orphanでない
        nt = nm(d["title"])
        # 前方一致する既存頁の題を探す(自分より短いもの)
        best = None
        for cand_nt, slugs in by_ntitle.items():
            if not cand_nt or cand_nt == nt or not nt.startswith(cand_nt):
                continue
            suf = nt[len(cand_nt):]
            if not (1 <= len(suf) <= MAXSUF):
                continue
            for slug in slugs:
                score = 0
                why = []
                if d["qid"] and any(d["qid"] in k for k in [slug]) :
                    pass
                bands = {i[:8] for i in isbns}
                if bands & page_band.get(slug, set()):
                    score += 2; why.append("同ISBN帯")
                if d["impr"] & page_impr.get(slug, set()):
                    score += 2; why.append("同レーベル")
                if len(cand_nt) >= 4:
                    score += 1
                gaps = [n for n in range(1, max(page_nums.get(slug) or [0]) + 1)
                        if n not in (page_nums.get(slug) or set())]
                if gaps:
                    score += 1; why.append("親に欠番%s" % gaps[:4])
                # ★FIT_GAP = マショウ型の決定的署名。
                #   orphan の発売日が「親の欠番の直前巻 < orphan < 直後巻」に収まるなら、
                #   その欠番は**まさにこの本**である可能性が非常に高い。
                _ods = [x for x in (_d(r) for _, _, r in vols) if x]
                od = min(_ods) if _ods else None
                fit = None
                if od:
                    for g in gaps:
                        prev = page_vdate.get(slug, {}).get(g - 1)
                        nxt = page_vdate.get(slug, {}).get(g + 1)
                        if prev and nxt and _d(prev) <= od <= _d(nxt):
                            fit = g; break
                # ★ISBN_FIT: 日付が無い orphan 用。同じISBN帯なら、書名記号の数値が
                #   「欠番の前巻 < orphan < 次巻」に収まるかで同じ判定ができる。
                #   マショウのあほすたさんW は種2に日付が無いのでこちらで当たる
                #   (9141-0=1巻 < 9180-9=W < 9209-7=3巻)。
                if fit is None:
                    for g in gaps:
                        pi = page_isbn.get(slug, {}).get(g - 1)
                        ni = page_isbn.get(slug, {}).get(g + 1)
                        oi = sorted(isbns)[0]
                        if pi and ni and pi[:8] == ni[:8] == oi[:8] and pi < oi < ni:
                            fit = g; why.append("★欠番%dのISBN枠に収まる" % g); break
                    if fit is not None:
                        score += 4
                else:
                    score += 4; why.append("★欠番%dの日付枠に収まる" % fit)
                if score >= 3 and (best is None or score > best[0]):
                    best = (score, slug, cand_nt, suf, why, fit)
        if best:
            score, slug, cand_nt, suf, why, fit = best
            if DROP_SUF.search(suf) or DROP_SUF.search(d["title"]):
                continue          # アンソロジー/傑作選/画集 = 巻抜けでなく掲載対象外
            if SPINOFF_SUF.search(suf):
                continue          # 外伝/番外/第N部 = 正当に別頁でよい作品
            out.append((score, "FIT_GAP" if fit is not None else "候補", slug, page_title[slug], d["title"], suf,
                        d["key"], len(vols),
                        ";".join(str(i) for _, i, _ in vols if i),
                        ";".join(str(r or "") for _, _, r in vols),
                        ",".join(sorted(d["impr"])), ",".join(why)))
    out.sort(key=lambda r: (-r[0], r[2]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("score\t親slug\t親題\torphan題\t接尾\torphan_series_key\t巻数\tISBN\t発売日\timprint\t根拠\n")
        for r in out:
            f.write("\t".join(str(x) for x in r) + "\n")
    print("接尾つきorphan続巻の候補: %d 件 → %s" % (len(out), os.path.relpath(OUT, ROOT)))
    print("★候補であって確定ではない。スピンオフ/別作品が正当に別頁なことは普通にある。1件ずつ裏取りすること。")
    for r in out[:30]:
        print("  score%-2d %-8s %-38s 『%s』 + 「%s」 | %s | %s"
              % (r[0], r[1], r[2], r[3][:20], r[5], r[9], r[11]))


if __name__ == "__main__":
    main()
