"""A = S180 誤マッチ率の調査。 corroboration 強度でリスク分類し、 高リスク群を抽出。

S180(score>=180)は base100 + 加点で到達。 「何で180に達したか」で信頼度が違う:
  - 著者照合(author_match/keyauthor_match) or en_match で達した = 強い裏取り
  - title channel + year/vol だけで達した = 同名異作品の取り違えリスク
  - author_MISMATCH を含むのに180 = 最も危険(著者が食い違うのに題/年で押し切った)

出力: リスク別件数 + 高リスクサンプルを .cache/s180-fp-*.tsv に。
"""
import csv, sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
TSV = Path(".cache/match-v9-all.tsv")


def main():
    rows = []
    with TSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] == "S180":
                rows.append(r)
    n = len(rows)
    print(f"S180 総数: {n:,}")

    cat = Counter()
    risk_mismatch, risk_noauthor, risk_yearvol = [], [], []
    for r in rows:
        reason = r["reason"]
        has_author = ("author_match" in reason) or ("keyauthor_match" in reason)
        has_en = "en_match" in reason
        has_mismatch = "author_MISMATCH" in reason
        if has_mismatch:
            cat["R1_author_MISMATCH(最危険)"] += 1
            risk_mismatch.append(r)
        elif not has_author and not has_en:
            cat["R2_著者/en裏取り無し(題+年/巻のみ)"] += 1
            risk_noauthor.append(r)
        else:
            cat["SAFE(著者orEn裏取り有)"] += 1
        # 年/巻ズレも別軸で
        if ("year_diff=" in reason and not reason.count("year_exact")) or "!" in reason:
            risk_yearvol.append(r)

    print("\n=== corroboration リスク分類 ===")
    for k, v in cat.most_common():
        print(f"  {k}: {v:,} ({v*100//n}%)")
    print(f"\n  (補助) 年/巻に乖離痕跡あり: {len(risk_yearvol):,}")

    # 高リスク群を書き出し(読みやすい列だけ)
    cols = ["score", "reason", "s3_title", "s3_authors", "s3_year", "s3_vols",
            "a_native", "a_romaji", "a_authors", "a_year", "a_vols"]

    def dump(rows, path):
        with Path(path).open("w", encoding="utf-8") as f:
            f.write("\t".join(cols) + "\n")
            for r in rows:
                f.write("\t".join(str(r.get(c, "")) for c in cols) + "\n")

    dump(risk_mismatch, ".cache/s180-fp-R1-mismatch.tsv")
    dump(risk_noauthor, ".cache/s180-fp-R2-noauthor.tsv")
    print(f"\nwrote .cache/s180-fp-R1-mismatch.tsv ({len(risk_mismatch)})")
    print(f"wrote .cache/s180-fp-R2-noauthor.tsv ({len(risk_noauthor)})")


if __name__ == "__main__":
    main()
