#!/usr/bin/env python3
"""
Phase④ 適用 = 2パス検証で confirm されたジャンルを genre-rakuten.yml に純粋追加(union)。
過付与は reject されているので、 残ったものだけを足す。
"""
import json, sys
from pathlib import Path
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "genre-rakuten"
PRED = OUT / "phase4-out"
SEED = ROOT / "data" / "seeds" / "genre-rakuten.yml"

import yaml
MASTER = set(yaml.safe_load((ROOT / "data" / "genres.yml").read_text(encoding="utf-8")).keys())


def main():
    doc = yaml.safe_load(SEED.read_text(encoding="utf-8")) or {"additions": []}
    cur = {e["slug"]: set(e.get("genres") or []) for e in doc.get("additions", [])}
    before_works = len(cur)

    # 検証対象として送った候補総数(reject率算出用)
    sent = 0
    for line in (OUT / "gray-candidates.jsonl").open(encoding="utf-8"):
        pass

    confirmed_cnt = Counter()
    n_conf_works = 0; total_confirmed = 0
    for fp in sorted(PRED.glob("batch-*.json")):
        try:
            arr = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ! {fp.name}: {e}", flush=True); continue
        for r in arr:
            slug = r.get("id")
            conf = [g for g in (r.get("confirmed") or []) if g in MASTER]
            if not slug or not conf:
                continue
            n_conf_works += 1
            total_confirmed += len(conf)
            cur.setdefault(slug, set()).update(conf)
            for g in conf:
                confirmed_cnt[g] += 1

    # 書き戻し
    new_add = [{"slug": s, "genres": sorted(gs)} for s, gs in sorted(cur.items())]
    hdr = ("# 楽天あらすじ由来ジャンル(Phase③+④。 provisional work=trusted空 のみ promote が採用)\n"
           "# Phase③=信頼度閾値で適合率≥0.80 / Phase④=2パス検証で confirm された救済分。 [[genre_from_rakuten_story_plan]]\n")
    SEED.write_text(hdr + yaml.dump({"additions": new_add}, allow_unicode=True, sort_keys=False), encoding="utf-8")

    print(f"=== Phase④ 適用結果 ===", flush=True)
    print(f"検証で confirm された work: {n_conf_works:,}(confirm総数 {total_confirmed:,})", flush=True)
    print(f"  救済ジャンル別: " + ", ".join(f"{k}:{c}" for k, c in confirmed_cnt.most_common()), flush=True)
    print(f"genre-rakuten.yml: {before_works:,} → {len(new_add):,} work", flush=True)


if __name__ == "__main__":
    main()
