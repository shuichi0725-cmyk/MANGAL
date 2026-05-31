"""種a isAdult を第5 signal に union した場合の差分を実測(プロトタイプ・調査専用)。

新方式: adult = 現状(adult_score>=3、 override除外)OR 種a isAdult(v14マッチ)。
現方式との差分(新規adult化)を 種a genre/tag で分類して、 米基準採用の影響を見る。
★db/adult_score 不変。 計算のみ。
"""
import sqlite3, csv, gzip, json, sys, yaml, re
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def main():
    con = sqlite3.connect(".cache/db-v2.sqlite")
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    score = {sk: (sc or 0) for sk, sc in con.execute("SELECT series_key, adult_score FROM series")}
    title = {sk: (t or sk) for sk, t in con.execute("SELECT series_key, title FROM series")}
    con.close()

    ovr = set()
    for o in (yaml.safe_load(open("data/seeds/adult-overrides.yml", encoding="utf-8")) or {}).get("overrides", []):
        if o.get("force_adult") is False:
            ovr.add(o["series_key"])

    # 現方式 adult
    cur_adult = {sk for sk, sc in score.items() if sc >= 3 and sk not in ovr}

    # v14 マッチ: series_key → a_id
    m = {}
    with open(".cache/match-v14-all.tsv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"].startswith("S") and r["a_id"]:
                m[r["s3_key"]] = int(r["a_id"])

    # 種a: a_id → (isAdult, genres, tags)
    need = set(m.values())
    ainfo = {}
    with gzip.open(".cache/anilist-manga-dump.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e.get("id") in need:
                tags = [t.get("name") if isinstance(t, dict) else t for t in (e.get("tags") or [])]
                ainfo[e["id"]] = (bool(e.get("isAdult")), e.get("genres") or [], tags)

    # 種a isAdult な series
    ani_adult = {sk for sk, aid in m.items() if ainfo.get(aid, (False, [], []))[0]}

    new_adult = cur_adult | ani_adult
    delta = ani_adult - cur_adult        # 種aで新規 adult 化
    recovered_unmatched = cur_adult & ani_adult  # 両方一致(確認)

    print(f"=== 現方式 vs 新方式(種a union)===")
    print(f"  現 adult: {len(cur_adult):,}")
    print(f"  種a isAdult(マッチ済): {len(ani_adult):,}")
    print(f"  新 adult(union): {len(new_adult):,}")
    print(f"  ★種aで新規 adult化(差分): {len(delta):,}")

    # 差分を 種a genre で分類
    def cls(aid):
        _, g, t = ainfo.get(aid, (False, [], []))
        s = " ".join([str(x) for x in g] + [str(x) for x in t])
        if re.search(r"Yaoi|Boys.?Love", s): return "BL"
        if re.search(r"Yuri|Girls.?Love", s): return "百合"
        if "Hentai" in s: return "Hentai(露骨)"
        if "Ecchi" in s: return "Ecchi"
        return "その他"
    cat = Counter(cls(m[sk]) for sk in delta)
    print(f"\n=== 新規adult化 {len(delta)} の 種a分類 ===")
    for k, v in cat.most_common():
        print(f"  {k}: {v:,}")

    # サンプル(分類別)
    print(f"\n=== 分類別サンプル ===")
    seen = Counter()
    for sk in sorted(delta, key=lambda k: str(title.get(k, k))):
        c = cls(m[sk])
        if seen[c] < 4:
            seen[c] += 1
            print(f"  [{c}] {str(title.get(sk, sk))[:30]}")

    # FN救済: 現状漏れてた explicit(Hentai)が何件拾えたか
    hentai_recover = [sk for sk in delta if "Hentai" in " ".join(str(x) for x in ainfo.get(m[sk], (0, [], []))[1])]
    print(f"\n★FN救済(現状漏れ→Hentaiで新規adult): {len(hentai_recover):,}")


if __name__ == "__main__":
    main()
