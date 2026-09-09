#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""共通シェル(全頁で動く器)の配線ゲート。★週次preflight / 機能蒸留の前検査で回す。

なぜ要るか (= 2026-09-08 実害):
  2026-09-07 に PC左レール(FilterRail)を `app/layout.tsx` へ入れて全頁常設にしたところ、
  レールが `useFilterPanelData → useMangaIndex` を無条件に呼ぶため、
  **ホーム以外の全頁(漫画詳細69,241頁を含む)で 索引6.06MB を取得し haystack を前計算**
  するようになった。`hidden lg:block` は CSS で隠すだけなので、レールを一生見ない
  モバイルも実機3,773msを払っていた。
  ★既存の検索スナップショットゲート(lib/searchSnapshot.test.ts)は「結果の正しさ」を見る番人で、
  「どの頁で何を読むか」は構造的に見えない = 全緑のまま本番へ出た。

この番人が見るもの:
  検査1 = 器の費用: layout から到達する **app/ components/ の部品** が
          重いデータ経路(索引ロード/検索前計算)に触れていたら、
          許可台帳 data/seeds/shell-wiring-allow.json に
          「なぜ許すか + どう抑えているか(guards)」が書かれていることを要求する。
          ★guards は実在確認する = 抑制を外すと台帳が嘘になり、ここで落ちる(判子だけの許可を防ぐ)。
  検査2 = 境界の整合: 「左レールが出る幅」「モバイル抽斗が消える幅」「JS側 matchMedia の値」が
          全部同じであること。ズレると **どちらも出ない幅の帯** が生まれる
          (実害: 2026-09-07〜 768〜1023px に絞り込みUIが1つも無かった)。

使い方:
  python scripts/_check-shell-wiring.py          # FAIL があれば exit 1
  python scripts/_check-shell-wiring.py --list   # 到達部品と重い経路を一覧するだけ(exit 0)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = os.path.join(ROOT, "data", "seeds", "shell-wiring-allow.json")
LAYOUT = os.path.join(ROOT, "app", "layout.tsx")

# 重いデータ経路 = 一覧索引(6.06MB)の取得 / 検索の前計算 に繋がる呼び名。
HEAVY = ("useMangaIndex", "useFilterPanelData", "ensureFullIndex", "prewarmSearch", "prewarmAlt")
# 実装そのもの(= lib 配下)は対象外。見たいのは「器にマウントされる部品」の側。
WATCH_DIRS = ("app/", "components/")

# ★重いサーバローダ = 呼んだ結果を props で渡すと **全ルートの RSC ペイロード**
#   (HTML内インライン + .txt の2箇所)に直列化される。 2026-09-09 実害:
#   layout の `loadMasters()` が publishers+magazines 48.6KB を全92,000ルートへ焼き、
#   **約9.9GB**(out/ 19.0GB の52%)を生んだ。 `/contact` は80.6KB中69.4KBが出版社リストだった。
#   ※ import しただけ(= 大きいJSONから2文字列だけ導出する等)は無害。 見るのは**呼び出し**。
HEAVY_LOADERS = (
    "loadMasters", "loadListBundle", "loadAllManga", "loadArtBooks",
    "loadMangaListIndex", "loadTitlesPages", "loadAiReviews",
)
# 最小頁の床を測る実測プローブ(内容がほぼ無い頁 = 太っていれば器のせい)。
FLOOR_PROBE = os.path.join("out", "contact.html")
FLOOR_LIMIT_KB = 45.0

IMPORT_RE = re.compile(r'^\s*import\s+(?:[^\'"]*?\s+from\s+)?[\'"]([^\'"]+)[\'"]', re.M)

# Tailwind 既定のブレイクポイント
BP_PX = {"sm": 640, "md": 768, "lg": 1024, "xl": 1280, "2xl": 1536}

fails: list[tuple[str, str]] = []
oks: list[str] = []


def fail(msg: str, detail: str = "") -> None:
    fails.append((msg, detail))


def ok(msg: str) -> None:
    oks.append(msg)


def rel(p: str) -> str:
    return os.path.relpath(p, ROOT).replace("\\", "/")


def resolve(spec: str, frm: str) -> str | None:
    if spec.startswith("@/"):
        base = os.path.join(ROOT, spec[2:])
    elif spec.startswith("."):
        base = os.path.normpath(os.path.join(os.path.dirname(frm), spec))
    else:
        return None  # node_modules は追わない
    for ext in (".tsx", ".ts", "/index.tsx", "/index.ts"):
        if os.path.exists(base + ext):
            return base + ext
    return base if os.path.isfile(base) else None


def walk_from_layout() -> tuple[set[str], dict[str, list[str]]]:
    """layout から到達する .ts/.tsx を集め、各ファイルの「重い呼び名」も返す。"""
    seen: set[str] = set()
    heavy: dict[str, list[str]] = {}

    def go(path: str) -> None:
        if path in seen or not path.endswith((".ts", ".tsx")):
            return
        seen.add(path)
        try:
            src = open(path, encoding="utf-8").read()
        except Exception:
            return
        found = [h for h in HEAVY if re.search(r"\b" + h + r"\b", src)]
        if found:
            heavy[rel(path)] = found
        for spec in IMPORT_RE.findall(src):
            p = resolve(spec, path)
            if p:
                go(p)

    go(LAYOUT)
    return seen, heavy


def _guard_is_used(src: str, guard: str) -> bool:
    """guard が「実際に使われている」か。★宣言だけ残して呼び出しを消す抜け道を塞ぐ。

    2026-09-08 の負テストで発覚: 単なる識別子検索だと
    `const isLg = useIsLg();` を `const isLg = true;` に書き換えても、
    **同じファイルに残る `function useIsLg()` の定義**に当たって素通りした
    (= 抑制が消えているのに台帳が通る = 判子だけの許可)。
    宣言行(function/const/let/var/型のプロパティ)を落としてから、なお残る出現を「使用」と数える。
    """
    g = re.escape(guard)
    decl = re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?function\s+" + g + r"\b"      # function useIsLg(...)
        r"|^\s*(?:export\s+)?(?:const|let|var)\s+" + g + r"\b"          # const wantIndex = ...
        r"|^\s*" + g + r"\??\s*:\s*[A-Za-z(]",                          # 型/引数の宣言 enabled?: boolean
        re.M,
    )
    body = "\n".join(ln for ln in src.splitlines() if not decl.match(ln))
    return re.search(r"\b" + g + r"\b", body) is not None


def check1_shell_cost(heavy: dict[str, list[str]]) -> None:
    """検査1: 器に載る部品が重いデータ経路に触れるなら、許可台帳+抑制の実在を要求。"""
    targets = {f: hs for f, hs in heavy.items() if f.startswith(WATCH_DIRS)}
    allow = {}
    if os.path.exists(ALLOW):
        try:
            allow = json.load(open(ALLOW, encoding="utf-8"))
        except Exception as e:
            fail(f"許可台帳が読めない {rel(ALLOW)}: {e}")
            return
    else:
        fail(f"許可台帳が無い {rel(ALLOW)}",
             "初回は {} を置き、下の指摘に従って entry を書く")
        return

    for f, hs in sorted(targets.items()):
        entry = allow.get(f)
        if not entry:
            fail(
                f"★器に載る部品が索引を読む: {f} ({', '.join(hs)})",
                "layout から到達する部品は**全頁**で動く。索引は6.06MB・haystack前計算は実機3,773ms。\n"
                "       意図した配線なら data/seeds/shell-wiring-allow.json に\n"
                '       {\"reason\": \"なぜ必要か\", \"gate\": \"どう抑えているか\", \"guards\": [\"実在を検査する識別子\"]}\n'
                "       を追加する。意図していないなら配線を外す(= lib を器から切る)。",
            )
            continue
        guards = entry.get("guards") or []
        if not guards:
            fail(f"許可台帳に guards が無い: {f}",
                 "抑制の実体(識別子)を1つ以上書く。書かないと『判子だけの許可』になる。")
            continue
        src = open(os.path.join(ROOT, f), encoding="utf-8").read()
        missing = [g for g in guards if not _guard_is_used(src, g)]
        if missing:
            fail(
                f"★抑制が消えている: {f} に {', '.join(missing)} が無い",
                f"台帳の gate: {entry.get('gate', '(未記入)')}\n"
                "       抑制を外したのに台帳が古いまま = 全頁で索引を読む状態に戻っている疑い。",
            )
        else:
            ok(f"器の費用 {f}: 抑制あり({', '.join(guards)})")

    # 台帳にあるのに、もう器から到達しない entry は掃除を促す(腐り防止)。
    # ★"_" 始まりはメタキー(_readme 等)なので対象外(消せと案内すると読み手を惑わす)。
    for f in allow:
        if not f.startswith("_") and f not in targets:
            ok(f"許可台帳の {f} は現在 layout から到達しない(entry を消してよい)")

    if not targets:
        ok("器に載る部品で索引を読むものは無い")


def _find(path: str, pattern: str, flags=0):
    src = open(os.path.join(ROOT, path), encoding="utf-8").read()
    return re.findall(pattern, src, flags), src


def check2_breakpoints() -> None:
    """検査2: レールが出る幅 / 抽斗が消える幅 / matchMedia の3つが一致しているか。"""
    rail = "components/FilterRail.tsx"
    home = "app/HomeClient.tsx"
    for p in (rail, home):
        if not os.path.exists(os.path.join(ROOT, p)):
            fail(f"境界検査の対象が無い: {p}")
            return

    # ① レールの表示境界: <aside className="hidden lg:block ...">
    m, _ = _find(rail, r'hidden\s+(sm|md|lg|xl|2xl):block')
    if not m:
        fail(f"{rail}: レールの表示境界(hidden <bp>:block)が見つからない")
        return
    rail_bp = m[0]

    # ② レールのJS側ゲート: matchMedia("(min-width: Npx)")
    m2, _ = _find(rail, r'matchMedia\(\s*"\(min-width:\s*(\d+)px\)"')
    if not m2:
        fail(f"{rail}: matchMedia の境界が見つからない",
             "CSSだけで隠しても中身はマウントされる。JS側のゲートは必須。")
        return
    rail_px = int(m2[0])

    # ③ 抽斗(モバイル用フィルター)の境界: className={`<bp>:hidden fixed inset-0 z-50 ...
    m3, _ = _find(home, r'`(sm|md|lg|xl|2xl):hidden fixed inset-0 z-50')
    if not m3:
        fail(f"{home}: 抽斗オーバーレイの境界(<bp>:hidden fixed inset-0 z-50)が見つからない")
        return
    drawer_bp = m3[0]

    # ④ 抽斗のマウント判定
    m4, _ = _find(home, r'matchMedia\(\s*"\(min-width:\s*(\d+)px\)"')
    if not m4:
        fail(f"{home}: matchMedia の境界が見つからない")
        return
    drawer_px = int(m4[0])

    want = BP_PX[rail_bp]
    bad = []
    if drawer_bp != rail_bp:
        bad.append(f"抽斗 {drawer_bp}: != レール {rail_bp}:")
    if rail_px != want:
        bad.append(f"レールの matchMedia {rail_px}px != {rail_bp}({want}px)")
    if drawer_px != want:
        bad.append(f"抽斗の matchMedia {drawer_px}px != {rail_bp}({want}px)")

    if bad:
        fail(
            "★絞り込みUIの境界がズレている: " + " / ".join(bad),
            "レールが出る幅と抽斗が消える幅がズレると、**どちらも出ない幅の帯**ができる\n"
            "       (2026-09-07〜 実害: レール=lg・抽斗=md で 768〜1023px に絞り込みUIが無かった)。\n"
            "       CSSクラスと matchMedia は必ず同じ値にする(片方だけ動かすと\n"
            "       『CSSでは出るのにマウントされない=押しても何も起きない』になる)。",
        )
    else:
        ok(f"絞り込みUIの境界 = {rail_bp}({want}px) で一致"
           f"(<{want}px=抽斗 / >={want}px=レール、CSSとmatchMediaも一致)")


def check3_serialized_payload() -> None:
    """検査3: 器に載るサーバ部品が**重いローダを呼んで props に流していないか**(静的)。

    ★これが 2026-09-09 に抜けた穴。 検査1は「クライアントの重い経路」を見るので、
      `const masters = loadMasters()` を props で渡す**サーバ側の直列化**は素通りした。
    """
    reachable, _ = walk_from_layout()
    hits: list[tuple[str, list[str]]] = []
    # ★walk_from_layout の seen は**絶対パス**。 rel() を通してから WATCH_DIRS で絞る
    #   (2026-09-09 の負テストで発覚: 絶対パスのまま startswith("app/") して全件素通りした)。
    for path in sorted(reachable):
        f = rel(path)
        if not f.startswith(WATCH_DIRS):
            continue
        if not os.path.exists(path):
            continue
        try:
            src = open(path, encoding="utf-8").read()
        except Exception:
            continue
        found = [n for n in HEAVY_LOADERS if re.search(r"\b" + n + r"\s*\(", src)]
        if found:
            hits.append((f, found))

    if not hits:
        ok("直列化ペイロード = 器に重いローダの呼び出し無し")
        return
    for f, names in hits:
        fail(
            "★器に載る部品が重いローダを呼ぶ: " + f + " (" + ", ".join(names) + ")",
            "戻り値を props で渡すと**全ルートのRSCペイロード**(HTML内 + .txt の2箇所)に焼かれる。\n"
            "       2026-09-09 実測: layout の loadMasters() = 48.6KB x 2 x 92,000ルート = 約9.9GB。\n"
            "       小さく削って渡す(例 loadRailMasters = genres+demographics 1.4KB)か、\n"
            "       静的JSONにしてクライアントで取る(例 /data/masters.json + lib/useRailMasters.ts)。",
        )


def check4_page_floor() -> None:
    """検査4: 直近ビルドの**最小頁の実サイズ**(機構を問わず「太ったら鳴る」実測の網)。

    ★WARN 止まり = preflight はビルドの**前**に走るので、ここで FAIL にすると
      「太りを直すビルド」自体を止めてしまう。 数字を毎回見せることが目的。
    """
    probe = os.path.join(ROOT, FLOOR_PROBE)
    if not os.path.exists(probe):
        ok("最小頁の床 = 未計測(まだ " + FLOOR_PROBE + " が無い)")
        return
    kb = os.path.getsize(probe) / 1024
    if kb <= FLOOR_LIMIT_KB:
        ok("最小頁の床 %s = %.1fKB(上限 %.0fKB)" % (FLOOR_PROBE, kb, FLOOR_LIMIT_KB))
    else:
        ok("⚠ 最小頁の床 %s = %.1fKB > 上限 %.0fKB(前回ビルド時点。"
           "器に重い物が載っていないか検査3と併せて見る)" % (FLOOR_PROBE, kb, FLOOR_LIMIT_KB))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="到達部品と重い経路の一覧だけ出す")
    a = ap.parse_args()

    seen, heavy = walk_from_layout()

    if a.list:
        print(f"layout から到達する .ts/.tsx: {len(seen)} 本")
        print(f"重いデータ経路に触れるもの: {len(heavy)} 本")
        for f, hs in sorted(heavy.items()):
            mark = "★器" if f.startswith(WATCH_DIRS) else "  lib"
            print(f"  {mark} {f}  ({', '.join(hs)})")
        return 0

    check1_shell_cost(heavy)
    check2_breakpoints()
    check3_serialized_payload()
    check4_page_floor()

    for m in oks:
        print(f"  OK   {m}")
    for m, d in fails:
        print(f"  FAIL {m}")
        if d:
            for ln in d.splitlines():
                print(f"       {ln}" if not ln.startswith("       ") else ln)

    print(f"\n共通シェル配線: FAIL {len(fails)} / OK {len(oks)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
