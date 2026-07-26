"""★出版社誤り監査: 「ISBN出版者記号」と当方の出版社が食い違う頁を検出(外部照会ゼロ)。

背景(2026-07-26 ユーザ提供のMADB生RDF M1115029 で発覚):
  MADB raw は `schema:publisher: ["一迅社", "[頒布]講談社"]` と **発行元と頒布元を
  role prefix で区別**しているが、 clean-madb-seed.ts の `stripLeadingRolePrefix` が
  `[頒布]`/`[発売]` を除去するため区別が消える。 promote の `_ISBN2PUB` は
  **配列の先頭**を採るだけなので、頒布元(講談社)が出版社として採用され得る。
  実例: 隣人のお兄さん。 ISBN 9784758099608(=978-4-**7580**=一迅社) なのに 講談社 表示。

判定: ★**ISBN出版者記号は不変の事実**なので外部照会は要らない。
  ①単一出版社のISBNから「出版者記号 × **発売年** → 出版社」の多数決表を作る(自己教師)
  ②各版の出版社が、その巻のISBN記号が**その年に名乗っていた社名**と食い違うものを flag
  ★年別にするのが肝(2026-07-26 ユーザ指摘「名前が変わった時期で判断できないかな?」):
    publisherは**版ごとの当時社名**が正([[publisher_model_edition_level]])。年を見ないと
    「角川グループパブリッシング(2013年まで)→KADOKAWA」の社名変遷を全部誤りに数えてしまう
    (実測642件の偽陽性)。 記号40486 は 2010=角川グループパブリッシング / 2013+=KADOKAWA と
    データ自身が変更時期を語る。
出力: docs/production-diagnostics/publisher-vs-isbn.tsv (read-only)

usage: python scripts/_audit-publisher-vs-isbn.py
"""
import collections
import glob
import json
import re
import sys
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
META = ROOT / ".cache" / "madb" / "metadata101-clean.json"
SRC = ROOT / "data" / "manga.v2"
OUT = ROOT / "docs" / "production-diagnostics" / "publisher-vs-isbn.tsv"
try:
    from yaml import CSafeLoader as L
except ImportError:
    L = yaml.SafeLoader


def to13(s):
    d = re.sub(r"[^0-9Xx]", "", str(s or ""))
    if len(d) == 13:
        return d
    if len(d) == 10:
        core = "978" + d[:9]
        c = (10 - sum(int(x) * (1 if i % 2 == 0 else 3) for i, x in enumerate(core)) % 10) % 10
        return core + str(c)
    return None


def prefixes(isbn13):
    """出版者記号の候補(978-4-XXXX..)。 桁数不定なので 2..7桁を全部見る。"""
    body = isbn13[3:]          # 4XXXXXXXXX
    return [body[1:1 + n] for n in (2, 3, 4, 5, 6, 7)]


def main():
    print("[1/4] metadata101-clean から ISBN→出版社リスト ...", flush=True)
    import ijson
    isbn_pubs = {}
    isbn_year = {}
    n = 0
    with META.open("rb") as f:
        for rec in ijson.items(f, "@graph.item"):
            n += 1
            if n % 100000 == 0:
                print(f"    ...{n:,}", flush=True)
            p = rec.get("schema:publisher")
            i = to13(rec.get("schema:isbn"))
            if not p or not i:
                continue
            ps = [p] if isinstance(p, str) else [x for x in p if isinstance(x, str)]
            ps = [x.strip() for x in ps if x and x.strip()]
            if ps:
                isbn_pubs[i] = ps
                dt = str(rec.get("schema:datePublished") or "")
                if len(dt) >= 4 and dt[:4].isdigit():
                    isbn_year[i] = dt[:4]
    print(f"  ISBN {len(isbn_pubs):,} / 複数出版社 {sum(1 for v in isbn_pubs.values() if len(v) > 1):,}", flush=True)

    print("[2/4] 出版者記号→出版社 の多数決表(単一出版社ISBNだけで学習) ...", flush=True)
    votes = collections.defaultdict(collections.Counter)      # (prefix, year) -> Counter
    allv = collections.defaultdict(collections.Counter)       # prefix -> Counter(年不問)
    for ib, ps in isbn_pubs.items():
        if len(ps) != 1 or not ib.startswith("9784"):
            continue
        y = isbn_year.get(ib)
        for pf in prefixes(ib):
            allv[pf][ps[0]] += 1
            if y:
                votes[(pf, y)][ps[0]] += 1
    # ★記号表は「票数」だけで採否を決め、**比率はここで切らない**。
    #   (比率0.9で切ると 4-8342[ホーム社126/集英社54=0.70] が未学習になり、
    #    短い記号 4-83.. にフォールバックして **芳文社** に化けた = 142版の偽検出。
    #    ISBNの短い記号は「同じ出版社の上位区分」ではなく別社と共有する帯なので、
    #    ★桁をまたぐフォールバックをしてはいけない。 2026-07-26)
    table, ytable, ratio = {}, {}, {}
    for pf, c in allv.items():
        top, cnt = c.most_common(1)[0]
        tot = sum(c.values())
        if tot >= 8:
            table[pf] = top
            ratio[pf] = cnt / tot
    for (pf, y), c in votes.items():
        top, cnt = c.most_common(1)[0]
        if sum(c.values()) >= 3 and cnt / sum(c.values()) >= 0.8:
            ytable[(pf, y)] = top
    # ★年別表は疎なので「その年に**在効**だった社名」を引けるようにする:
    #   prefix ごとに年を並べ、対象年**以下で最も近い年**の社名を採る。
    #   (該当年が無い時に年不問の多数決へ落ちると、改称後の名前が古い巻に付く
    #    = 角川グループパブリッシング2012刊が KADOKAWA 扱いになる 2026-07-26)
    yseries = collections.defaultdict(list)
    for (pf, y), nm in ytable.items():
        yseries[pf].append((y, nm))
    for pf in list(yseries):
        yseries[pf].sort()
        # ★年別を使うのは **実際に社名が変わった記号だけ**。 変わっていない記号で
        #   疎な年別に頼ると、票の薄い年のノイズを拾って偽陽性が増える
        #   (2026-07-26 実測: 全記号に年別を当てたら B型が62→152に悪化した)。
        if len({nm for _, nm in yseries[pf]}) < 2:
            del yseries[pf]
    print(f"  記号表 {len(table):,} / ★記号×年 表 {len(ytable):,}", flush=True)

    def implied(ib, year=None):
        """★同じ年に その記号が名乗っていた社名 を優先(社名変遷を誤検出しない)。"""
        # ★記号は**長いものから**見る。 同じ記号で「年別→年不問」の順に引く。
        #   (短い記号の年別entryが長い記号より先に当たると別社に化ける
        #    = 2026-07-26 実測で 一迅社→スクエニ 333件等の偽陽性が出た)
        # ★**最長の有効記号だけ**を使う(短い記号へ降りない)。 その記号が割れている
        #   (majority<0.6)なら判定不能として None を返す = 誤検出より取りこぼしを選ぶ。
        for pf in sorted(prefixes(ib), key=len, reverse=True):
            if pf not in table:
                continue
            if ratio.get(pf, 0) < 0.6:
                return None, None
            # ★年別は「その年のデータが在る時だけ」使う。 疎な年別で近傍補間すると
            #   票の薄い年のノイズを拾って偽陽性が増える(2026-07-26 実測: 1,528→1,615に悪化)。
            #   無い年は年不問の多数決(頑健)に委ねる。
            if year and (pf, year) in ytable:
                return ytable[(pf, year)], pf
            return table[pf], pf
        return None, None

    print("[3/4] 本番頁を走査 ...", flush=True)
    rows = []
    n = 0
    for p in glob.glob(str(SRC / "*.yml")):
        n += 1
        if n % 20000 == 0:
            print(f"    ...{n:,}", flush=True)
        try:
            d = yaml.load(open(p, encoding="utf-8"), Loader=L)
        except Exception:
            continue
        if not d:
            continue
        for ed in (d.get("editions") or []):
            pub = (ed.get("publisher") or "").strip()
            ibs = [v.get("isbn13") for v in (ed.get("volumes") or []) if v.get("isbn13")]
            if not pub or not ibs:
                continue
            # ★判定年 = **版の開始年**(最古の巻の発売年)。 publisher は版に1つしか持てず、
            #   改称を跨いで刊行された版(角川グループパブリッシング2012-2015 等)は
            #   「版の開始時点の当時社名」が正([[publisher_model_edition_level]])。
            #   巻ごとの年で見ると改称跨ぎの版を全部誤りに数えてしまう
            #   (2026-07-26 実測: 518版中447は全巻が改称前=当方が正、71版が跨ぎ)。
            _ys = [str(v.get("release_date") or "")[:4] for v in (ed.get("volumes") or [])]
            _ys = sorted(y for y in _ys if y.isdigit())
            _edy = _ys[0] if _ys else None
            imp = collections.Counter()
            for ib in ibs:
                w, pf = implied(str(ib), _edy)
                if w:
                    imp[w] += 1
            if not imp:
                continue
            want, cnt = imp.most_common(1)[0]
            if want == pub or cnt < max(1, len(ibs) // 2):
                continue
            cand = isbn_pubs.get(str(ibs[0]), [])
            rows.append((d.get("slug"), d.get("title"), pub, want,
                         " / ".join(cand), str(len(ibs)), str(ibs[0])))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        f.write("slug\ttitle\tours\tisbn_implies\tmadb_candidates\tvols\tisbn\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    print(f"\n[4/4] === 出版社がISBN出版者記号と食い違う版 ===")
    print(f"  ★{len(rows):,} 件 → {OUT}")
    c = collections.Counter((r[2], r[3]) for r in rows)
    for (a, b), v in c.most_common(12):
        print(f"   {v:5,}  当方={a[:16]:18s} → ISBN記号={b[:16]}")


if __name__ == "__main__":
    main()
