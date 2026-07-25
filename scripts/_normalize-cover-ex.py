"""本番/preview の書影URLの `_ex` サイズ指定を一律 300x300 に正規化(冪等・再実行可)。

★背景(2026-07-25 実測): 楽天サムネは「1枚のマスター + `_ex` サイズ指定」で、APIが返す
  `largeImageUrl`(= `_ex=200x200`) は**最大ではない**。 `_ex` を上げるとマスター原寸まで返る。
    新刊 141x200(200) → 211x300(300) → 352x500(500) → 705x1000(原寸)
    古書(来るべき世界2巻)はマスターが160x227しかなく300でも打ち止め = **容量も増えない**
  容量は本番20枚実測で 13.9KB → 23.3KB(1.68倍)。 ★書影は楽天CDN直リンクなので R2課金には無影響。

恒久化は各生成器側(`_promote-bulk-v2._norm_cover_ex` / `_gen-corner-stocks` /
`_build-anime-season-view` / `lib/coverSlim.ts`)で済ませてあり、本scriptは
**既に焼かれている頁**を揃えるための一括パス(promoteを回さずに反映できる)。

usage: python scripts/_normalize-cover-ex.py [--ex 300x300] [--dry] [--dir data/manga.v2 ...]
"""
import glob
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIRS = ["data/manga.v2", ".preview-data/manga", "data/art-books.v2"]
RK = "https://thumbnail.image.rakuten.co.jp/"


def main():
    ex = "300x300"
    if "--ex" in sys.argv:
        ex = sys.argv[sys.argv.index("--ex") + 1]
    dry = "--dry" in sys.argv
    dirs = []
    if "--dir" in sys.argv:
        i = sys.argv.index("--dir") + 1
        while i < len(sys.argv) and not sys.argv[i].startswith("--"):
            dirs.append(sys.argv[i]); i += 1
    dirs = dirs or DEFAULT_DIRS

    # 楽天サムネURLに付く ?_ex=NxN のみ差し替え(他ホスト・他クエリは触らない)
    pat = re.compile(r"(https://thumbnail\.image\.rakuten\.co\.jp/\S*?)\?_ex=\d+x\d+")
    bare = re.compile(r"(https://thumbnail\.image\.rakuten\.co\.jp/[^\s\"']+\.(?:jpg|gif|png))(?![?\w])")
    total_f = touched_f = total_u = 0
    for d in dirs:
        p = ROOT / d
        if not p.is_dir():
            print(f"  (skip) {d} 無し")
            continue
        n = t = u = 0
        for f in glob.glob(str(p / "*.yml")):
            n += 1
            if n % 20000 == 0:
                print(f"    ...{n:,}", flush=True)
            raw = open(f, encoding="utf-8").read()
            if RK not in raw:
                continue
            new, c1 = pat.subn(rf"\1?_ex={ex}", raw)
            new, c2 = bare.subn(rf"\1?_ex={ex}", new)   # _ex無し(原寸)も明示して揃える
            if c1 + c2 and new != raw:
                u += c1 + c2
                t += 1
                if not dry:
                    open(f, "w", encoding="utf-8").write(new)
        print(f"  {d}: {n:,}頁 / 書換 {t:,}頁 {u:,}URL")
        total_f += n; touched_f += t; total_u += u
    print(f"\n{'(dry-run) ' if dry else ''}★合計 {total_f:,}頁 走査 / {touched_f:,}頁 {total_u:,}URL を _ex={ex} に統一")


if __name__ == "__main__":
    main()
