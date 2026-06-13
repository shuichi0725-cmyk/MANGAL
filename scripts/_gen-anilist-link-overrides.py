"""AniList誤リンクの override seed を生成(純粋追加方式、 adult-overrides と同じ哲学)。
[[anilist_link_quality]]。 2アクション:

  relink : franchise兄弟に native完全一致(_relink-anilist-s3.py の s3-relink-map.json)
           → 正しい巻(本編)へ a_id 付け替え。 ★dropより優先(本編のあらすじ復活)。
  drop   : 高確信誤り(S1読切/S2巻数乖離/S4章数僅少 or 複数シグネチャ)で
           relink先が無いもの → enrich から除外(誤あらすじ消滅)。

入力 = .cache/anilist-link-suspects.tsv + .cache/s3-relink-map.json。
★S3単独で relink できない曖昧分は触らない(LEAVE。 stripはラテンvsカナ誤判定多で不採用)。
"""
import csv, json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent
SUS = ROOT / ".cache" / "anilist-link-suspects.tsv"
RELINK = ROOT / ".cache" / "s3-relink-map.json"
OUT = ROOT / "data" / "seeds" / "anilist-link-overrides.yml"


def main():
    relink_map = json.loads(RELINK.read_text(encoding="utf-8")) if RELINK.exists() else {}

    # 高確信drop候補 = S3単独でない suspect(S1/S2/S4 を含む or 複数シグネチャ)
    drop_keys = {}
    with SUS.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            sigs = [s for s in r["signals"].split("|") if s]
            if sigs == ["S3_romaji_tail"]:
                continue
            drop_keys[r["key"]] = {"a_id": r["a_id"], "signals": r["signals"], "title": r["title"]}

    # relink が優先: drop候補でも relink先があれば relink(本編復活)
    relink_entries = []
    for key, to_id in relink_map.items():
        relink_entries.append((key, int(to_id)))
    drop_entries = [(k, v) for k, v in drop_keys.items() if k not in relink_map]

    lines = [
        "# AniList誤リンク override(自動生成 _gen-anilist-link-overrides.py)。",
        "# relink: franchise本編へ a_id 付け替え(native完全一致で確証)。",
        "# drop:   高確信誤り(S1/S2/S4 or 複数シグネチャ)で relink先無し → enrich除外。",
        "# ★S3単独の曖昧分は触らない(stripはラテンvsカナ誤判定が多いため不採用)。",
        "overrides:",
    ]
    for key, to_id in sorted(relink_entries):
        kq = json.dumps(key, ensure_ascii=False)
        lines.append(f"  - {{key: {kq}, action: relink, to_id: {to_id}}}")
    for key, meta in sorted(drop_entries):
        kq = json.dumps(key, ensure_ascii=False)
        sq = json.dumps(meta["signals"], ensure_ascii=False)
        tq = json.dumps(meta["title"], ensure_ascii=False)
        aid = meta["a_id"] or "null"
        lines.append(f"  - {{key: {kq}, action: drop, a_id: {aid}, signals: {sq}, title: {tq}}}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"relink(本編へ付替): {len(relink_entries):,}")
    print(f"drop(relink先無しの高確信誤り): {len(drop_entries):,}")
    print(f"  (relink優先で drop から救済: {len(drop_keys) - len(drop_entries):,})")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
