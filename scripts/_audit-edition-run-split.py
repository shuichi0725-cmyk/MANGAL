# -*- coding: utf-8 -*-
"""同一の刊行runが版タブに割れている頁の検出(名前に依存しない構造シグナル。2026-08-28 新設)。

★`_audit-canonical-imprint-split.py` は imprint 文字列の近さで探すため、
  **英字レーベル名 vs 和名**(SHONEN SUNDAY COMICS WIDE EDITION ⇔ 少年サンデーコミックスワイド版)や
  **略称 vs 正式名**(KCスペシャル ⇔ 講談社コミックススペシャル)を取り逃す。
  ARMS のワイド版がまさにそれで、5-8巻だけが英字名の別版に落ちていた(2026-08-28 ユーザ発見)。

判定(名前を一切見ない):
  同一頁の2版が
   ①出版社が一致(またはISBN出版者記号が共通) ②巻番号が重複しない
     ★②の重複判定は **ISBNを持つ巻だけ**で行う(2026-08-30)。ISBN無しの幽霊巻が1つ在るだけで
       1本のrunが「別run」と判定され、分裂が丸ごと隠れる(エロイカより愛をこめて=20巻ぶんが不可視だった)。
   ③合わせると連番になる(欠番なし) ④合わせて巻順に並べると発売日が単調増加
  を全て満たす = 1本の刊行runが2つに割れている強い疑い。
  ★新装版/復刻版は巻番号が重複するか日付が単調にならないので、この4条件でほぼ落ちる。

  tier A = imprint を正規化(NFKC/小書きカナ/記号除去/大文字化)すると一致 → ほぼ確実
  tier B = 名前は違う(英字↔和名・略称↔正式名など) → 外部裏取りしてから統合

出力: docs/production-diagnostics/edition-run-split.tsv
★自動統合は禁止。楽天seriesName(キャッシュ1パス)+MADB cm104のシリーズ容器ID+刊行リストで1件ずつ裏取りする。

  python scripts/_audit-edition-run-split.py
"""
import glob, io, os, sys, unicodedata
from collections import Counter
from itertools import combinations
import yaml
try: from yaml import CSafeLoader as L
except Exception: from yaml import SafeLoader as L

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMALL = str.maketrans("ァィゥェォッャュョヮヵヶ", "アイウエオツヤユヨワカケ")


def nk(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    for ch in " ・<>〔〕[]":
        s = s.replace(ch, "")
    return s.translate(SMALL).upper()


def main() -> None:
    rows = []
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml"))):
        try:
            d = yaml.load(io.open(p, encoding="utf-8"), Loader=L) or {}
        except Exception:
            continue
        eds = []
        for e in (d.get("editions") or []):
            vs = [v for v in (e.get("volumes") or []) if isinstance(v.get("number"), int) and v["number"] >= 1]
            if vs:
                eds.append((e, vs))
        if len(eds) < 2:
            continue
        for (a, va), (b, vb) in combinations(eds, 2):
            pa, pb = (a.get("publisher") or ""), (b.get("publisher") or "")
            ia = {(v.get("isbn13") or "")[:8] for v in va if v.get("isbn13")}
            ib = {(v.get("isbn13") or "")[:8] for v in vb if v.get("isbn13")}
            if not ((pa and pa == pb) or (ia and ib and (ia & ib))):
                continue
            # ★幽霊巻(ISBN無し)は重複判定から外す(2026-08-30 エロイカより愛をこめてで実踏)。
            #   PRINCESS COMICS側にISBN無しの「7巻」が1つ在っただけで、通常版(1-19)と
            #   PRINCESS COMICS(20-39)という**全39巻の1本のrun**が「巻番号が重複=別run」と
            #   判定され、20巻ぶんの分裂が丸ごと見えなくなっていた。
            #   promote の種4マージも同じ考え方(ISBNの無い行は番号を占有しない)。
            iso_a = {v["number"] for v in va if v.get("isbn13")}
            iso_b = {v["number"] for v in vb if v.get("isbn13")}
            ghosts = [v for v in va if not v.get("isbn13") and v["number"] in iso_b] +                      [v for v in vb if not v.get("isbn13") and v["number"] in iso_a]
            va = [v for v in va if v.get("isbn13") or v["number"] not in iso_b]
            vb = [v for v in vb if v.get("isbn13") or v["number"] not in iso_a]
            if not va or not vb:
                continue
            na = [v["number"] for v in va]
            nb = [v["number"] for v in vb]
            if set(na) & set(nb):
                continue
            merged = sorted(va + vb, key=lambda v: v["number"])
            nums = [v["number"] for v in merged]
            if len(nums) < 4 or nums != list(range(min(nums), min(nums) + len(nums))):
                continue
            dates = [(v.get("release_date") or "")[:7] for v in merged]
            if sum(1 for x in dates if x) < len(dates) * 0.8:
                continue
            seq = [x for x in dates if x]
            if seq != sorted(seq):
                continue
            tier = "A" if nk(a.get("imprint")) == nk(b.get("imprint")) else "B"
            rows.append((tier, os.path.basename(p)[:-4], d.get("title") or "",
                         a.get("imprint") or "(空)", str(na), b.get("imprint") or "(空)", str(nb),
                         str([v["number"] for v in ghosts]) if ghosts else ""))
    rows.sort()
    dst = os.path.join(ROOT, "docs", "production-diagnostics", "edition-run-split.tsv")
    with io.open(dst, "w", encoding="utf-8") as f:
        f.write("tier\tslug\ttitle\timprintA\tvolsA\timprintB\tvolsB\n")
        for r in rows:
            f.write("\t".join(r) + "\n")
    print("刊行runが版タブに割れている疑い: %d ペア / %d 頁 → %s" % (len(rows), len({r[1] for r in rows}), dst))
    print("  tier:", dict(Counter(r[0] for r in rows)))


if __name__ == "__main__":
    main()
