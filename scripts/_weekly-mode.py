# -*- coding: utf-8 -*-
"""週次蒸留のモード判定 (= ハイブリッド週次 2026-08-27 ユーザ裁定「ハイブリッド化して」)。

marker(前回フルビルドのcode_commit)→HEAD の git diff をファイル場所で分類:
  CODE    = 漫画頁に効くコードが動いた(app/manga・app/layout・globals.css・components/・lib/・
            next.config・package.json・tailwind) → 従来のフルビルド週次(手順3〜6)
  SURFACE = 非漫画面のコードのみ(app/のその他=ホーム/shinkan/browse等) → データ週+機能蒸留
  DATA    = コード変更なし → データ週(diff-deploy --weekly-json + finalize --data-week)=数分・数千ops

  python scripts/_weekly-mode.py     # 判定+根拠ファイル+次に打つコマンドを表示。exit: 0=DATA/1=SURFACE/2=CODE
"""
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKER = os.path.join(ROOT, ".cache", "prod-deploy-marker.json")
# _deploy-differential.py の CODE_SCOPE と同一定義(片方だけ変えるな)
MANGA_CODE = ["app/manga", "app/layout.tsx", "app/globals.css", "components", "lib",
              "next.config.ts", "package.json", "tailwind.config.ts"]
SURFACE_CODE = ["app"]  # MANGA_CODE を除いた app/ 配下 = 非漫画面


def main() -> None:
    if not os.path.exists(MARKER):
        print("marker無し → 初回はフルビルド週次(CODE扱い)")
        sys.exit(2)
    mk = json.load(open(MARKER, encoding="utf-8"))
    base = mk["code_commit"]

    def diff(paths):
        r = subprocess.run(["git", "diff", "--name-only", f"{base}..HEAD", "--", *paths],
                           capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
        return [x for x in r.stdout.splitlines() if x.strip()]

    manga = diff(MANGA_CODE)
    surface = [f for f in diff(SURFACE_CODE) if f not in set(manga)
               and not f.startswith("app/manga") and f != "app/layout.tsx" and f != "app/globals.css"]
    print(f"基準: 前回フル {base[:9]} → HEAD")
    if manga:
        print(f"判定: ★CODE週(漫画頁に効くコード {len(manga)}件) → 従来フルビルド週次(手順3〜6)")
        for f in manga[:8]:
            print("   ", f)
        sys.exit(2)
    if surface:
        print(f"判定: SURFACE週(非漫画面のコードのみ {len(surface)}件) → データ週+機能蒸留:")
        for f in surface[:8]:
            print("   ", f)
        print("  1) python scripts/_deploy-differential.py --weekly-json")
        print("  2) python scripts/_deploy-feature.py")
        print("  3) python scripts/_kv-redirects-sync.py")
        print("  4) python scripts/_weekly-finalize.py --data-week")
        sys.exit(1)
    print("判定: DATA週(コード変更なし) → 差分ルート(数分・数千ops):")
    print("  1) python scripts/_deploy-differential.py --weekly-json")
    print("  2) python scripts/_kv-redirects-sync.py")
    print("  3) python scripts/_weekly-finalize.py --data-week")
    sys.exit(0)


if __name__ == "__main__":
    main()
