#!/usr/bin/env python3
"""源(SRC)なし manga.v2 頁の検出 (= 2026-09-17 新設 / 月次サニティ #34)。

★なぜ要るか:
  promote の頁producerは **2つだけ** =
    ① data/manga/*.yml(合成ソース) + data/seeds/source-pages/*.yml の src ループ
    ② data/seeds/preorder-pages/*.yml
  フルpromoteは冒頭で data/manga.v2/*.yml を**全削除**してから作り直すので、
  どちらにも源が無い頁は **次の月次で黙って消える**。しかも本番索引には載っている
  = 公開中の頁がある日いきなり404になる。 [[orphan_source_pages_restored]]

  実績: 2026-08-26 に258件を復元 → 2026-09-14 に414件で再発 → 2026-09-17 に400件を復元。
  「復元しても頁化フローの永続化漏れでまた増える」ので、**件数を月次で監視**する。

  ★根因の多くは「src頁を作ったのに `.cache/apply/key2slug.tsv` に登録し忘れ」
  ([[new_page_creation_srcpage_key2slug]])。 実測 2026-09-17: 400件中398件が未登録だった。

出力: stdout(件数+一覧の先頭) / docs/production-diagnostics/orphan-source-pages.tsv
終了コード: 0(検出は報告のみ。 復元は per-case 判断 = 過merge/重複頁を生む _skey があるため)
"""
import glob
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "production-diagnostics" / "orphan-source-pages.tsv"


def stems(pat: str) -> set[str]:
    return {os.path.basename(p)[:-4] for p in glob.glob(str(ROOT / pat))}


def main() -> int:
    v2 = stems("data/manga.v2/*.yml")
    src = stems("data/manga/*.yml")
    sp = stems("data/seeds/source-pages/*.yml")
    pp = stems("data/seeds/preorder-pages/*.yml")
    orphan = sorted(v2 - src - sp - pp)

    # 索引に載っているか(= 公開中か)。 索引が無ければ判定を省く。
    inidx: set[str] = set()
    idx_p = ROOT / "data" / "manga-list-index.json"
    if idx_p.exists():
        idx = json.load(io.open(idx_p, encoding="utf-8"))
        si = idx["f"].index("slug")
        inidx = {r[si] for r in idx["d"]}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fo:
        fo.write("stem\t公開slug\ttitle\t索引\n")
        for s in orphan:
            slug = title = ""
            try:
                for ln in io.open(ROOT / "data" / "manga.v2" / f"{s}.yml", encoding="utf-8"):
                    if ln.startswith("slug:"):
                        slug = ln.split(":", 1)[1].strip()
                    elif ln.startswith("title:"):
                        title = ln.split(":", 1)[1].strip()
                    if slug and title:
                        break
            except OSError:
                pass
            fo.write(f"{s}\t{slug}\t{title}\t{'有' if slug in inidx else '無'}\n")

    print(f"manga.v2 {len(v2):,} / SRC {len(src):,} / source-pages {len(sp):,} / preorder-pages {len(pp):,}")
    print(f"★源なし頁(次のフルpromoteで消える): {len(orphan):,}")
    for s in orphan[:20]:
        print(f"   {s}")
    if len(orphan) > 20:
        print(f"   … 他 {len(orphan)-20:,}件")
    print(f"→ {OUT}")
    if orphan:
        print("  ★復元 = manga.v2 から最小の源stubを source-pages に作る(_skey は頁ISBNの種2逆引き多数決)。")
        print("    ただし _skey が親シリーズを指すと **別の生きた頁と重複**するので、復元後に必ず同値確認する。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
