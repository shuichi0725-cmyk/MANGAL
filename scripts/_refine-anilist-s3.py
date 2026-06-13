"""⑦ AniList誤リンク S3単独の精緻化(read-only=分類のみ、 適用は別)。
[[anilist_link_quality]] の「S3単独は正当混在=副題一致で精緻化」を実装。

S3シグナル = a_romaji骨格 が kana骨格 の 1.5倍+2 超(題+副題の過剰マッチ)。
精緻化 = kana に **subtitle_kana を足して**再判定:
  - 副題込みでも まだ長すぎ → 別作品/スピンオフ = DROP候補
  - 副題込みなら収まる        → 正当な副題込み正式題     = KEEP
さらに base 不一致(a骨格が kana骨格で始まらない)= 強DROP。

出力 = .cache/s3-refine.tsv(verdict毎)+ 集計。 ★ここでは overrides に書かない。
"""
import csv, re, sys, sqlite3, json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent
S = {"S180", "S150", "S130", "S100"}


def skel(s):
    return re.sub(r"[aeiou\W_]", "", (s or "").lower())


def main():
    # 既に剥がし済(470)の key は対象外
    import yaml
    ovr = yaml.safe_load((ROOT / "data/seeds/anilist-link-overrides.yml").read_text(encoding="utf-8")) or {}
    already = {o["key"] for o in (ovr.get("overrides") or []) if o.get("action") == "drop"}

    # series_key -> subtitle_kana
    con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite")
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    sub_kana = {r[0]: (r[1] or "") for r in con.execute("SELECT series_key, subtitle_kana FROM series")}
    con.close()

    import pykakasi
    kks = pykakasi.kakasi()

    def kana_skel(kana):
        r = "".join(it["hepburn"] for it in kks.convert(re.sub(r"[\s　]", "", kana or "")))
        return skel(r)

    keep, drop, base_mismatch = [], [], []
    with (ROOT / ".cache/match-v14-all.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] not in S or not r.get("a_id"):
                continue
            key = r["s3_key"]
            if key in already:
                continue
            kana = r.get("s3_kana") or ""
            a_romaji = r.get("a_romaji") or ""
            ksk = kana_skel(kana)
            ask = skel(a_romaji)
            if not (ksk and ask and len(ask) > 1.5 * len(ksk) + 2):
                continue  # S3 が立たない=対象外
            # 副題込みで再判定
            sub = sub_kana.get(key, "")
            ksk_full = kana_skel(kana + sub)
            row = (r["verdict"], r["s3_title"][:34], (kana or "")[:20], (sub or "")[:18],
                   a_romaji[:50], r.get("a_id"), key[:56])
            # base 不一致: a骨格の先頭が kana骨格で始まらない(別題)
            if ask[:len(ksk)] != ksk and ksk[:6] not in ask[:max(8, len(ksk)+2)]:
                base_mismatch.append(row); continue
            if len(ask) > 1.5 * len(ksk_full) + 2:
                drop.append(row)      # 副題込みでも長い=別作品
            else:
                keep.append(row)      # 副題で説明可=正当

    out = ROOT / ".cache/s3-refine.tsv"
    with out.open("w", encoding="utf-8") as f:
        f.write("bucket\tverdict\ttitle\tkana\tsubtitle_kana\ta_romaji\ta_id\tkey\n")
        for b, rows in (("DROP", drop), ("BASE_MISMATCH", base_mismatch), ("KEEP", keep)):
            for x in rows:
                f.write(b + "\t" + "\t".join(str(v) for v in x) + "\n")

    print(f"S3単独 精緻化(470既剥がしを除く):")
    print(f"  DROP(副題込みでも別作品): {len(drop):,}")
    print(f"  BASE_MISMATCH(base自体不一致=強DROP): {len(base_mismatch):,}")
    print(f"  KEEP(副題で説明可=正当・温存): {len(keep):,}")
    print(f"→ {out}")
    for label, rows in (("DROP", drop), ("BASE_MISMATCH", base_mismatch), ("KEEP", keep)):
        print(f"\n=== {label} サンプル ===")
        for x in rows[:12]:
            print(f"  {x[1]} 〔{x[2]}+{x[3]}〕 ⇔ {x[4]}")


if __name__ == "__main__":
    main()
