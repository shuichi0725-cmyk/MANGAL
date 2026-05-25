"""指定シリーズについて 「volume_label の prefix で 集計分割」 した場合の
適用前後の cluster + gap を **シミュレーションのみ** で 比較表示。

破壊操作なし。 sqlite 不変。 audit script にも 触らない。
ユーザが分割効果を 目視確認するための probe ツール。

使い方: python scripts/_sim-label-split.py
  → デフォルト = 艦これ コミックアラカルト を 確認
  → 別シリーズに 切り替えるなら TARGETS list を 変更
"""
from __future__ import annotations
import re
import sqlite3
from pathlib import Path

DB = Path(".cache/db-v2.sqlite")

# 確認対象: title 部分一致 で 引く
TARGETS = [
    "艦隊これくしょん-艦これ-コミックアラカルト",
    "艦隊これくしょん-艦これ-電撃コミックアンソロジー",
]

# label の末尾数字 を 除いた prefix を 抽出
LABEL_PREFIX_RE = re.compile(r"^(.+?)\s*(\d+)\s*$")
NUM_RE = re.compile(r"^\s*(\d+)\s*$")


def to_int(s):
    if s is None:
        return None
    m = NUM_RE.match(str(s))
    return int(m.group(1)) if m else None


def get_label_prefix(label: str | None) -> str:
    """'舞鶴鎮守府編19' → '舞鶴鎮守府編'、 'SP記念!2' → 'SP記念!'、 None/'' → ''"""
    if not label:
        return ""
    m = LABEL_PREFIX_RE.match(label)
    return m.group(1).strip() if m else label.strip()


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    for target in TARGETS:
        print(f"\n========== TARGET: {target} ==========")
        srows = con.execute(
            "SELECT id, qid, title, subtitle FROM series WHERE title LIKE ?",
            (f"%{target}%",),
        ).fetchall()
        if not srows:
            print("  (no series)")
            continue

        sids = [r["id"] for r in srows]
        ph = ",".join("?" * len(sids))
        vrows = con.execute(
            f"""
            SELECT v.number, v.volume_label, v.is_extra, e.type AS edt,
                   e.series_id, s.title AS stitle, s.subtitle AS ssub
            FROM volumes v
            JOIN editions e ON e.id = v.edition_id
            JOIN series s   ON s.id = e.series_id
            WHERE e.series_id IN ({ph})
            """,
            sids,
        ).fetchall()

        # 適用前 (= 現 audit) bucket = (cluster_key, edt)  ← cluster_key は title 統合済想定
        # ここでは シミュレーションなので 簡略化 = 「title 統合した全 series_id を 同 cluster」 と仮定
        before_buckets: dict[tuple[str, ...], list[int]] = {}
        after_buckets: dict[tuple[str, ...], list[int]] = {}

        cluster_key = f"target:{target}"

        for v in vrows:
            if v["is_extra"]:
                continue
            n = to_int(v["number"])
            if n is None or n <= 0:
                continue
            label = v["volume_label"]
            prefix = get_label_prefix(label)

            b_key = (cluster_key, v["edt"] or "standard")
            a_key = (cluster_key, v["edt"] or "standard", prefix)

            before_buckets.setdefault(b_key, []).append(n)
            after_buckets.setdefault(a_key, []).append(n)

        # 表示
        def show(buckets, label_text):
            print(f"\n  --- {label_text} ---")
            for k, nums in sorted(buckets.items(), key=lambda x: (-max(x[1]) if x[1] else 0)):
                snums = sorted(set(nums))
                mx = max(snums)
                expected = set(range(1, mx + 1))
                missing = sorted(expected - set(snums))
                print(f"    {k}")
                print(f"      max={mx}, present={len(snums)}, gap={len(missing)}")
                if len(snums) <= 30:
                    print(f"      nums: {snums}")
                else:
                    print(f"      nums (first 10): {snums[:10]}, (last 10): {snums[-10:]}")
                if missing and len(missing) <= 30:
                    print(f"      missing: {missing}")
                elif missing:
                    print(f"      missing (first 30): {missing[:30]}... total {len(missing)}")

        show(before_buckets, "BEFORE (= 現状 = label 無視で 1 bucket に集約)")
        show(after_buckets, "AFTER (= label_prefix で 分割)")


if __name__ == "__main__":
    main()
