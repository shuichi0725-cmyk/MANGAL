"""対象読者(demographic)の調査一覧を作る(2026-11-27 ユーザ裁定「表を作って後から調査して変更する仕組み」)。

読み取り専用。本番 data/manga.v2 の各頁について
  - 今の値と、その値の出どころ(種3=5月AI一括 / 対応表で充填 / realign / edition-overrides / 出どころ不明)
  - 根拠: レーベル(imprint-demographic.yml labels) / 連載誌(magazines.yml) / 出版社(publishers_without_imprint)
を突き合わせ、調べるべき頁だけを TSV に出す。

出力:
  docs/production-diagnostics/demographic-worklist.tsv   (調査対象の頁)
  docs/production-diagnostics/demographic-worklist-summary.json (件数)

kind(調査の種類):
  empty     = 値が空
  conflict  = 今の値と根拠が食い違う(realign / overrides で確定済みの頁は除く)
  unsourced = 値は在るが、種3にも根拠にも出どころが無い(旧 promote の shounen 既定の名残)
案(proposal):
  根拠が1つの値に揃えば その値 / 割れたら「割れ」 / 何も無ければ「根拠なし」

使い方: python scripts/_demographic-worklist.py
結果を seed へ書くのは別工程(imprint-demographic.yml の realign へ、ユーザ裁定の後)。
"""
import glob
import json
import os
import pickle
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import yaml

try:
    from yaml import CSafeLoader as _L
except ImportError:
    from yaml import SafeLoader as _L

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT_TSV = ROOT / "docs" / "production-diagnostics" / "demographic-worklist.tsv"
OUT_SUM = ROOT / "docs" / "production-diagnostics" / "demographic-worklist-summary.json"
LABEL_JA = {"shounen": "少年", "shoujo": "少女", "seinen": "青年", "josei": "女性", "kodomo": "子ども"}


def norm_label(x):
    """_promote-bulk-v2.py の _norm_label_for_demo と同じ式。"""
    x = unicodedata.normalize("NFKC", str(x or "")).strip().strip("'\"")
    x = re.sub(r"\s+", " ", x)
    x = re.sub(r"[\s]*[\d]+$", "", x)
    w = x.split(" ")
    if len(w) >= 2 and w[0] == w[1]:
        x = w[0]
    x = re.sub(r" (CM|CMK|C)$", "", x)
    return x.strip()


def yl(p):
    with open(p, encoding="utf-8") as f:
        return yaml.load(f, Loader=_L)


def load_seed3_demo():
    pk = ROOT / ".cache" / "seed3-promote.pkl"
    if pk.exists():
        with pk.open("rb") as f:
            d = pickle.load(f)
        return {k: (v or {}).get("demographic") for k, v in d.items()}
    d = yl(ROOT / "data" / "seeds" / "series-supplement-v2.yml")
    return {e["key"]: e.get("demographic") for e in d["series"]}


def main():
    seed = yl(ROOT / "data" / "seeds" / "imprint-demographic.yml")
    labels = seed.get("labels") or {}
    pubs = seed.get("publishers_without_imprint") or {}
    realign = seed.get("realign") or {}
    mags = {k: (v or {}).get("demographic") for k, v in (yl(ROOT / "data" / "magazines.yml") or {}).items()}
    eov = json.load(open(ROOT / "data" / "seeds" / "edition-overrides.json", encoding="utf-8"))
    eov_demo = {k for k, v in eov.items() if isinstance(v, dict) and v.get("demographic")}
    s3 = load_seed3_demo()

    rows, kinds, origins, cur_c = [], Counter(), Counter(), Counter()
    skey_re = re.compile(r"^_skey:\s*(.+)$", re.M)
    files = sorted(glob.glob(str(ROOT / "data" / "manga.v2" / "*.yml")))
    for i, fp in enumerate(files):
        if i and i % 10000 == 0:
            print(f"  {i}/{len(files)}", file=sys.stderr)
        stem = os.path.basename(fp)[:-4]
        d = yl(fp) or {}
        slug = d.get("slug") or stem
        cur = d.get("demographic") or ""
        if cur == "other":
            cur = ""
        cur_c[cur or "(空)"] += 1

        # 種3の値(SRC の _skey で引く)
        s3v = None
        sp = ROOT / "data" / "manga" / f"{stem}.yml"
        if sp.exists():
            m = skey_re.search(sp.read_text(encoding="utf-8", errors="ignore")[:4000])
            if m:
                s3v = s3.get(m.group(1).strip().strip("'\""))
        if s3v == "other":
            s3v = None

        # 根拠
        imps = sorted({x for x in (norm_label(e.get("imprint")) for e in (d.get("editions") or [])
                                   if isinstance(e, dict)) if x})
        lab_vals = {labels[x] for x in imps if x in labels}
        ev = {}
        if len(lab_vals) == 1:
            ev["レーベル"] = next(iter(lab_vals))
        elif len(lab_vals) > 1:
            ev["レーベル"] = "割れ"
        mag = d.get("magazine")
        if isinstance(mag, str) and mags.get(mag) and mags[mag] != "other":
            ev["連載誌"] = mags[mag]
        if not imps and pubs.get(d.get("publisher") or ""):
            ev["出版社"] = pubs[d["publisher"]]
        vals = set(ev.values())
        if "割れ" in vals or len(vals) > 1:
            prop = "割れ"
        elif vals:
            prop = next(iter(vals))
        else:
            prop = "根拠なし"

        # 出どころ
        if slug in eov_demo or stem in eov_demo:
            origin = "overrides"
        elif stem in realign or slug in realign:
            origin = "realign"
        elif not cur:
            origin = "-"
        elif s3v and s3v == cur:
            origin = "種3(AI一括)"
        elif ev.get("レーベル") == cur or ev.get("出版社") == cur:
            origin = "対応表"
        else:
            origin = "不明"
        origins[origin] += 1

        if not cur:
            kind = "empty"
        elif origin in ("overrides", "realign"):
            kind = None
        elif prop not in ("割れ", "根拠なし") and prop != cur:
            kind = "conflict"
        elif origin == "不明":
            kind = "unsourced"
        else:
            kind = None
        if not kind:
            continue
        kinds[kind] += 1
        rows.append([kind, stem, str(d.get("title") or ""), LABEL_JA.get(cur, cur), origin,
                     LABEL_JA.get(prop, prop),
                     " / ".join(f"{k}={LABEL_JA.get(v, v)}" for k, v in ev.items()),
                     ",".join(imps)[:80], str(mag or ""), str(d.get("publisher") or ""),
                     ",".join(d.get("genres") or [])])

    order = {"conflict": 0, "unsourced": 1, "empty": 2}
    rows.sort(key=lambda r: (order[r[0]], r[5] in ("割れ", "根拠なし"), r[1]))
    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_TSV.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(["種類", "stem", "題", "今の値", "出どころ", "案", "根拠", "レーベル",
                           "連載誌", "出版社", "ジャンル"]) + "\n")
        for r in rows:
            f.write("\t".join(x.replace("\t", " ") for x in r) + "\n")
    prop_c = Counter((r[0], r[5]) for r in rows)
    summ = {"pages": len(files), "current": dict(cur_c), "origin": dict(origins),
            "worklist": dict(kinds),
            "worklist_by_proposal": {f"{k}:{p}": n for (k, p), n in sorted(prop_c.items())}}
    OUT_SUM.write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False, indent=1))
    print(f"→ {OUT_TSV.relative_to(ROOT)} ({len(rows)} 行)")


if __name__ == "__main__":
    main()
