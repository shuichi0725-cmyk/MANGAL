# -*- coding: utf-8 -*-
"""日次蒸留のpreview入れ替え(2026-08-11 ユーザ裁定「追加ではなく何も言わないでも入れ替え」)。

前回までの日次ドラフトが .preview-data に溜まったまま新バッチを足すと、ユーザは
「前回見た物」と「今回の新規」を区別できない。毎回の日次蒸留の冒頭でこれを走らせ、
**過去ドラフトをpreviewから退場**させてから今回分を生成する(=preview は常に「今回のみ」)。

退場条件(3条件AND=誤削除の三重ガード):
  ① .cache/preorders/drafts/ に居る(=日次蒸留が作ったドラフトである。手作業頁/サンプル頁は触らない)
  ② data/seeds/preorder-pages/ に居ない(=本番化済みドラフトは preview 掲示を維持)
  ③ data/manga.v2/ に居ない(=本番昇格済み頁のpreviewコピーは反映フローの管轄=触らない)
★ドラフト台帳(.cache/preorders/drafts/)自体は消さない=incrementの過去draft除外網はそのまま生きる。
★索引はここでは組み直さない(runbook手順11が毎回やる)。

使い方:
  python scripts/_preorder-preview-swap.py --list   # 退場対象の確認のみ
  python scripts/_preorder-preview-swap.py          # 実行(削除+件数報告)
"""
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def stems(pattern):
    return {os.path.basename(p)[:-4] for p in glob.glob(pattern)}


def main():
    dry = "--list" in sys.argv
    drafts = stems(f"{ROOT}/.cache/preorders/drafts/*.yml")
    productionized = stems(f"{ROOT}/data/seeds/preorder-pages/*.yml")
    prod = stems(f"{ROOT}/data/manga.v2/*.yml")
    preview = sorted(stems(f"{ROOT}/.preview-data/manga/*.yml"))
    out = [s for s in preview if s in drafts and s not in productionized and s not in prod]
    keep = len(preview) - len(out)
    print(f"preview {len(preview)}頁: 過去ドラフト退場対象 {len(out)} / 残置 {keep}")
    for s in out:
        if dry:
            print(f"  [list] {s}")
        else:
            os.remove(f"{ROOT}/.preview-data/manga/{s}.yml")
    if not dry and out:
        print("削除済み。★手順11の索引再構築(.preview-data)を忘れずに(このscriptは索引を触らない)")


if __name__ == "__main__":
    main()
