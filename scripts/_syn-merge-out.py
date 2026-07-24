"""syn-out(AI和訳 batch出力) を merge → ★あらすじ本体ゼロ由来を除外 → 1本のbatchへ。

★除外の理由: AniList には「本文ゼロ + Note: Includes one extra chapter. だけ」の record が
  多数あり(2026-07-25 実測 520件中215件)、AI は巻数/ジャンルから定型文を作ってしまう。
  それは「あらすじ」ではないので seed に入れない ([[feedback_accuracy_is_the_goal]] /
  「作れないものは作らない」)。 抽出器側も同条件で塞いだが、既存出力にも同じ濾過をかける。

usage: python scripts/_syn-merge-out.py <in_dir> <out_dir> <merged.json>
  例: python scripts/_syn-merge-out.py .cache/syn-batches-v2 .cache/syn-out-v2 .cache/syn-merged.json
出力の merged.json を `_apply-synopsis.py` に渡す。
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
NOTE = re.compile(r"\s*Note:.*$", re.I | re.S)
SOURCE = re.compile(r"\(Source:[^)]*\)")


def body(s):
    return SOURCE.sub("", NOTE.sub("", s or "")).strip()


def main():
    indir, outdir, dest = (Path(a) for a in sys.argv[1:4])
    src = {}
    for p in sorted(indir.glob("batch-*.json")):
        for x in json.loads(p.read_text(encoding="utf-8")):
            src[str(x["anilist_id"])] = x["desc"]

    merged, dropped, orphan = {}, [], 0
    for p in sorted(outdir.glob("batch-*.json")):
        for aid, ja in json.loads(p.read_text(encoding="utf-8")).items():
            aid = str(aid)
            if aid not in src:
                orphan += 1
                continue
            if len(body(src[aid])) < 20:          # ★本体ゼロ = 定型文しか作れない → 捨てる
                dropped.append(aid)
                continue
            merged[str(aid)] = (ja or "").strip()

    dest.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    L = [len(v) for v in merged.values()] or [0]
    print(f"merge: 採用 {len(merged):,} / ★本体ゼロで除外 {len(dropped):,} / 入力外 {orphan}")
    print(f"  和訳 文字数 min {min(L)} / avg {sum(L)//len(L)} / max {max(L)}")
    print(f"  → {dest}")


if __name__ == "__main__":
    main()
