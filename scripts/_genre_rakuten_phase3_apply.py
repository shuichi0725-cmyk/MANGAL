#!/usr/bin/env python3
"""
Phase③ 適用 = target-out 予測 × Phase②較正方針 → seed 生成(純粋追加)。

入力:
  .cache/genre-rakuten/target-out/batch-*.json  (= [{id, genres:[{key,conf}], tags:[{key,conf}]}])
  .cache/genre-rakuten/phase2-calibration.json   (= ラベル別 採用信頼度レベル)
  .cache/genre-rakuten/target-meta.json          (= slug→{needs_genre, needs_tag})

出力(seed = slug単位の純粋追加):
  data/seeds/genre-rakuten.yml   (= provisional work へ振るジャンル)
  data/seeds/tag-rakuten.yml     (= theme tag未保有 work へ足す要素タグ)
  .cache/genre-rakuten/gray-candidates.jsonl  (= 閾値未達/非採用の高conf候補 = Phase④送り)
"""
import json, sys
from pathlib import Path
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "genre-rakuten"
PRED = OUT / "target-out"

import yaml
MASTER = list(yaml.safe_load((ROOT / "data" / "genres.yml").read_text(encoding="utf-8")).items())
GLEARN = set(k for k, _ in MASTER) - {"gag", "romcom", "samurai", "4-koma"}
TVOCAB = set(t["key"] for t in json.loads((OUT / "tag-vocab.json").read_text(encoding="utf-8")))
LV = {"high": 3, "medium": 2, "low": 1}


def main():
    calib = json.loads((OUT / "phase2-calibration.json").read_text(encoding="utf-8"))
    g_level = {r["key"]: LV[r["apply_level"]] for r in calib["genre"] if r.get("apply_level")}
    t_level = {r["key"]: LV[r["apply_level"]] for r in calib["tag"] if r.get("apply_level")}
    print(f"採用ジャンル {len(g_level)} / 採用タグ {len(t_level)}", flush=True)

    meta = json.loads((OUT / "target-meta.json").read_text(encoding="utf-8"))

    files = sorted(PRED.glob("batch-*.json"))
    print(f"target-out batch: {len(files)}", flush=True)
    g_seed = []; t_seed = []
    gray = []
    gc = Counter(); tc = Counter()
    seen = set()
    for fp in files:
        try:
            arr = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ! {fp.name}: {e}", flush=True); continue
        for r in arr:
            slug = r.get("id")
            if slug is None or slug in seen:
                continue
            seen.add(slug)
            m = meta.get(slug) or {}
            preds_g = [(x["key"], LV.get(x.get("conf"), 1)) for x in (r.get("genres") or [])
                       if isinstance(x, dict) and x.get("key") in GLEARN]
            preds_t = [(x["key"], LV.get(x.get("conf"), 1)) for x in (r.get("tags") or [])
                       if isinstance(x, dict) and x.get("key") in TVOCAB]

            # --- ジャンル適用(needs_genre のみ)---
            applied_g = set()
            if m.get("needs_genre"):
                for k, lv in preds_g:
                    if k in g_level and lv >= g_level[k]:
                        applied_g.add(k)
                if applied_g & {"baseball", "soccer"}:
                    applied_g.add("sports")
                if applied_g:
                    g_seed.append({"slug": slug, "genres": sorted(applied_g)})
                    for k in applied_g:
                        gc[k] += 1

            # --- タグ適用(needs_tag のみ)---
            applied_t = set()
            if m.get("needs_tag"):
                for k, lv in preds_t:
                    if k in t_level and lv >= t_level[k]:
                        applied_t.add(k)
                if applied_t:
                    t_seed.append({"slug": slug, "tags": sorted(applied_t)})
                    for k in applied_t:
                        tc[k] += 1

            # --- gray(Phase④送り)= 高conf(>=2)だが未適用 ---
            gg = [{"key": k, "conf": lv} for k, lv in preds_g
                  if lv >= 2 and k not in applied_g]
            gt = [{"key": k, "conf": lv} for k, lv in preds_t
                  if lv >= 2 and k not in applied_t]
            if gg or gt:
                gray.append({"slug": slug, "needs_genre": bool(m.get("needs_genre")),
                             "needs_tag": bool(m.get("needs_tag")),
                             "genres_gray": gg, "tags_gray": gt})

    # seed 書出
    hdr_g = ("# 楽天あらすじ由来ジャンル(Phase③・純粋追加。 provisional work=trusted空 のみ promote が採用)\n"
             "# 較正: Phase② 信頼度閾値で適合率≥0.80 を満たす採用ジャンルのみ。 [[genre_from_rakuten_story_plan]]\n")
    (ROOT / "data" / "seeds" / "genre-rakuten.yml").write_text(
        hdr_g + yaml.dump({"additions": g_seed}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    hdr_t = ("# 楽天あらすじ由来 要素タグ(Phase③・純粋追加。 theme tag未保有 work に追加)\n"
             "# 較正: Phase② 信頼度閾値で適合率≥0.70 を満たす採用タグのみ。 表示=tag-i18n 和訳。\n")
    (ROOT / "data" / "seeds" / "tag-rakuten.yml").write_text(
        hdr_t + yaml.dump({"additions": t_seed}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with (OUT / "gray-candidates.jsonl").open("w", encoding="utf-8") as f:
        for g in gray:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")

    print(f"\n=== Phase③ 適用結果 ===", flush=True)
    print(f"ジャンル付与 work: {len(g_seed):,} → data/seeds/genre-rakuten.yml", flush=True)
    print(f"  ジャンル別: " + ", ".join(f"{k}:{c}" for k, c in gc.most_common()), flush=True)
    print(f"タグ付与 work: {len(t_seed):,} → data/seeds/tag-rakuten.yml", flush=True)
    print(f"  タグ別(上位20): " + ", ".join(f"{k}:{c}" for k, c in tc.most_common(20)), flush=True)
    print(f"gray候補(Phase④送り): {len(gray):,} work → gray-candidates.jsonl", flush=True)


if __name__ == "__main__":
    main()
