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

使い方: python scripts/_check-edition-canonical.py   (異常があれば終了コード1)
"""
import io
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "data" / "seeds" / "edition-canonical"
SRC_DIR = ROOT / "data" / "manga.v2"
SUPP = ROOT / "data" / "seeds" / "volumes-supplement.yml"


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
    files = sorted(SEED_DIR.glob("*.yml"))
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
                if miss:
                    problems.append(
                        "種4(取込もれ巻)がseedに入っていない %s = canonicalが上書きして頁から消す"
                        % sorted(miss)[:6])
            for i, xe in enumerate(seed.get("extra_editions") or []):
                check_volumes("extra_editions[%d](%s)" % (i, xe.get("label")),
                              xe.get("volumes"), problems)
        if problems:
            print("NG %s" % p.name)
            for m in problems:
                print("   " + m)
            bad += 1
    print("\nedition-canonical: %d 本 / 異常 %d 本" % (len(files), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
