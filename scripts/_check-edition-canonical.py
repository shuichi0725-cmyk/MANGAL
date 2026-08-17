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

使い方: python scripts/_check-edition-canonical.py   (異常があれば終了コード1)
"""
import io
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "data" / "seeds" / "edition-canonical"
SRC_DIR = ROOT / "data" / "manga.v2"


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
