"""draft-2000 yml の 巻数 anomaly 自動 scan (= I1-I6)。

検出項目:
  I1. 巻号 飛び 多い (= missing 率 > 20%)
  I2. edition 異常多 (= 6+ editions)
  I3. 巻数 極端 (= 1 巻 or 300+ 巻)
  I4. 連載期間 vs 巻数 矛盾 (= 期間/巻 ratio が 異常)
  I5. slug 衝突 残り (= '-2', '-3' suffix)
  I6. 特殊 vol_label 残り (= 番号化できない label)

出力: TSV format に flag 列 ['slug','title','vols','editions','year','flags']
"""

import yaml
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFT = ROOT / "data" / "manga.draft-2000"


def main() -> None:
    results = []
    for p in sorted(DRAFT.glob("*.yml")):
        with p.open("r", encoding="utf-8") as f:
            d = yaml.safe_load(f)
        slug = p.stem
        title = d.get("title", "")
        editions = d.get("editions", [])
        year_started = d.get("year_started")
        year_ended = d.get("year_ended")

        all_vols: set[int] = set()
        special_labels: list[str] = []
        for ed in editions:
            for v in ed["volumes"]:
                if v.get("number"):
                    all_vols.add(v["number"])
                if v.get("volume_label"):
                    special_labels.append(v["volume_label"])
        vol_count = len(all_vols)
        max_vol = max(all_vols) if all_vols else 0
        flags = []

        # I1: 飛び 多い
        if max_vol > 0:
            missing = max_vol - vol_count
            miss_rate = missing / max_vol
            if miss_rate > 0.2 and missing >= 3:
                flags.append(f"I1:miss{missing}/{max_vol}({miss_rate*100:.0f}%)")

        # I2: edition 異常多
        if len(editions) >= 6:
            flags.append(f"I2:ed{len(editions)}")

        # I3: 巻数 極端
        if vol_count == 1:
            flags.append("I3:1vol")
        elif vol_count >= 200:
            flags.append(f"I3:{vol_count}vols")

        # I4: 連載期間 vs 巻数 矛盾
        if year_started and year_ended:
            period = year_ended - year_started + 1
            if period > 0 and vol_count > 0:
                vols_per_year = vol_count / period
                if vols_per_year > 20:
                    flags.append(f"I4:speed({vol_count}/{period}y={vols_per_year:.1f}/y)")
                if vols_per_year < 0.2 and period >= 5:
                    flags.append(f"I4:slow({vol_count}/{period}y={vols_per_year:.2f}/y)")

        # I5: slug -N suffix
        import re
        m = re.match(r".+-(\d+)$", slug)
        if m and int(m.group(1)) <= 9:
            flags.append(f"I5:suffix-{m.group(1)}")

        # I6: 特殊 vol_label 残り (= 漢字 + 「巻」 / 副題系)
        suspicious_labels = [l for l in special_labels if not re.match(r"^第?\d+巻?$", l or "")]
        if suspicious_labels:
            sample = suspicious_labels[0][:30]
            flags.append(f"I6:label({len(suspicious_labels)})({sample})")

        if flags:
            results.append({
                "slug": slug,
                "title": title,
                "vols": vol_count,
                "max_vol": max_vol,
                "editions": len(editions),
                "year": f"{year_started}-{year_ended or '?'}",
                "flags": flags,
            })

    # Sort by flag count desc
    results.sort(key=lambda x: (-len(x["flags"]), -x["vols"]))

    # Output TSV
    print(f"{'slug':<40}\t{'title':<25}\t{'vols':>5}\t{'max':>4}\t{'ed':>3}\t{'year':<12}\tflags")
    print("-" * 130)
    for r in results:
        flags_str = " | ".join(r["flags"])
        print(f"{r['slug'][:40]:<40}\t{r['title'][:25]:<25}\t{r['vols']:>5}\t{r['max_vol']:>4}\t{r['editions']:>3}\t{r['year']:<12}\t{flags_str}")

    # Summary
    print(f"\n--- summary ---", file=sys.stderr)
    print(f"total flagged: {len(results)} / {len(list(DRAFT.glob('*.yml')))}", file=sys.stderr)
    from collections import Counter
    flag_counter: Counter = Counter()
    for r in results:
        for f in r["flags"]:
            flag_counter[f.split(":")[0]] += 1
    for k, v in flag_counter.most_common():
        print(f"  {k}: {v}", file=sys.stderr)


if __name__ == "__main__":
    main()
