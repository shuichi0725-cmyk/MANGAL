"""intake.py = 取込オーケストレーション (= 派生層の再構築を順序立てて 1 コマンド化)。

★ このscriptが回す範囲 = 「種2 rebuild後 or ソース更新後の 派生層再構築 + 検出 + 本番再生成」。
   STEP6 で merge は series_key 参照になったので 既存mergeは再build後も壊れない。
   本pipelineは 新規work反映 / role再適用 / 検出更新 / 本番更新 のため。

★ このscriptの対象外 (= 別フェーズ、 手動/Go/AI 要):
   - 種1/種504 delta取込 + 種2 rebuild  (= 月次蒸留 Phase0-2、 CLAUDE.md protocol + Go サイン)
   - 種3 AI fill (フリガナ/ジャンル/synopsis)  (= Claude 必要)
   - 種a productionization の種3書込: en-fill (_apply-en-fills-surgical --commit) /
     anilist_id 結線  (= 種3 純粋追加だが deliberate に実行。 match-v14 確定後)
   - NDL裏取りバッチ (_seed4-candidates --ndl)  (= 1時間級throttle、 別途)

依存順序 (フル、 ★promote は adult_us map を読むので最後):
   roles → merge → seed4 → detect
   → match(v9) → match13 → merge14(=v14) → adultus → trailing
   → promote
   (★merge の partial-overlap統合が role を使うので role が先。
    ★matcher v14 → adult_us map → promote が adult_us 付与。 ※matcher は遅い: ~20分)

安全策:
   - default = dry (計画表示のみ)。 --run で実行。
   - db を変更するステージ前に backup。 ステージ失敗で即 abort。
   - git dirty なら警告 (本番yml変更が混ざるため)。

使い方:
   python scripts/intake.py                       # 計画表示 (dry、 フル)
   python scripts/intake.py --run                 # ★フル派生再生成 (matcher+adult_us+promote)
   python scripts/intake.py --run --group madb     # 種2派生のみ (roles→detect→promote、 既存adult_us流用)
   python scripts/intake.py --run --group anilist  # 種a照合のみ (v9→v13→v14→adult_us→trailing)
   python scripts/intake.py --run --stages roles,merge,promote
"""
from __future__ import annotations
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
PY = sys.executable

# stage 定義: (name, group, 説明, コマンド(scriptからの相対), mutates_db)
STAGES = [
    # --- 種2 (MADB) 派生層 ---
    ("roles",   "madb", "series_authors.role 再導出 (raw101+汚染フィルタ)",
        ["_apply-roles-rawfiltered.py", "--apply"], True),
    ("merge",   "madb", "series-merge-auto.json 再生成 (著者集合+kana+partial、 role使用)",
        ["_gen-author-set-merges.py"], False),
    ("seed4",   "madb", "種4 NDL登録の再評価 (volumes-supplement-auto + pending)",
        ["_register-seed4-ndl.py", "--apply"], False),
    ("detect",  "madb", "内部欠け検出 (gap audit、 取込もれ候補更新)",
        ["_audit-volume-gaps.py", "--by-title"], False),
    # --- 種a (AniList) 照合 → match-v14 → 派生 ---
    ("match",   "anilist", "種a↔種3 v9 照合 (match-v9-all.tsv)",
        ["_audit-match-v9.py"], False),
    ("match13", "anilist", "v13 照合 (著者正規化+exact題優先+CSafeLoader、 match-v13-all.tsv)",
        ["_audit-match-v13.py"], False),
    ("merge14", "anilist", "v14 = v9⊕v13 grounded-best マージ (退行0、 match-v14-all.tsv)",
        ["_merge-v14-best.py"], False),
    ("adultus", "anilist", "adult_us map 生成 (種a isAdult=米基準フラグ、 .cache/adult-us-map.json)",
        ["_build-adult-us-map.py"], False),
    ("trailing","anilist", "末尾取込もれ再検出 (AniList総巻数 vs 種2max)",
        ["_audit-trailing-gaps.py"], False),
    # --- 本番再生成 (adult_us map を読むので ★最後) ---
    ("promote", "madb", "本番 yml 再生成 (data/manga.v2、 adult_us 付与)",
        ["_promote-bulk-v2.py"], False),
]


def jst_now():
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d-%H%M%S")


def main():
    args = sys.argv[1:]
    RUN = "--run" in args
    group = None  # default = 全ステージ(依存順フルパイプライン)
    only = None
    for i, a in enumerate(args):
        if a == "--group" and i + 1 < len(args):
            group = args[i + 1]
        if a == "--stages" and i + 1 < len(args):
            only = {s.strip() for s in args[i + 1].split(",") if s.strip()}

    if only:                                   # --stages = 指定のみ(group跨ぎ可)
        plan = [s for s in STAGES if s[0] in only]
    elif group:                                # --group = そのgroupのみ
        plan = [s for s in STAGES if s[1] == group]
    else:                                       # default = フル(matcher→adult_us→promote)
        plan = list(STAGES)

    print("=" * 70)
    print(f"intake pipeline ({'RUN' if RUN else 'DRY = 計画のみ'})  group={group or 'FULL(全ステージ)'}")
    print("=" * 70)
    print("前提(別フェーズ・本scriptの対象外):")
    print("  - 種1/504 delta取込 + 種2 rebuild (月次蒸留 Phase0-2、 Go要)")
    print("  - 種3 AI fill (Claude要) / en-fill・anilist_id 結線 (種3書込=deliberate)")
    print("  - NDL裏取りバッチ (_seed4-candidates --ndl)")
    print("-" * 70)
    print("実行予定ステージ (依存順):")
    for name, g, desc, cmd, mut in plan:
        print(f"  [{name:<9}] {desc}{'  ★db変更' if mut else ''}")
    print("-" * 70)

    if not RUN:
        print("(--run で実行。 db変更ステージ前に自動backup、 失敗で即abort)")
        return

    if not DB.exists():
        print(f"ABORT: {DB} が無い (= 種2 rebuild が先)")
        sys.exit(1)

    # db変更ステージがあれば事前backup
    if any(mut for _, _, _, _, mut in plan):
        bak = DB.with_name(f"db-v2.sqlite.bak-intake-{jst_now()}")
        shutil.copy(DB, bak)
        print(f"[backup] {DB.name} → {bak.name}")

    for name, g, desc, cmd, mut in plan:
        print(f"\n{'='*70}\n▶ STAGE [{name}] {desc}\n{'='*70}", flush=True)
        full = [PY, str(ROOT / "scripts" / cmd[0])] + cmd[1:]
        r = subprocess.run(full, cwd=str(ROOT))
        if r.returncode != 0:
            print(f"\n✗ ABORT: stage [{name}] failed (exit {r.returncode})")
            sys.exit(r.returncode)
        print(f"✓ stage [{name}] done")

    print(f"\n{'='*70}\n✓ intake pipeline 完了 (group={group})")
    print("次: git diff で本番yml変更を確認 → commit/push。")
    print("    種a productionization(en-fill/anilist_id=種3書込)と種3 AI fill は別途 deliberate に。")


if __name__ == "__main__":
    main()
