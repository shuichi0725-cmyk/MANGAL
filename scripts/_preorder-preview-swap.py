# -*- coding: utf-8 -*-
"""日次蒸留のpreview入れ替え(2026-08-11 ユーザ裁定「追加ではなく何も言わないでも入れ替え」)。

★2026-08-15 全面是正(ユーザ指摘「テスト環境に何かある場合は入れ替えるようにskillしたはず
  だけどなってない?」): 旧実装は退場条件を「日次ドラフトである(=.cache/preorders/drafts に居る)」
  かつ「data/manga.v2 に居ない」の AND にしていたため、**手作業でpreviewに入れた確認用コピーが
  1頁も退場しなかった**(2026-08-14 実害= 巻抜け仮想の確認セット155頁が残ったまま日次ドラフト102頁が
  足され、preview 257頁で「前回見た物」と「今回の新規」が混ざった)。
  裁定の趣旨は「preview は常に今回のみ」なので、**由来を問わず現在の掲示物を全部退場させる**に改める。

退場条件(2026-08-15〜):
  preview に在る全頁を退場させる。ただし以下は残す。
    A. **復元手段が無い頁**(= .cache/preorders/drafts にも data/manga.v2 にも
       data/seeds/preorder-pages にも実体が無い)。消すと二度と戻せないため安全弁として残置し警告する。
    B. **keep リストに載せた頁**(= data/seeds/preview-keep.txt に1行1slug、# でコメント)。
       「この確認セットは日次をまたいで残したい」時だけ人が明示的に積む。

★退場=preview からの掲示取り下げであって、データは消えない:
  日次ドラフトは .cache/preorders/drafts/ に台帳が残る(=increment の過去draft除外網もそのまま生きる)。
  手作業コピーは data/manga.v2 が実体。戻したい時は cp するだけ(下の復元コマンドを実行時に表示する)。
★索引はここでは組み直さない(runbook手順11が毎回やる)。

使い方:
  python scripts/_preorder-preview-swap.py --list   # 退場対象の確認のみ
  python scripts/_preorder-preview-swap.py          # 実行(削除+件数報告+復元コマンド表示)
"""
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEEP_FILE = os.path.join(ROOT, "data", "seeds", "preview-keep.txt")


def stems(pattern):
    return {os.path.basename(p)[:-4] for p in glob.glob(pattern)}


def load_keep():
    keep = set()
    if os.path.exists(KEEP_FILE):
        for ln in open(KEEP_FILE, encoding="utf-8"):
            ln = ln.split("#", 1)[0].strip()
            if ln:
                keep.add(ln)
    return keep


def main():
    dry = "--list" in sys.argv
    drafts = stems(f"{ROOT}/.cache/preorders/drafts/*.yml")
    productionized = stems(f"{ROOT}/data/seeds/preorder-pages/*.yml")
    prod = stems(f"{ROOT}/data/manga.v2/*.yml")
    keep = load_keep()
    preview = sorted(stems(f"{ROOT}/.preview-data/manga/*.yml"))

    recoverable = drafts | productionized | prod
    orphan = [s for s in preview if s not in recoverable]        # A: 復元不可=安全弁で残す
    kept = [s for s in preview if s in keep and s in recoverable]  # B: 明示keep
    out = [s for s in preview if s in recoverable and s not in keep]

    print(f"preview {len(preview)}頁: 退場 {len(out)} / keep明示 {len(kept)} / 復元不可で残置 {len(orphan)}")
    if orphan:
        print("  ★復元手段が無いため残した頁(preview限定・実体なし。要調査):")
        for s in orphan:
            print(f"     {s}")
    if kept:
        print(f"  keep({os.path.relpath(KEEP_FILE, ROOT)}): " + ", ".join(kept))

    _from_prod = [s for s in out if s in prod]
    for s in out:
        if dry:
            print(f"  [list] {s}")
        else:
            os.remove(f"{ROOT}/.preview-data/manga/{s}.yml")
    if not dry and out:
        print("削除済み。★手順11の索引再構築(.preview-data)を忘れずに(このscriptは索引を触らない)")
        if _from_prod:
            print(f"  ↩ 本番実体のある {len(_from_prod)} 頁を戻すには:")
            print("     for s in <slug...>; do cp data/manga.v2/$s.yml .preview-data/manga/; done")
            print("     (日次ドラフトは .cache/preorders/drafts/ から同様に cp)")


if __name__ == "__main__":
    main()
