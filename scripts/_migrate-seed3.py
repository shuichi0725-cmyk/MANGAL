"""step F: 旧 種3 (= data/seeds/series-supplement.yml) を 新 series_key に migrate。

旧 key format:  qid|baseTitle  (qid='noqid' for unresolved)
新 key format:  qid:Q...|name:<title>           (= 副題なし)
                qid:Q...|name:<title>|sub:<sub> (= 副題あり)
                name:<creator>|name:<title>     (= qid 未解決)

migration ロジック:
  1. 旧 entry を 順次走査:
     a. key を (qid, baseTitle) に split
     b. db-v2.series で 一致候補 lookup:
        WHERE qid = ? AND title = ? AND subtitle IS NULL  ← 副題なし優先
     c. 候補 1 件 → 1:1 migrate
        候補 0 件 → orphan (= 旧 entry に対応する新 series なし)
        副題なし候補 0 件 で 副題あり候補 N 件 → ambiguous (= 旧 entry を主 cluster に
          紐づけられない、 別途確認)
  2. 各 新 series で 旧 entry が migrate されなかったもの → AI fill 候補

output:
  - data/seeds/series-supplement-v2.yml (= 新 series_key 形式)
  - data/seeds/migration-stats.yml (= 統計レポート)

旧 yml は 破棄せず 完全保持 (= rollback 可能)。
"""

import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
OLD_SEED3 = ROOT / "data" / "seeds" / "series-supplement.yml"
NEW_SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
STATS_YML = ROOT / "data" / "seeds" / "migration-stats.yml"


def load_old_seed3():
    print(f"loading {OLD_SEED3} ...", file=sys.stderr)
    with OLD_SEED3.open("r", encoding="utf-8") as f:
        d = yaml.safe_load(f)
    return d


def main():
    old = load_old_seed3()
    old_entries = old["series"]
    print(f"  old entries: {len(old_entries)}", file=sys.stderr)

    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    # 新 series の lookup index
    # qid 持ち: (qid, title, subtitle_or_null) → series_row
    # qid なし: (qid_part='name:creator', title, subtitle_or_null) → series_row
    new_by_qid_title: dict[tuple[str, str], list[dict]] = defaultdict(list)
    new_by_id_part_title: dict[tuple[str, str], list[dict]] = defaultdict(list)
    cur.execute("SELECT id, series_key, qid, title, subtitle, source FROM series")
    for r in cur.fetchall():
        rd = dict(r)
        rd["subtitle"] = rd["subtitle"] or ""
        if rd["qid"]:
            new_by_qid_title[(rd["qid"], rd["title"])].append(rd)
        # name:creator|name:title pattern も
        parts = rd["series_key"].split("|")
        if parts and parts[0].startswith("name:"):
            new_by_id_part_title[(parts[0], rd["title"])].append(rd)

    print(
        f"  new series indexed: {len(new_by_qid_title)} qid+title groups + "
        f"{len(new_by_id_part_title)} name+title groups",
        file=sys.stderr,
    )

    # migrate
    stats = Counter()
    migrated_entries = []   # 新 yml に出力する entries (= 移行成功分)
    orphan_old_keys = []    # 対応する新 series なし
    ambiguous_old_keys = [] # 副題なし新 series なし、 副題あり 1+ あり

    migrated_new_keys: set[str] = set()  # 新 series 視点で 「埋まった」 key

    for e in old_entries:
        old_key = e["key"]
        parts = old_key.split("|", 1)
        if len(parts) != 2:
            stats["malformed_old_key"] += 1
            continue
        qid_part, base_title = parts

        # 候補 lookup
        candidates: list[dict] = []
        if qid_part != "noqid" and qid_part.startswith("Q"):
            # qid 持ち
            candidates = new_by_qid_title.get((qid_part, base_title), [])
        else:
            # qid なし → name 形式 lookup を 試行
            # 旧 noqid|... の baseTitle は 副題 strip 済なので そのまま検索
            # 新 series で qid IS NULL かつ title 一致
            candidates = [
                r for r in new_by_qid_title.get(("", base_title), [])
                if not r["qid"]
            ]
            # name:creator pattern も 試行 (= name fallback で 新 series_key)
            for k, v_list in new_by_id_part_title.items():
                if k[1] == base_title:
                    candidates.extend(v_list)

        if not candidates:
            stats["orphan_old"] += 1
            orphan_old_keys.append(old_key)
            continue

        # 副題なし優先 で 1 つ選ぶ
        no_sub = [c for c in candidates if not c["subtitle"]]
        if no_sub:
            target = no_sub[0]
            stats["migrated_1to1" if len(no_sub) == 1 else "migrated_1tom_no_sub"] += 1
        else:
            # 副題あり しかない → ambiguous
            stats["ambiguous_only_sub"] += 1
            ambiguous_old_keys.append(old_key)
            continue

        # migrate
        new_key = target["series_key"]
        new_entry = {k: v for k, v in e.items() if k != "key"}
        new_entry = {"key": new_key, **new_entry}
        migrated_entries.append(new_entry)
        migrated_new_keys.add(new_key)

    # 新 series で 旧 entry に matched されてない (= AI fill 候補)
    all_new_keys = set()
    cur.execute("SELECT series_key, adult_score FROM series WHERE adult_score < 3")
    public_new_keys = []
    for r in cur.fetchall():
        all_new_keys.add(r["series_key"])
        public_new_keys.append(r["series_key"])
    need_fill = set(public_new_keys) - migrated_new_keys
    stats["new_total_public"] = len(public_new_keys)
    stats["new_migrated_from_old"] = len(migrated_new_keys & set(public_new_keys))
    stats["new_need_ai_fill"] = len(need_fill)

    # write new yml
    print(f"\n[write] {NEW_SEED3} ({len(migrated_entries)} entries) ...", file=sys.stderr)
    out_data = {
        "schema_version": 2,
        "generated_at": "{auto-fill on save}",
        "generator": "scripts/_migrate-seed3.py",
        "series": migrated_entries,
    }
    with NEW_SEED3.open("w", encoding="utf-8") as f:
        yaml.dump(out_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    # write migration stats
    stats_data = {
        "stats": dict(stats),
        "orphan_old_keys_sample": orphan_old_keys[:20],
        "orphan_old_keys_count": len(orphan_old_keys),
        "ambiguous_old_keys_sample": ambiguous_old_keys[:20],
        "ambiguous_old_keys_count": len(ambiguous_old_keys),
        "need_fill_sample": list(need_fill)[:20],
    }
    with STATS_YML.open("w", encoding="utf-8") as f:
        yaml.dump(stats_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    print(f"\n=== migration stats ===", file=sys.stderr)
    for k, v in stats.most_common():
        print(f"  {k}: {v}", file=sys.stderr)

    print(f"\nwrote {NEW_SEED3}", file=sys.stderr)
    print(f"wrote {STATS_YML}", file=sys.stderr)
    db.close()


if __name__ == "__main__":
    main()
