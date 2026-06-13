"""⑦ S3誤リンクの relations ベース精密判定(read-only=分類のみ)。
ローマ字骨格は短題/ラテン題で不安定(H・E/ソード)→ **日本語native題で直接照合**。

各S3疑惑(470既剥がしを除く)について a_id の franchise(relations の MANGA ノード)を見て:
  - RELINK: 兄弟に 我々の題と native完全一致 があり 現a_id と異なる(=正しい巻を発見)
  - DROP:   a_id native も 兄弟 native も 我々の題と全く一致しない(=無関係リンク)
  - LEAVE:  上記以外(接頭辞曖昧=ペルソナ2型 等)は触らない(誤操作回避)
出力 = .cache/s3-relink.tsv + 集計。 ★overrides には書かない(検証後に別途)。
"""
import csv, gzip, json, re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent
S = {"S180", "S150", "S130", "S100"}


def norm_ja(s):
    s = s or ""
    s = re.sub(r"[(（〈《\[【「『].*?[)）〉》\]】」』]", "", s)  # 括弧内(読み注記等)除去
    s = re.sub(r"[\s　・:：;；!！?？.,。、'\"\-–—~〜=＝/／*＊\.]", "", s)
    return s.lower()


def main():
    # ★470 も対象に含める(drop より relink=本編復活 を優先したいため除外しない)
    # v3 dump: id -> (native, romaji, format, popularity, relations[(id,type,native)])
    meta = {}
    with gzip.open(ROOT / ".cache/anilist-manga-dump-v3.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            t = d.get("title") or {}
            rels = []
            for e in (d.get("relations") or {}).get("edges", []):
                nd = e.get("node") or {}
                nt = (nd.get("title") or {})
                rels.append((nd.get("id"), nd.get("type"), nt.get("native"), nt.get("romaji"), nd.get("format")))
            meta[d["id"]] = {"native": t.get("native"), "romaji": t.get("romaji"),
                             "format": d.get("format"), "pop": d.get("popularity") or 0, "rels": rels}

    def score(our_n, cand):
        c = norm_ja(cand or "")
        if not c or not our_n:
            return 0
        if c == our_n:
            return 100
        # 接頭辞だが直後が数字=別ナンバリング(ペルソナ2型)は加点しない
        if c.startswith(our_n):
            tail = c[len(our_n):]
            return 30 if tail[:1].isdigit() else 60
        if our_n.startswith(c):
            return 55
        if c in our_n or our_n in c:
            return 40
        return 0

    relink, drop, leave = [], [], []
    relink_map = {}
    with (ROOT / ".cache/match-v14-all.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] not in S or not r.get("a_id"):
                continue
            key = r["s3_key"]
            try:
                aid = int(r["a_id"])
            except ValueError:
                continue
            m = meta.get(aid)
            if not m:
                continue
            # S3 が立つものだけ(a_romaji が長い)
            ask = re.sub(r"[aeiou\W_]", "", (r.get("a_romaji") or "").lower())
            our_kana = re.sub(r"[\s　]", "", r.get("s3_kana") or "")
            if not (ask and our_kana):
                continue
            our_n = norm_ja(r["s3_title"])
            if not our_n:
                continue
            cur = score(our_n, m["native"])
            # franchise の MANGA 兄弟(自身含む)
            cands = [(aid, m["native"], m["pop"])]
            for (rid, rtype, rnat, rrom, rfmt) in m["rels"]:
                if rtype == "MANGA" and rid:
                    cands.append((rid, rnat, meta.get(rid, {}).get("pop", 0)))
            # 各候補の score(native)
            scored = [(score(our_n, nat), pop, rid, nat) for (rid, nat, pop) in cands]
            scored.sort(key=lambda x: (-x[0], -x[1]))
            best_sc, best_pop, best_id, best_nat = scored[0]
            row = (r["s3_title"][:30], (m["native"] or "")[:28], cur,
                   best_sc, (best_nat or "")[:28], aid, best_id, key[:54])
            if best_sc >= 100 and best_id != aid:
                relink.append(row)            # 兄弟に完全一致=正しい巻
                relink_map[key] = best_id     # ★full key で記録
            elif best_sc == 0:
                drop.append(row)              # a_idも兄弟も無関係=誤リンク
            else:
                leave.append(row)             # 曖昧=触らない

    out = ROOT / ".cache/s3-relink.tsv"
    with out.open("w", encoding="utf-8") as f:
        f.write("our_title\ta_native\tcur_score\tbest_score\tbest_native\ta_id\tbest_id\tkey\n")
        for b, rows in (("RELINK", relink), ("DROP", drop), ("LEAVE", leave)):
            for x in rows:
                f.write(b + "\t" + "\t".join(str(v) for v in x) + "\n")

    # ★relink map(full key → to_id)= 採用する唯一の高精度アクション。 DROPバケツは破棄(誤判定多)。
    mp = ROOT / ".cache/s3-relink-map.json"
    mp.write_text(json.dumps(relink_map, ensure_ascii=False), encoding="utf-8")

    print(f"S3 relations精密判定:")
    print(f"  RELINK(兄弟に完全一致=正しい巻へ付替): {len(relink):,} → {mp}")
    print(f"  DROP(★破棄=ラテンvsカナ/記号で誤判定多): {len(drop):,}")
    print(f"  LEAVE(曖昧=触らない): {len(leave):,}")
    print(f"→ {out}")
    for label, rows in (("RELINK", relink), ("DROP", drop)):
        print(f"\n=== {label} サンプル ===")
        for x in rows[:14]:
            print(f"  「{x[0]}」 a={x[1]}(sc{x[2]}) → best={x[4]}(sc{x[3]}) [{x[5]}→{x[6]}]")


if __name__ == "__main__":
    main()
