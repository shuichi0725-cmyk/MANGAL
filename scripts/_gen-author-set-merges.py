"""著者集合 + 正規化title による series 統合を自動生成 → data/seeds/series-merge-auto.yml

案A の構造解決本体。 詳細: docs/series-fragmentation-analysis.md。

- 種2 sqlite 不変・種3 不変・series_key 不変。 merge_sids lookup を 生成するだけ。
- 既存 hand 版 (data/seeds/series-merge.yml) の merge_sids と **1 sid でも重複する
  group は skip** (= 手動キュレーション優先、 うる星カラー版/SLF 等を上書きしない)。
- semantic subtitle (第/部/編/外伝/番外/章/完結) を含む混在 group は **保留**
  (= 別ページ維持が正当、 .cache/held-groups-classified.txt 参照)。 自動統合しない。

★ 重要: merge_sids は raw series.id を参照するため、 **db-v2 再 build 後は必ず再生成**
すること (= sid が変わる)。 build flow に組込推奨。

出力: data/seeds/series-merge-auto.json (= _promote-bulk-v2.py が hand yaml と両方 load)
  ※ JSON 採用理由: 約1万 group の PyYAML パースは 30-60秒 と遅い。 json.load なら <1秒。
"""
from __future__ import annotations
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
HAND = ROOT / "data" / "seeds" / "series-merge.yml"
OUT = ROOT / "data" / "seeds" / "series-merge-auto.json"

SEMANTIC = ["第", "部", "編", "外伝", "前編", "後編", "番外", "スピンオフ",
            "章", "完結", "SEASON", "season", "Season", "Part", "PART"]


def norm_title(t: str) -> str:
    return re.sub(r"[・\s　：:，、。.\-―ー~〜!！?？／/]+", "", t or "")


def is_semantic_sub(s: str | None) -> bool:
    return bool(s) and any(m in s for m in SEMANTIC)


def load_hand_merge_sids() -> set[int]:
    """既存 hand 版 series-merge.yml の merge_sids 全 sid (= 重複 skip 用)。"""
    if not HAND.exists():
        return set()
    out: set[int] = set()
    with HAND.open(encoding="utf-8") as f:
        for e in (yaml.safe_load(f) or []):
            for sid in (e.get("merge_sids") or []):
                out.add(int(sid))
    return out


def main() -> None:
    con = sqlite3.connect(DB)
    c = con.cursor()
    auth = defaultdict(set)
    for sid, mid in c.execute("SELECT series_id, mangaka_id FROM series_authors"):
        auth[sid].add(mid)
    volc = defaultdict(int)
    for sid, n in c.execute(
        "SELECT e.series_id, COUNT(*) FROM editions e "
        "JOIN volumes v ON v.edition_id=e.id GROUP BY e.series_id"
    ):
        volc[sid] = n
    rows = c.execute("SELECT id, title, subtitle, qid FROM series").fetchall()

    grp: dict[tuple, list[dict]] = defaultdict(list)
    for sid, t, s, q in rows:
        a = frozenset(auth.get(sid, ()))
        if not a:
            continue  # 著者ゼロは対象外
        grp[(a, norm_title(t))].append(
            {"sid": sid, "title": t, "sub": s, "qid": q, "vols": volc[sid]}
        )

    hand_sids = load_hand_merge_sids()
    print(f"hand merge_sids 既存: {len(hand_sids)} 個 (重複 skip)", file=sys.stderr)

    entries = []
    skipped_hand = 0
    held = 0
    for (a, nt), members in grp.items():
        sids = {m["sid"] for m in members}
        if len(sids) < 2:
            continue
        # semantic subtitle 混在 = 保留 (別ページ維持)
        nonsem = {m["sid"] for m in members if not is_semantic_sub(m["sub"])}
        if any(is_semantic_sub(m["sub"]) for m in members) and len(nonsem) < len(sids):
            held += 1
            continue
        # hand 版と重複 = skip (手動優先)
        if sids & hand_sids:
            skipped_hand += 1
            continue
        members.sort(key=lambda m: -m["vols"])
        main_title = members[0]["title"]
        entries.append({
            "main": main_title,
            "merge_sids": sorted(sids),
            "note": "auto: author-set + normalized-title (_gen-author-set-merges.py)",
        })

    entries.sort(key=lambda e: e["merge_sids"][0])

    doc = {
        "_README": (
            "自動生成 — 手で編集しない。生成元: scripts/_gen-author-set-merges.py / "
            "詳細: docs/series-fragmentation-analysis.md。種2 sqlite 不変・種3 不変・"
            "series_key 不変。手動版 data/seeds/series-merge.yml と重複する group は skip 済"
            "(= 手動優先)。★ db-v2 再 build 後は sid が変わるため必ず再生成すること。"
        ),
        "merges": entries,
    }
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=0)

    print(f"=== series-merge-auto.json 生成 ===", file=sys.stderr)
    print(f"  auto 統合 group     : {len(entries):,}", file=sys.stderr)
    print(f"  hand 重複 skip      : {skipped_hand}", file=sys.stderr)
    print(f"  semantic 保留 skip  : {held}", file=sys.stderr)
    print(f"  統合される series   : {sum(len(e['merge_sids']) for e in entries):,}", file=sys.stderr)
    print(f"  wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
