"""db-v2.sqlite に adult filter を 適用 (= step E)。

処理:
  1. seed: adult_imprints (= local yml), adult_publishers + adult_mangaka_known
     (= Wikipedia cache yml)
  2. UPDATE series SET adult_score=0 (= step D 仮 score を 一旦リセット)
  3. DELETE FROM adult_signals
  4. 各 series で 5 signals を 計算:
     - madb_content_rating (= series-v2.json cluster.is_adult, weight=5)
     - wikidata_hentai_credit (= mangaka.has_adult_credit, weight=2)
     - wikipedia_adult_mangaka_list (= adult_mangaka_known, weight=2)
     - adult_imprint (= adult_imprints LIKE editions.imprint, weight=3)
     - adult_publisher_imprint (= adult_publishers LIKE editions.imprint, weight=3、
                                 imprint 当たれば 排他で skip)
  5. UPDATE series.adult_score、 INSERT adult_signals
  6. stats 出力

threshold: score >= 3 → 非公開 (= 公開DB から除外)
"""

import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SERIES_V2 = ROOT / ".cache" / "series-v2.json"
IMPRINTS_YML = ROOT / "data" / "seeds" / "adult-imprints.yml"
WIKI_CACHE_YML = ROOT / "data" / "seeds" / "adult-wikipedia-cache.yml"


def normalize_creator_name(s: str) -> str:
    """lib/edition.ts normalizeCreatorName() の Python 移植。"""
    # NFKC + 空白/記号 除去
    import unicodedata
    n = unicodedata.normalize("NFKC", s)
    return re.sub(r"[\s,，、・·.\-_]", "", n)


def match_adult_imprint(imprint: str, known_set: set[str]) -> str | None:
    """imprint が known_set に substring 含まれていれば match name 返す。"""
    if not imprint:
        return None
    import unicodedata
    norm = unicodedata.normalize("NFKC", imprint)
    if norm in known_set:
        return norm
    for name in known_set:
        if name in norm:
            return name
    return None


def seed_adult_tables(db: sqlite3.Connection) -> dict:
    """yml 経由で 3 tables を 再 seed (= db-v2 に)"""
    stats = {}
    cur = db.cursor()

    # adult_imprints
    cur.execute("DELETE FROM adult_imprints")
    with IMPRINTS_YML.open("r", encoding="utf-8") as f:
        d = yaml.safe_load(f)
    n = 0
    for r in d.get("imprints", []):
        cur.execute(
            "INSERT OR IGNORE INTO adult_imprints (imprint, publisher, count, source) "
            "VALUES (?, ?, ?, ?)",
            (r["imprint"], r.get("publisher"), r.get("count"), "manual_seed"),
        )
        n += 1
    stats["adult_imprints"] = n

    # adult_publishers + adult_mangaka_known (= Wikipedia cache)
    cur.execute("DELETE FROM adult_publishers")
    cur.execute("DELETE FROM adult_mangaka_known")
    with WIKI_CACHE_YML.open("r", encoding="utf-8") as f:
        d = yaml.safe_load(f)
    n_pub = 0
    for r in d.get("adult_publishers", []):
        cur.execute(
            "INSERT OR IGNORE INTO adult_publishers (name, source) VALUES (?, ?)",
            (r["name"], r.get("source", "wikipedia_adult_magazines")),
        )
        n_pub += 1
    n_mk = 0
    for r in d.get("adult_mangaka_known", []):
        cur.execute(
            "INSERT OR IGNORE INTO adult_mangaka_known (name, display, source) "
            "VALUES (?, ?, ?)",
            (r["name"], r["display"], r.get("source", "wikipedia_adult_mangaka_list")),
        )
        n_mk += 1
    stats["adult_publishers"] = n_pub
    stats["adult_mangaka_known"] = n_mk
    db.commit()
    return stats


def main():
    print(f"loading {SERIES_V2} ...", file=sys.stderr)
    with SERIES_V2.open("r", encoding="utf-8") as f:
        v2 = json.load(f)
    # series_key → cluster lookup (= is_adult を 取るため)
    cluster_by_key = {c["series_key"]: c for c in v2["clusters"]}
    print(f"  v2 clusters: {len(cluster_by_key)}", file=sys.stderr)

    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row

    print(f"\n[seed] adult tables ...", file=sys.stderr)
    seed_stats = seed_adult_tables(db)
    for k, v in seed_stats.items():
        print(f"  {k}: {v}", file=sys.stderr)

    cur = db.cursor()

    # reset score + signals
    cur.execute("UPDATE series SET adult_score = 0")
    cur.execute("DELETE FROM adult_signals")
    db.commit()

    # known sets (= in-memory)
    known_imprints = {r["imprint"] for r in cur.execute("SELECT imprint FROM adult_imprints")}
    known_publishers = {r["name"] for r in cur.execute("SELECT name FROM adult_publishers")}
    known_mangaka = {r["name"] for r in cur.execute("SELECT name FROM adult_mangaka_known")}
    print(f"\nin-memory sets: imprints={len(known_imprints)}, publishers={len(known_publishers)}, mangaka={len(known_mangaka)}", file=sys.stderr)

    # process each series
    cur.execute("""
        SELECT s.id, s.series_key, s.qid, s.title, s.adult_score
        FROM series s
    """)
    series_rows = cur.fetchall()
    print(f"\nprocessing {len(series_rows)} series ...", file=sys.stderr)

    # mangaka.has_adult_credit lookup
    mangaka_adult = {}  # qid → has_adult_credit
    cur.execute("SELECT qid, name, has_adult_credit FROM mangaka")
    for r in cur.fetchall():
        mangaka_adult[r["qid"]] = (r["name"], bool(r["has_adult_credit"]))

    sig_counter: Counter = Counter()
    score_dist: Counter = Counter()
    signal_inserts = []
    score_updates = []

    for s in series_rows:
        series_id = s["id"]
        key = s["series_key"]
        qid = s["qid"]
        title = s["title"]
        cluster = cluster_by_key.get(key)
        score = 0
        signals = []  # list of (signal, weight, evidence)

        # 1. madb_content_rating (= cluster.is_adult)
        if cluster and cluster.get("is_adult"):
            score += 5
            signals.append(("madb_content_rating", 5, "schema:contentRating=成年コミック"))

        # 2. wikidata_hentai_credit
        if qid and qid in mangaka_adult:
            author_name, has_credit = mangaka_adult[qid]
            if has_credit:
                score += 2
                signals.append(("wikidata_hentai_credit", 2, author_name))

        # 3. wikipedia_adult_mangaka_list (= known_mangaka 名前一致)
        # cluster の creator_name を normalize して 照合
        if cluster:
            cname = cluster.get("creator_name") or ""
            norm = normalize_creator_name(cname)
            if norm and norm in known_mangaka:
                score += 2
                signals.append(("wikipedia_adult_mangaka_list", 2, cname))

        # 4 + 5. imprints (= editions.imprint で 照合、 imprint 当たれば publisher skip)
        cur2 = db.cursor()
        cur2.execute("SELECT imprint FROM editions WHERE series_id=?", (series_id,))
        imprints = [r["imprint"] for r in cur2.fetchall() if r["imprint"]]

        imprint_matched = False
        for imp in imprints:
            matched = match_adult_imprint(imp, known_imprints)
            if matched:
                score += 3
                signals.append(("adult_imprint", 3, f"{imp} ⟵ {matched}"))
                imprint_matched = True
                break
        if not imprint_matched:
            for imp in imprints:
                matched = match_adult_imprint(imp, known_publishers)
                if matched:
                    score += 3
                    signals.append(("adult_publisher_imprint", 3, f"{imp} ⟵ {matched}"))
                    break

        if score > 0:
            score_updates.append((score, series_id))
        for sig, w, ev in signals:
            sig_counter[sig] += 1
            signal_inserts.append((series_id, sig, w, ev))
        score_dist[score] += 1

    # batch update
    print(f"\n[apply] {len(score_updates)} series with score > 0", file=sys.stderr)
    cur.executemany("UPDATE series SET adult_score=? WHERE id=?", score_updates)
    cur.executemany(
        "INSERT OR REPLACE INTO adult_signals (series_id, signal, weight, evidence) VALUES (?, ?, ?, ?)",
        signal_inserts,
    )
    db.commit()

    print(f"\n=== signal 分布 ===", file=sys.stderr)
    for sig, cnt in sig_counter.most_common():
        print(f"  {sig}: {cnt}", file=sys.stderr)

    print(f"\n=== adult_score 分布 ===", file=sys.stderr)
    for sc in sorted(score_dist.keys()):
        print(f"  score={sc}: {score_dist[sc]}", file=sys.stderr)

    # threshold cut
    threshold = 3
    print(f"\n=== threshold check (= score >= {threshold} → 非公開) ===", file=sys.stderr)
    over = sum(c for s, c in score_dist.items() if s >= threshold)
    under = sum(c for s, c in score_dist.items() if s < threshold)
    print(f"  非公開 (= adult): {over}", file=sys.stderr)
    print(f"  公開              : {under}", file=sys.stderr)

    db.close()


if __name__ == "__main__":
    main()
