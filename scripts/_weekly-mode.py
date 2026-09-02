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
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKER = os.path.join(ROOT, ".cache", "prod-deploy-marker.json")
MANIFEST = os.path.join(ROOT, ".cache", "r2-manifest.json")
SHINKAN_DIR = os.path.join(ROOT, "public", "shinkan")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _r2_manifest  # noqa: E402


def shinkan_months_missing_html():
    """本番R2にHTMLが無い /shinkan 月別頁 = public/shinkan/{ym}.json は在るのに manifest に shinkan/{ym}.html が無い月。
    ★データ週(diff-deploy --weekly-json)は calendar/shinkan の JSON面だけPUTしてHTMLを建てないため、
    step1 の _gen-shinkan-data.py が「当月+3」の窓を進めて生んだ新月の頁が無いままサイトマップにだけ載る(404)
    (2026-09-02 ユーザ質問「週次で新刊コーナーは増える仕組みか」で発見)。在れば SURFACE週に格上げ=機能蒸留が頁を建てる。
    manifest が読めない時も格上げ(安全側。機能蒸留側が manifest 不在で止まるので実害なし)。"""
    if not os.path.isdir(SHINKAN_DIR):
        return []
    months = sorted(f[:-5] for f in os.listdir(SHINKAN_DIR) if re.fullmatch(r"\d{4}-\d{2}\.json", f))
    manifest, status = _r2_manifest.load(MANIFEST, quarantine=False)
    if status != "ok":
        print(f"  WARN r2-manifest が {status} → /shinkan 新月判定不能=全月を未配信扱い(安全側)")
        return months
    return [ym for ym in months if f"shinkan/{ym}.html" not in manifest]
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
    new_months = shinkan_months_missing_html()
    print(f"基準: 前回フル {base[:9]} → HEAD")
    if new_months:
        head = ", ".join(new_months[:6]) + (" …" if len(new_months) > 6 else "")
        print(f"★/shinkan 月別頁のHTML未配信 {len(new_months)}月 ({head}) = データ週では建たない→機能蒸留(SURFACE)以上が要る")
    if manga:
        print(f"判定: ★CODE週(漫画頁に効くコード {len(manga)}件) → 従来フルビルド週次(手順3〜6)")
        for f in manga[:8]:
            print("   ", f)
        sys.exit(2)
    if surface or new_months:
        why = f"非漫画面のコードのみ {len(surface)}件" + (f" + /shinkan新月HTML {len(new_months)}月" if new_months else "")
        print(f"判定: SURFACE週({why}) → データ週+機能蒸留:")
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
