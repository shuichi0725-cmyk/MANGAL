# -*- coding: utf-8 -*-
"""AniList dump(v3) → 連載状態の軽量map生成 (2026-08-18 連載中再検査)。

出力 = .cache/anilist-status-map.json  {anilist_id(str): [status, endYear]}
status = FINISHED / RELEASING / CANCELLED / HIATUS / NOT_YET_RELEASED。
promote の外部権威層(_load_anilist_status)が読む。dumpから常に再生成可能なので .cache 置き。
月次/週次で dump を更新したら再実行する。
"""
import gzip
import io
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".cache" / "anilist-manga-dump-v3.jsonl.gz"
OUT = ROOT / ".cache" / "anilist-status-map.json"


def main() -> None:
    m = {}
    with gzip.open(SRC, "rt", encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            st = r.get("status")
            if not st:
                continue
            ey = (r.get("endDate") or {}).get("year")
            m[str(r["id"])] = [st, ey]
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(
        json.dumps(m, ensure_ascii=False, separators=(",", ":"))
    )
    print(f"entries: {len(m)} -> {OUT}")
    print(Counter(v[0] for v in m.values()))


if __name__ == "__main__":
    main()
