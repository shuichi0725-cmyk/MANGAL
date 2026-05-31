"""種a和訳 synopsis batch を master map (.cache/synopsis-ja-map.json) へ純粋追加。

map = {anilist_id(str): ja_synopsis}。 promote が enrich の anilist_id 経由で join。
★追加 only(既存 aid の上書きは警告+スキップ、 --force で許可)。 長さ check。
usage: _apply-synopsis.py <batch.json> [--force]
"""
import json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
MAP = Path(".cache/synopsis-ja-map.json")


def main():
    if len(sys.argv) < 2:
        print("usage: _apply-synopsis.py <batch.json> [--force]"); return
    batch = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    force = "--force" in sys.argv
    cur = json.loads(MAP.read_text(encoding="utf-8")) if MAP.exists() else {}

    added = overwrote = skipped = 0
    warns = []
    for aid, ja in batch.items():
        aid = str(aid); ja = (ja or "").strip()
        if not ja:
            skipped += 1; continue
        n = len(ja)
        if n < 20 or n > 160:
            warns.append(f"  ⚠ 長さ {n}: aid={aid} {ja[:30]}")
        if aid in cur and cur[aid] != ja:
            if not force:
                skipped += 1; warns.append(f"  ⚠ 既存上書きスキップ aid={aid}"); continue
            overwrote += 1
        elif aid not in cur:
            added += 1
        cur[aid] = ja
    MAP.write_text(json.dumps(cur, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"applied={added}, overwrote={overwrote}, skipped={skipped}, map計={len(cur):,}")
    if warns:
        print("\n".join(warns[:30]))


if __name__ == "__main__":
    main()
