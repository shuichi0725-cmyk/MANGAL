"""#2b imprint バグ調査 = 別の display 題が同一 slug に潰れる群を抽出。

仮説: title_kana(フリガナ)が作品名でなく レーベル/シリーズ名 で埋まっている →
kana 起点 slug が別作品で同一化。 衝突を 2 分類:
  - 正当同名: display 題がほぼ同一(日本の歴史×31)→ suffix で解決
  - ★imprint疑い: display 題が相異なるのに kana(=slug)が同一 → kana データ不正
出力: .cache/slug-imprint-suspect.tsv + stdout。 ※調査のみ。
"""
import pickle, csv, re, sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
PKL = Path(".cache/seed3-promote.pkl")
CHOSEN = Path(".cache/slug-chosen.tsv")


def base_title(key):
    ns = [p[5:] for p in key.split("|") if p.startswith("name:")]
    return ns[-1] if ns else ""


def norm_disp(t):
    return re.sub(r"[\s　・！!？?、。「」『』〜~ー\-—–:：/／]+", "", t).lower()


def main():
    d = pickle.load(PKL.open("rb"))
    kana = {e["key"]: (e.get("title_kana") or "") for e in d.values()}

    by_slug = defaultdict(list)  # slug → [(key, title)]
    with CHOSEN.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["slug"]:
                by_slug[r["slug"]].append((r["key"], r["title"]))

    genuine = imprint = 0
    suspects = []
    for slug, members in by_slug.items():
        if len(members) < 2:
            continue
        disps = {norm_disp(t) for _, t in members}
        if len(disps) == 1:
            genuine += 1   # 同一 display 題 = 正当同名
        else:
            imprint += 1   # 別題が同一 slug = kana 不正疑い
            # この群の kana(同一のはず)と各 display を記録
            ks = {kana.get(k, "") for k, _ in members}
            suspects.append((slug, len(members), len(disps),
                             " | ".join(sorted(ks))[:40],
                             " || ".join(t for _, t in members[:5])))

    print(f"衝突 slug 種類: {genuine + imprint:,}")
    print(f"  正当同名(display一致): {genuine:,}")
    print(f"  ★別題が同一slug(kana不正疑い): {imprint:,}")
    suspects.sort(key=lambda x: -x[1])
    print(f"\n=== imprint疑い top25(slug, 件数, 異題数, kana, titles)===")
    for slug, n, nd, ks, titles in suspects[:25]:
        print(f"  [{n:>3}] {slug[:26]:<26} kana=[{ks[:22]}] {titles[:46]}")
    with open(".cache/slug-imprint-suspect.tsv", "w", encoding="utf-8") as f:
        f.write("slug\tmembers\tdistinct_titles\tkana\tsample_titles\n")
        for slug, n, nd, ks, titles in suspects:
            f.write(f"{slug}\t{n}\t{nd}\t{ks}\t{titles}\n")
    affected = sum(n for _, n, _, _, _ in suspects)
    print(f"\n★imprint疑いに巻き込まれた entry: {affected:,}")
    print("wrote .cache/slug-imprint-suspect.tsv")


if __name__ == "__main__":
    main()
