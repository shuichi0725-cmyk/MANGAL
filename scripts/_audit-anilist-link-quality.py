"""AniListリンク精度の規模測定(★読み取りのみ・修正なし。 2026-06-12 ユーザ指示「測定だけ慎重に」)。

対象 = match-v14 の S判定(enrichに流れる集合)。 誤リンクの機械シグネチャを数える:
  S1 one_shot   : AniList format が ONE_SHOT なのに 種2巻数 >= 2(読切を本編に割当=bardock型)
  S2 vols_gap   : AniList volumes >= 1 かつ 種2巻数 >= max(5, 4×a_vols)(規模の大乖離)
  S3 romaji_tail: a_romaji の子音骨格が kana より大幅に長い(題+副題の過剰マッチ、slug長さガードと同条件)
  S4 few_chaps  : format MANGA だが chapters <= 6 で 種2巻数 >= 3
被害面: シグネチャhitのうち synopsis-ja.json に和訳が存在する(=あらすじ誤表示が実際に出る)件数。
出力: .cache/anilist-link-suspects.tsv + 集計。
"""
import csv
import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent
S = {"S180", "S150", "S130", "S100"}


def skel(s):
    return re.sub(r"[aeiou\W_]", "", (s or "").lower())


def main():
    # AniList dump: id -> (format, volumes, chapters, popularity)
    meta = {}
    with gzip.open(ROOT / ".cache/anilist-manga-dump-v3.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            meta[str(d["id"])] = (d.get("format"), d.get("volumes"), d.get("chapters"), d.get("popularity") or 0)

    syn = json.loads((ROOT / "data/seeds/synopsis-ja.json").read_text(encoding="utf-8"))

    import pykakasi
    kks = pykakasi.kakasi()

    def kana_skel(kana):
        r = "".join(it["hepburn"] for it in kks.convert(kana or ""))
        return skel(r)

    rows = []
    st = Counter()
    n_s = 0
    with (ROOT / ".cache/match-v14-all.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] not in S:
                continue
            n_s += 1
            aid = r.get("a_id") or ""
            fmt, a_vols, a_chaps, pop = meta.get(aid, (None, None, None, 0))
            try:
                s3v = int(r.get("s3_vols") or 0)
            except ValueError:
                s3v = 0
            sigs = []
            if fmt == "ONE_SHOT" and s3v >= 2:
                sigs.append("S1_one_shot")
            if a_vols and s3v >= max(5, 4 * a_vols):
                sigs.append("S2_vols_gap")
            ksk = kana_skel(re.sub(r"[\s　]", "", r.get("s3_kana") or ""))
            ask = skel(r.get("a_romaji") or "")
            if ksk and ask and len(ask) > 1.5 * len(ksk) + 2:
                sigs.append("S3_romaji_tail")
            if fmt == "MANGA" and a_chaps and a_chaps <= 6 and s3v >= 3:
                sigs.append("S4_few_chaps")
            if not sigs:
                continue
            has_syn = aid in syn
            for sg in sigs:
                st[sg] += 1
            st["pages_hit"] += 1
            if has_syn:
                st["synopsis_visible"] += 1
            rows.append((r["verdict"], "|".join(sigs), "syn" if has_syn else "",
                         r["s3_title"][:36], f"v{s3v}", f"a:{fmt}/{a_vols}v/{a_chaps}c",
                         (r.get("a_romaji") or "")[:46], aid, r["s3_key"][:60]))

    out = ROOT / ".cache/anilist-link-suspects.tsv"
    with out.open("w", encoding="utf-8") as f:
        f.write("verdict\tsignals\tsynopsis\ttitle\ts3_vols\tanilist\ta_romaji\ta_id\tkey\n")
        for x in rows:
            f.write("\t".join(str(v) for v in x) + "\n")

    print(f"S判定総数: {n_s:,}")
    print(f"疑惑hit: {st['pages_hit']:,} 行 ({st['pages_hit']*100/max(n_s,1):.1f}%)")
    for k in ("S1_one_shot", "S2_vols_gap", "S3_romaji_tail", "S4_few_chaps"):
        print(f"  {k}: {st[k]:,}")
    print(f"  ★うち synopsis 和訳あり(=あらすじ誤表示が実際に出る): {st['synopsis_visible']:,}")
    print(f"→ {out}")
    print("\n=== サンプル(複数シグネチャ優先) ===")
    rows.sort(key=lambda x: -len(x[1].split("|")))
    for x in rows[:15]:
        print(f"  [{x[1]}]{'[syn]' if x[2] else ''} {x[3]} ({x[4]}) ⇔ {x[5]} | {x[6]}")


if __name__ == "__main__":
    main()
