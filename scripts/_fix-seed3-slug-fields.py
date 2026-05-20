#!/usr/bin/env python3
"""B-2: seed3 yml の 51 件の手動 slug field を 修正 / 削除 / 追加。

仕様 (= 会議で確定):
- A カテゴリ (= 純和語、 22件): slug field 削除 → 自動生成に任せる
- B カテゴリ (= 外来語ローマ字、 11件): slug field 削除 + alternative_titles.en 追加
- C1 (= アニメコミカライズ、 6件): entry 削除
- C2 (= 漫画ではない、 1件): entry 削除
- C3 (= 編集版、 5件): slug field 削除 → 自動生成で本編 slug に統合
- C4 (= key/slug 不整合): slug field 削除 (例外: Pの悲劇 は 'p-no-higeki' に書き換え)
- C5 (= 不可解 suffix、 1件): slug field 削除

PUA 文字保護のため line-by-line で処理 (= yaml.load/dump は不可)。
"""

import re
import shutil
import sys
from pathlib import Path

YML = Path("data/seeds/series-supplement-v2.yml")

# 削除対象 entry key (= C1 アニメコミカライズ + C2 漫画ではない、 計 7 件)
DELETE_KEYS = {
    "qid:Q219948|name:テレビアニメ版 犬夜叉",
    "qid:Q219948|name:劇場版犬夜叉時代を越える想い",
    "qid:Q219948|name:映画 犬夜叉",
    "qid:Q219948|name:うる星やつら2|sub:ビューティフル・ドリーマー",
    "qid:Q219948|name:うる星やつら3|sub:リメンバー・マイ・ラヴ",
    "qid:Q219948|name:うる星やつら4|sub:ラム・ザ・フォーエバー",
    "qid:Q219948|name:うる星やつら ソングBOOK",
}

# slug field 削除のみ (= A + C3 + C4 + C5、 計 43 件、 ただし削除済 entry は別)
SLUG_DELETE_KEYS = {
    # A カテゴリ (= 純和語等、 22件)
    "qid:Q1993|name:NARUTO",
    "qid:Q1324593|name:銀魂",
    "qid:Q219948|name:MAO",
    "qid:Q47465101|name:アオアシ",
    "qid:Q24865213|name:鬼滅の刃",
    "qid:Q3782468|name:進撃の巨人",
    "qid:Q230962|name:鋼の錬金術師",
    "qid:Q719354|name:ジョジョの奇妙な冒険",
    "qid:Q219948|name:うる星やつら",
    "qid:Q219948|name:人魚の傷",
    "qid:Q219948|name:人魚の森",
    "qid:Q219948|name:夜叉の瞳",
    "qid:Q219948|name:専務の犬",
    "qid:Q219948|name:犬夜叉奥義皆伝",
    "qid:Q219948|name:赤い花束",
    "qid:Q219948|name:運命の鳥",
    "qid:Q219948|name:鏡が来た",
    "qid:Q219948|name:高橋留美子",
    "qid:Q219948|name:高橋留美子劇場",
    "qid:Q219948|name:高橋留美子傑作短編集",
    "qid:Q219948|name:境界のRINNE",
    "qid:Q219948|name:半妖の夜叉姫|sub:異伝・絵本草子",
    "qid:Q219948|name:英訳・うる星やつら",
    "qid:Q219948|name:1ポンドの福音",
    "qid:Q219948|name:ザ・超女",
    # C3 編集版 → 本編 slug に統合 (= slug 削除で自動生成)
    "qid:Q11615162|name:美味しんぼ",
    "qid:Q219948|name:うる星やつらパーフェクト★カラーエディション",
    "qid:Q459911|name:SLAM DUNK|sub:新装再編版",
    "qid:Q313945|name:名探偵コナン",
    "qid:Q219948|name:るーみっくわーるど35",  # 編集版扱い (= 35周年記念)
    # C4 key/slug 不整合 (= Pの悲劇 は別 + 1 or W)
    "qid:Q219948|name:1 or W",
    # C5 不可解 suffix
    "qid:Q219948|name:犬夜叉",
}

# slug field 値変更 (= C4 Pの悲劇 のみ)
SLUG_REWRITE = {
    "qid:Q219948|name:Pの悲劇": "p-no-higeki",
}

# B カテゴリ (= slug 削除 + en fill、 11件)
EN_FILL = {
    "qid:Q11411575|name:ハイキュー!!": "Haikyu!!",
    "qid:Q2010|name:ONE PIECE": "One Piece",
    "qid:Q208582|name:ドラゴンボール": "Dragon Ball",
    "qid:Q219948|name:めぞん一刻": "Maison Ikkoku",
    "qid:Q295073|name:Bleach": "Bleach",
    "qid:Q3981526|name:SPY×FAMILY": "Spy x Family",
    "qid:Q550311|name:ハンター×ハンター": "Hunter x Hunter",
    "qid:Q715725|name:ベルセルク": "Berserk",
    "qid:Q9116547|name:キングダム": "Kingdom",
    "qid:Q219948|name:るーみっくわーるど": "Rumic World",
    "qid:Q219948|name:らんま1/2": "Ranma ½",  # 数字特殊読み、 en で公式英題
}

# B 一覧の中で slug 削除も同時に行う (= EN_FILL の key と同じ)
SLUG_DELETE_KEYS |= set(EN_FILL.keys())


def process_lines(lines: list[str]) -> list[str]:
    """seed3 yml の 各 entry block を 処理。

    block 構造:
      - key: <key string>
        magazine: ...
        slug: ...   ← 削除 or 書換 対象
        alternative_titles:
          en: ...   ← 追加 対象
        ...
    """
    out = []
    i = 0
    n = len(lines)
    stats = {
        "deleted_entry": 0,
        "deleted_slug": 0,
        "rewrote_slug": 0,
        "added_en": 0,
        "skipped_en_already": 0,
    }
    matched_keys: set[str] = set()

    while i < n:
        line = lines[i]
        # entry の開始行 (= "  - key: ...")
        m = re.match(r"^  - key: (.+)$", line)
        if not m:
            out.append(line)
            i += 1
            continue

        key = m.group(1).rstrip()
        # block の 範囲 (= 次の "  - key:" or EOF まで) を 取得
        j = i + 1
        while j < n and not re.match(r"^  - key: ", lines[j]):
            j += 1
        block = lines[i:j]

        # ---- 削除対象 entry ----
        if key in DELETE_KEYS:
            matched_keys.add(key)
            stats["deleted_entry"] += 1
            i = j
            continue  # block ごと skip

        # ---- block 修正 ----
        new_block = list(block)

        # slug field の処理
        slug_idx = None
        for k, bl in enumerate(new_block):
            if re.match(r"^    slug:\s", bl):
                slug_idx = k
                break

        if key in SLUG_REWRITE:
            new_value = SLUG_REWRITE[key]
            matched_keys.add(key)
            if slug_idx is not None:
                new_block[slug_idx] = f"    slug: {new_value}\n"
                stats["rewrote_slug"] += 1
            else:
                # slug 行が無ければ key 行の直後に挿入
                new_block.insert(1, f"    slug: {new_value}\n")
                stats["rewrote_slug"] += 1
        elif key in SLUG_DELETE_KEYS:
            matched_keys.add(key)
            if slug_idx is not None:
                new_block.pop(slug_idx)
                stats["deleted_slug"] += 1

        # en fill
        if key in EN_FILL:
            en_value = EN_FILL[key]
            # 既に alternative_titles.en があるか確認
            has_en = any(re.match(r"^      en:\s", b) for b in new_block)
            if has_en:
                stats["skipped_en_already"] += 1
            else:
                # alternative_titles ブロックがあるか
                alt_idx = None
                for k, bl in enumerate(new_block):
                    if re.match(r"^    alternative_titles:\s*$", bl):
                        alt_idx = k
                        break
                if alt_idx is not None:
                    # 既存 alternative_titles の 下に en 追加
                    new_block.insert(alt_idx + 1, f"      en: {en_value}\n")
                else:
                    # 末尾に alternative_titles + en 追加
                    new_block.append(f"    alternative_titles:\n")
                    new_block.append(f"      en: {en_value}\n")
                stats["added_en"] += 1

        out.extend(new_block)
        i = j

    # マッチしなかった key を表示
    expected_keys = (
        DELETE_KEYS | SLUG_DELETE_KEYS | set(SLUG_REWRITE.keys()) | set(EN_FILL.keys())
    )
    missing = expected_keys - matched_keys
    if missing:
        print(f"\n⚠️ matched 失敗 (= key 不一致 or entry 不存在): {len(missing)} 件",
              file=sys.stderr)
        for k in sorted(missing):
            print(f"  - {k}", file=sys.stderr)

    print(f"\n=== 統計 ===", file=sys.stderr)
    for k, v in stats.items():
        print(f"  {k}: {v}", file=sys.stderr)

    return out


def main():
    with YML.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    print(f"loaded {len(lines)} lines", file=sys.stderr)
    new_lines = process_lines(lines)
    print(f"output {len(new_lines)} lines (diff: {len(lines) - len(new_lines):+d})",
          file=sys.stderr)
    with YML.open("w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"\n✅ written to {YML}", file=sys.stderr)


if __name__ == "__main__":
    main()
