"""AniList enrich map = 種3↔種a productionization の本番出力用 join データ。

match-v14(series_key→a_id)+ dump(synonyms/genres/tags)→
  {series_key: {anilist_id, synonyms, genres_anilist, tags}}。
promote が join して本番 yml に出力(本番schema lib/schema.ts の箱を埋める)。
★種3は不変(promote-join 方式、 adult_us と同じ。 match更新で常に最新)。

tags filter(案2): category==Demographic(全) OR Theme rank>=60 OR
  Cast/Setting rank>=70。
synonyms filter: latin/CJK/hangul のみ(arabic/thai 等の不要スクリプト除外)。
"""
import csv, gzip, json, re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
MATCH = Path(".cache/match-v14-all.tsv")
DUMP = Path(".cache/anilist-manga-dump.jsonl.gz")
OUT = Path(".cache/anilist-enrich-map.json")
OVERRIDES = Path("data/seeds/anilist-link-overrides.yml")  # ★誤リンク剥がし(純粋追加seed)
S = {"S180", "S150", "S130", "S100"}


def load_link_overrides():
    """anilist-link-overrides.yml → (drop集合, relink辞書 key→to_id)。
    drop=enrichから除外 / relink=a_id を本編idへ付け替え。"""
    drops, relinks = set(), {}
    if not OVERRIDES.exists():
        return drops, relinks
    import yaml
    doc = yaml.safe_load(OVERRIDES.read_text(encoding="utf-8")) or {}
    for o in (doc.get("overrides") or []):
        if not isinstance(o, dict) or not o.get("key"):
            continue
        if o.get("action") == "drop":
            drops.add(o["key"])
        elif o.get("action") == "relink" and o.get("to_id"):
            relinks[o["key"]] = int(o["to_id"])
    return drops, relinks

USEFUL = re.compile(r"[A-Za-z0-9一-鿿぀-ヿ가-힣]")  # latin/CJK/かな/hangul


def syn_ok(s):
    """latin/CJK/hangul が過半の synonym のみ採用(arabic/thai 等の不要スクリプト除外)。"""
    if not s:
        return False
    core = re.sub(r"[\s　・:：!！?？.,'\"\-–—()（）\[\]【】]", "", s)
    if not core:
        return False
    return len(USEFUL.findall(core)) >= len(core) * 0.6


def tag_keep(t):
    cat = t.get("category") or ""
    rank = t.get("rank") or 0
    if t.get("isAdult"):  # adult tag は除外(別途 adult_us 管理)
        return False
    if "Demographic" in cat:
        return True
    if cat == "Theme" and rank >= 60:
        return True
    if cat in ("Cast", "Setting") and rank >= 70:
        return True
    return False


def main():
    # series_key → a_id (S-tier)
    sk_aid = {}
    with MATCH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] in S and r["a_id"]:
                sk_aid[r["s3_key"]] = int(r["a_id"])
    base_n = len(sk_aid)
    # ★recovery(強正規化×著者ゲート、 _match-recover-norm.py)を追加読み(既存優先)
    rec = Path(".cache/match-recovery.tsv")
    rec_added = 0
    if rec.exists():
        with rec.open(encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                if r.get("a_id") and r["s3_key"] not in sk_aid:
                    sk_aid[r["s3_key"]] = int(r["a_id"]); rec_added += 1
    # ★著者経由recall exact(⑥、 _match-recall-authorroute-apply.py)を追加読み(既存優先)
    ar = Path(".cache/match-recall-authorroute.tsv")
    ar_added = 0
    if ar.exists():
        with ar.open(encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                if r.get("a_id") and r["s3_key"] not in sk_aid:
                    sk_aid[r["s3_key"]] = int(r["a_id"]); ar_added += 1
    print(f"  base(v14 S-tier): {base_n:,} + recovery追加: {rec_added:,} + 著者recall: {ar_added:,}", file=sys.stderr)
    # ★誤リンク override: relink=本編idへ付替(優先) / drop=enrich除外
    drop_keys, relink_keys = load_link_overrides()
    relinked = 0
    for k, to_id in relink_keys.items():
        if k in sk_aid and sk_aid[k] != to_id:
            sk_aid[k] = to_id; relinked += 1
        elif k not in sk_aid:
            sk_aid[k] = to_id; relinked += 1   # 未マッチでも本編へ結線
    dropped = 0
    for k in list(sk_aid):
        if k in drop_keys and k not in relink_keys:
            del sk_aid[k]; dropped += 1
    print(f"  ★誤リンクrelink: {relinked:,} / drop: {dropped:,} (anilist-link-overrides.yml)", file=sys.stderr)
    # a_id → enrich
    need = set(sk_aid.values())
    aid_enrich = {}
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            i = e.get("id")
            if i not in need:
                continue
            syns = [s for s in (e.get("synonyms") or []) if syn_ok(s)][:8]
            genres = e.get("genres") or []
            tags = [{"name": t.get("name"), "category": t.get("category"), "rank": t.get("rank") or 0}
                    for t in (e.get("tags") or []) if isinstance(t, dict) and tag_keep(t)]
            tags = sorted(tags, key=lambda x: -x["rank"])[:12]
            aid_enrich[i] = {"anilist_id": i, "synonyms": syns,
                             "genres_anilist": genres, "tags": tags}
    out = {sk: aid_enrich[aid] for sk, aid in sk_aid.items() if aid in aid_enrich}
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    # stats
    n = len(out)
    sy = sum(1 for v in out.values() if v["synonyms"])
    ge = sum(1 for v in out.values() if v["genres_anilist"])
    tg = sum(1 for v in out.values() if v["tags"])
    print(f"v14 S-tier マッチ: {len(sk_aid):,}")
    print(f"★enrich map: {n:,} series_key")
    print(f"  synonyms有: {sy:,} / genres_anilist有: {ge:,} / tags有: {tg:,}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
