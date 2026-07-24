"""STEP 4: 末尾取込もれ検出 = AniList総巻数 > 種2最大巻 の作品 (= 最新刊がMADBに無い)。

内部欠け(STEP2)の盲点(末尾)を、 AniList volumes(完結作で総巻数確定)で埋める。

★ 慎重:
- 高信頼マッチ(verdict S180)のみ使用 (= 誤マッチ由来の偽信号を排除)。
- 種2の「最大巻」は **merge group 横断 + 種4補完込み** で取る (= グラゼニ↔Gurazeni
  分裂で偽トレイル検出するのを防ぐ。 29件と同じ轍を踏まない)。
- AniList volumes が 種2max より大 のときだけ候補 (= 最新刊欠け)。
- standard edition の巻番号で比較。

入力: .cache/match-v9-all.tsv + db + series-merge-auto.json + volumes-supplement(.yml/-auto.yml)
出力: .cache/trailing-gaps.csv (read-only、 本番不変)
"""
from __future__ import annotations
import csv
import gzip
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
TSV = ROOT / ".cache" / "match-v9-all.tsv"
DUMP = ROOT / ".cache" / "anilist-manga-dump.jsonl.gz"
AUTO = ROOT / "data" / "seeds" / "series-merge-auto.json"
HAND = ROOT / "data" / "seeds" / "series-merge.yml"
SUPP = [ROOT / "data" / "seeds" / "volumes-supplement.yml",
        ROOT / "data" / "seeds" / "volumes-supplement-auto.yml"]
OUT = ROOT / ".cache" / "trailing-gaps.csv"
OUT_TRACK = ROOT / "data" / "seeds" / "volumes-trailing.yml"

# 採用 verdict (= 高信頼)
HICONF = {"S180"}


def to_int(s):
    m = re.match(r"^\s*(\d+)\s*$", str(s or ""))
    return int(m.group(1)) if m else None


def main():
    con = sqlite3.connect(DB)
    c = con.cursor()

    # --- series_key → sid (merge_keys 解決に先に必要) ---
    key_sid = {}
    for sid, sk in c.execute("SELECT id, series_key FROM series"):
        key_sid[sk] = sid

    # --- merge group: sid → group sids ---
    # ★schema: _gen-author-set-merges.py は merge_keys(=series_key) を出す(2026-07)。
    #   旧 merge_sids(=sid直) も後方互換で受ける。keys は key_sid で sid 解決。
    def _grp_to_sids(entry):
        if entry.get("merge_keys"):
            return [key_sid[k] for k in entry["merge_keys"] if k in key_sid]
        if entry.get("merge_sids"):
            return [int(s) for s in entry["merge_sids"]]
        return []

    sid_group = {}
    if AUTO.exists():
        for g in json.load(open(AUTO, encoding="utf-8")).get("merges", []):
            grp = _grp_to_sids(g)
            for s in grp:
                sid_group[s] = grp
    if HAND.exists():
        for e in (yaml.safe_load(open(HAND, encoding="utf-8")) or []):
            grp = _grp_to_sids(e)
            for s in grp:
                sid_group[s] = grp

    # --- sid → max standard volume number (db) ---
    sid_maxstd = defaultdict(int)
    for sid, num in c.execute(
        "SELECT e.series_id, v.number FROM volumes v JOIN editions e ON e.id=v.edition_id "
        "WHERE e.type IN ('standard','') AND v.number IS NOT NULL"
    ):
        n = to_int(num)
        if n and n > sid_maxstd[sid]:
            sid_maxstd[sid] = n

    # --- 種4補完の巻も max に反映 (series_keys/qid → sid) ---
    for path in SUPP:
        if not path.exists():
            continue
        for e in (yaml.safe_load(open(path, encoding="utf-8")) or {}).get("volumes", []) or []:
            n = to_int(e.get("number"))
            if not n:
                continue
            sids = set()
            for sk in (e.get("series_keys") or []):
                if sk in key_sid:
                    sids.add(key_sid[sk])
            for sid in sids:
                if n > sid_maxstd[sid]:
                    sid_maxstd[sid] = n

    def work_max(sid):
        grp = sid_group.get(sid, [sid])
        return max((sid_maxstd.get(s, 0) for s in grp), default=0)

    # --- AniList a_id → status (= FINISHED 確実実在 / RELEASING 最新or予告) ---
    a_status = {}
    if DUMP.exists():
        with gzip.open(DUMP, "rt", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                a_status[str(d.get("id"))] = d.get("status")

    # --- v9 TSV を走査 ---
    cands = []
    rows = csv.DictReader(TSV.open(encoding="utf-8"), delimiter="\t")
    n_hi = 0
    for r in rows:
        if r["verdict"] not in HICONF:
            continue
        n_hi += 1
        av = to_int(r.get("a_vols"))
        if not av:
            continue
        sid = key_sid.get(r["s3_key"])
        if sid is None:
            continue
        m = work_max(sid)
        if m == 0:
            continue
        # AniList総巻数 > 種2max = 末尾取込もれ候補 (= 巻 m+1..av が欠け)
        if av > m and (av - m) <= 30:  # 30巻超の差は誤マッチ/別計数の疑い → 除外
            cands.append({
                "title": r["s3_title"], "a_native": r.get("a_native", ""),
                "s2_max": m, "anilist_vols": av, "missing_count": av - m,
                "missing_from": m + 1, "missing_to": av,
                "anilist_status": a_status.get(str(r.get("a_id")), ""),
                "s3_key": r["s3_key"], "a_id": r.get("a_id", ""),
            })

    cands.sort(key=lambda x: (-x["missing_count"], -x["anilist_vols"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "a_native", "anilist_status", "s2_max", "anilist_vols",
                                          "missing_count", "missing_from", "missing_to", "s3_key", "a_id"])
        w.writeheader()
        w.writerows(cands)

    # tracking 用 yml (= 将来 NDL/MADB が追いついたら再訪)。 promote には流さない (= ISBN未確定)。
    OUT_TRACK.write_text(
        "# 末尾取込もれ追跡 (= AniList総巻数 > 種2max、 最新刊がMADB/NDL未取込)。 read-only tracking。\n"
        "# 生成元 _audit-trailing-gaps.py。 status: FINISHED=確実実在 / RELEASING=最新or予告。\n"
        "# ★ISBN未確定のため種4には未登録。 NDL/MADB更新後に再訪 (_seed4-candidates 等で裏取り)。\n"
        + yaml.dump({"trailing": [
            {"title": x["title"], "anilist_status": x["anilist_status"],
             "s2_max": x["s2_max"], "anilist_vols": x["anilist_vols"],
             "missing": f"{x['missing_from']}-{x['missing_to']}", "a_id": x["a_id"]}
            for x in cands]}, allow_unicode=True, sort_keys=False, width=200),
        encoding="utf-8")

    from collections import Counter
    st = Counter(x["anilist_status"] for x in cands)
    print(f"=== 末尾取込もれ検出 (STEP 4) ===")
    print(f"  高信頼マッチ(S180): {n_hi:,}")
    print(f"  ★末尾取込もれ候補 (AniList総巻数 > 種2max): {len(cands):,}")
    print(f"    status: {dict(st)}  (FINISHED=確実実在 / RELEASING=最新or予告)")
    mc = Counter(x["missing_count"] for x in cands)
    print(f"  欠け巻数 分布(上位): {dict(sorted(mc.items())[:6])}")
    print(f"  → {OUT} / {OUT_TRACK}")
    print(f"\n  --- 欠け1巻(=最新刊1冊欠け、 最も確度高い) 上位20 ---")
    one = [x for x in cands if x["missing_count"] == 1]
    print(f"  (欠け1巻 計 {len(one)})")
    for x in one[:20]:
        print(f"    {x['title']!r}  種2max={x['s2_max']} / AniList={x['anilist_vols']}  → {x['missing_from']}巻欠け")


if __name__ == "__main__":
    main()
