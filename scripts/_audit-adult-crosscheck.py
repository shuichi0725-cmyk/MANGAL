"""v14マッチを使った 種3↔種a アダルト判定 クロスチェック(慎重・調査専用)。

種3(MANGAL)adult判定 = 種2 series.adult_score >= 3(promote が <3 のみ本番採用)。
種a(AniList)adult判定 = dump の isAdult。

4象限を集計し、 2つの食い違いを抽出:
  (A) 種3アダルト漏れ: 種a=adult なのに 種3 score<3
  (B) 逆: 種3=adult(score>=3) なのに 種a=非adult
※仕様差で「間違いと言い切れない」点を理解の上、 判別材料として列挙。

出力: .cache/adult-A-leak.tsv(漏れ) / adult-B-over.tsv(過剰/仕様差)
"""
import csv, gzip, json, sqlite3, sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
S = {"S180", "S150", "S130", "S100"}
TH = 3  # adult_score >= 3 = アダルト


def main():
    # v14 マッチ: s3_key → a_id
    m = {}
    with open(".cache/match-v14-all.tsv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] in S and r["a_id"]:
                m[r["s3_key"]] = r
    print(f"v14 S-tier マッチ: {len(m):,}", flush=True)

    # 種a isAdult: a_id → (isAdult, native)
    a_adult = {}
    with gzip.open(".cache/anilist-manga-dump.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            a_adult[e.get("id")] = bool(e.get("isAdult"))

    # 種2 adult_score: series_key → score
    con = sqlite3.connect(".cache/db-v2.sqlite")
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    score = {sk: sc for sk, sc in con.execute("SELECT series_key, adult_score FROM series")}
    # adult_signals: series_id → signal list (根拠表示用)
    sid2key = {sid: sk for sid, sk in con.execute("SELECT id, series_key FROM series")}
    sig = {}
    for sid, signal, ev in con.execute("SELECT series_id, signal, evidence FROM adult_signals"):
        sig.setdefault(sid2key.get(sid), []).append(signal)
    con.close()

    quad = Counter()
    A_leak, B_over = [], []
    for k, r in m.items():
        aid = int(r["a_id"])
        s3_adult = score.get(k, 0) >= TH
        sa_adult = a_adult.get(aid, False)
        quad[(s3_adult, sa_adult)] += 1
        if sa_adult and not s3_adult:           # (A) 漏れ
            A_leak.append((r, score.get(k, 0)))
        elif s3_adult and not sa_adult:         # (B) 逆
            B_over.append((r, score.get(k, 0), sig.get(k, [])))

    print("\n=== 4象限(種3 score>=3 × 種a isAdult)===")
    print(f"  両方adult        : {quad[(True,True)]:,}")
    print(f"  両方非adult      : {quad[(False,False)]:,}")
    print(f"  ★(A)種3漏れ(種aのみadult): {quad[(False,True)]:,}")
    print(f"  ★(B)種3のみadult(種a非)   : {quad[(True,False)]:,}")

    with open(".cache/adult-A-leak.tsv", "w", encoding="utf-8") as f:
        f.write("s3_title\ts3_authors\ts3_score\ta_native\ta_id\tverdict\n")
        for r, sc in sorted(A_leak, key=lambda x: x[0]["s3_title"]):
            f.write(f"{r['s3_title']}\t{r['s3_authors']}\t{sc}\t{r['a_native']}\t{r['a_id']}\t{r['verdict']}\n")
    with open(".cache/adult-B-over.tsv", "w", encoding="utf-8") as f:
        f.write("s3_title\ts3_authors\ts3_score\tsignals\ta_native\ta_id\n")
        for r, sc, sg in sorted(B_over, key=lambda x: -x[1]):
            f.write(f"{r['s3_title']}\t{r['s3_authors']}\t{sc}\t{','.join(set(sg))}\t{r['a_native']}\t{r['a_id']}\n")
    print(f"\nwrote .cache/adult-A-leak.tsv ({len(A_leak)}) / adult-B-over.tsv ({len(B_over)})")


if __name__ == "__main__":
    main()
