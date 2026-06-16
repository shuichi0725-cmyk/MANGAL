#!/usr/bin/env python3
"""
Phase② 較正 = held-out v2 再分類(信頼度付き)から、ラベル別・信頼度別の適合率を測り、
**適用閾値(どの信頼度以上なら付与してよいか)**を決める。

pred 形式(heldout-v2-out/batch-*.json):
  [{"id","genres":[{"key","conf"}],"tags":[{"key","conf"}]}]
  conf ∈ {"high","medium","low"}

出力: .cache/genre-rakuten/phase2-calibration.json + 画面表
方針: genre は P≥0.80、 tag は P≥0.70 を満たす最も緩い信頼度を採用レベルとする。
      満たさないものは Phase④(2パス救済)送り。
"""
import json, sys
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "genre-rakuten"
PRED = OUT / "heldout-v2-out"

import yaml
MASTER = list(yaml.safe_load((ROOT / "data" / "genres.yml").read_text(encoding="utf-8")).items())
GNAME = {k: v["name"] for k, v in MASTER}
UNLEARN = {"gag", "romcom", "samurai", "4-koma"}
GLEARN = set(k for k, _ in MASTER if k not in UNLEARN)
tv = json.loads((OUT / "tag-vocab.json").read_text(encoding="utf-8"))
TJA = {t["key"]: t["ja"] for t in tv}
TVOCAB = set(t["key"] for t in tv)

LV = {"high": 3, "medium": 2, "low": 1}


def load_preds():
    pg = {}; pt = {}
    for fp in sorted(PRED.glob("batch-*.json")):
        try:
            arr = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ! {fp.name}: {e}", flush=True); continue
        for r in arr:
            gid = r.get("id")
            if gid is None:
                continue
            pg[gid] = {x["key"]: LV.get(x.get("conf"), 1) for x in (r.get("genres") or []) if isinstance(x, dict) and x.get("key")}
            pt[gid] = {x["key"]: LV.get(x.get("conf"), 1) for x in (r.get("tags") or []) if isinstance(x, dict) and x.get("key")}
    return pg, pt


def calibrate(truth, preds, vocab, name_map, p_target, label):
    eval_slugs = [s for s in truth if truth[s] and s in preds]
    rows = []
    for g in sorted(vocab):
        sup = sum(1 for s in eval_slugs if g in truth[s])
        if sup == 0:
            continue
        cell = {}
        for lv_name, lv in (("high", 3), ("medium", 2), ("low", 1)):
            pred_pos = [s for s in eval_slugs if preds[s].get(g, 0) >= lv]
            tp = sum(1 for s in pred_pos if g in truth[s])
            n = len(pred_pos)
            cell[lv_name] = (round(tp / n, 3) if n else 0.0, n, tp)
        # 採用レベル = P≥target を満たす最も緩い(low>med>high)。 recall優先で緩い順に試す。
        apply_lv = None
        for lv_name in ("low", "medium", "high"):
            p, n, tp = cell[lv_name]
            if n >= 5 and p >= p_target:
                apply_lv = lv_name
                break
        rows.append({"key": g, "ja": name_map.get(g, g), "support": sup,
                     "P_high": cell["high"], "P_med": cell["medium"], "P_all": cell["low"],
                     "apply_level": apply_lv})
    rows.sort(key=lambda r: -r["support"])
    print(f"\n===== {label} 較正(評価母数={len(eval_slugs)}, P目標≥{p_target})=====", flush=True)
    print("| key | 名称 | sup | P@high(n) | P@≥med(n) | P@all(n) | 採用 |", flush=True)
    print("|---|---|--:|--:|--:|--:|--|", flush=True)
    for r in rows:
        ph, nh, _ = r["P_high"]; pm, nm, _ = r["P_med"]; pa, na, _ = r["P_all"]
        print(f"| {r['key']} | {r['ja']} | {r['support']} | {ph:.2f}({nh}) | {pm:.2f}({nm}) | {pa:.2f}({na}) | {r['apply_level'] or '—'} |", flush=True)
    applied = [r for r in rows if r["apply_level"]]
    print(f"  → 採用 {len(applied)}/{len(rows)} {label}: " +
          ", ".join(f"{r['key']}({r['apply_level'][0]})" for r in applied), flush=True)
    return rows


def main():
    pg, pt = load_preds()
    print(f"preds: genre {len(pg):,} / tag {len(pt):,}", flush=True)

    gtruth = {}
    for l in (OUT / "heldout-truth.jsonl").open(encoding="utf-8"):
        r = json.loads(l); gtruth[r["slug"]] = set(x for x in r["label"] if x in GLEARN)
    ttruth = {}
    for l in (OUT / "heldout-tag-truth.jsonl").open(encoding="utf-8"):
        r = json.loads(l); ttruth[r["slug"]] = set(x for x in r["tags"] if x in TVOCAB)

    grows = calibrate(gtruth, pg, GLEARN, GNAME, 0.80, "ジャンル")
    trows = calibrate(ttruth, pt, TVOCAB, TJA, 0.70, "タグ")

    (OUT / "phase2-calibration.json").write_text(json.dumps(
        {"genre": grows, "tag": trows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ncalibration → {OUT/'phase2-calibration.json'}", flush=True)


if __name__ == "__main__":
    main()
