#!/usr/bin/env python3
"""
genre×楽天あらすじ step1 = 学習準備 (= [[genre_from_rakuten_story_plan]])

1. 教師コーパス(corpus.jsonl の trusted)を train / held-out に分割(決定的・seed固定)。
2. train から **ジャンル別 distinctive keyword**(log-odds)を採掘 → 「学習の中身」を可読化(台帳用)。
3. held-out を workflow 用の batch ファイルに分割(LLMが Read して分類)。
4. LLM 分類用の rubric(32→学習可能28キー + 日本語名 + データ由来キーワード)を出力。

held-out 件数 = 引数 or 既定3000。 master32 のうち教師ゼロの 4キー
(gag/romcom/samurai/4-koma)は学習・検証から除外(= 学習可能28キー)。
"""
import json, sys, re, math, random
from pathlib import Path
from collections import Counter, defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "genre-rakuten"
CORPUS = OUT / "corpus.jsonl"
BATCH_DIR = OUT / "heldout-batches"
BATCH_DIR.mkdir(parents=True, exist_ok=True)

import yaml
MASTER = list(yaml.safe_load((ROOT / "data" / "genres.yml").read_text(encoding="utf-8")).items())
MASTER_NAME = {k: v["name"] for k, v in MASTER}
# 教師ゼロ = この源では学習不可(step0判明)
UNLEARNABLE = {"gag", "romcom", "samurai", "4-koma"}
LEARNABLE = [k for k, _ in MASTER if k not in UNLEARNABLE]

HELDOUT_N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
BATCH = 40
SEED = 20260616

STOP = set("物語 作品 描く 連載 コミック シリーズ 単行本 収録 登場 主人公 世界 少年 少女 "
           "彼女 彼ら 自分 一人 二人 始まる 始まり 最強 最高 最新 最終 大人気 待望 ついに "
           "そして しかし だった ている である という ことが ような 描いた 贈る 第巻 雑誌 "
           "電子 限定 特典 試し読み 無料 配信 描き下ろし 巻末 収載".split())


def terms(cap):
    """可読 candidate term: カタカナ連(2-6) + 漢字連の 2/3-gram。"""
    out = set()
    for m in re.findall(r"[゠-ヿーー]{2,6}", cap):
        out.add(m)
    for run in re.findall(r"[一-鿿]{2,}", cap):
        for n in (2, 3):
            for i in range(len(run) - n + 1):
                t = run[i:i+n]
                if t not in STOP:
                    out.add(t)
    return out


def main():
    rows = []
    for line in CORPUS.open(encoding="utf-8"):
        r = json.loads(line)
        if not r.get("trusted"):
            continue
        lab = [g for g in r["label"] if g in LEARNABLE]
        if not lab:
            continue
        rows.append({"slug": r["slug"], "title": r["title"],
                     "caption": r["caption"], "label": sorted(lab)})
    print(f"教師(学習可能ラベル有): {len(rows):,} works", flush=True)

    rnd = random.Random(SEED)
    rnd.shuffle(rows)
    held = rows[:HELDOUT_N]
    train = rows[HELDOUT_N:]
    print(f"  held-out: {len(held):,} / train: {len(train):,}", flush=True)

    # held-out truth
    with (OUT / "heldout-truth.jsonl").open("w", encoding="utf-8") as f:
        for r in held:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # batches (id=slug, caption truncated 400)
    for p in BATCH_DIR.glob("*.json"):
        p.unlink()
    nb = 0
    for i in range(0, len(held), BATCH):
        chunk = held[i:i+BATCH]
        items = [{"id": r["slug"], "caption": r["caption"][:400]} for r in chunk]
        (BATCH_DIR / f"batch-{nb:03d}.json").write_text(
            json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        nb += 1
    print(f"  batches: {nb} ファイル ({BATCH}/batch) → {BATCH_DIR}", flush=True)

    # ===== distinctive keyword 採掘 (train のみ。 log-odds) =====
    df = Counter()                       # term → train内 doc頻度
    gdf = defaultdict(Counter)           # genre → term → doc頻度
    gcount = Counter()                   # genre → works
    N = len(train)
    for r in train:
        tset = terms(r["caption"])
        for t in tset:
            df[t] += 1
        for g in r["label"]:
            gcount[g] += 1
            for t in tset:
                gdf[g][t] += 1
    df = {t: c for t, c in df.items() if c >= 8}   # ノイズ除去

    cues = {}
    for g in LEARNABLE:
        ng = gcount.get(g, 0)
        if ng == 0:
            cues[g] = []
            continue
        scored = []
        for t, c_in in gdf[g].items():
            if t not in df or c_in < 4:
                continue
            c_all = df[t]
            # log-odds(genre vs background)
            p_in = (c_in + 0.5) / (ng + 1)
            p_out = (c_all - c_in + 0.5) / (N - ng + 1)
            lo = math.log(p_in / p_out)
            if lo > 0:
                scored.append((lo, c_in, t))
        scored.sort(reverse=True)
        cues[g] = [{"term": t, "lo": round(lo, 2), "n": c_in} for lo, c_in, t in scored[:15]]
    (OUT / "genre-cues.json").write_text(json.dumps(cues, ensure_ascii=False, indent=2), encoding="utf-8")

    # rubric.md (LLM へ渡す + 台帳)
    lines = ["# ジャンル判定 rubric (学習可能28キー)\n",
             "各キー = `key`(日本語名): train採掘の特徴語(log-odds上位)\n"]
    for g in LEARNABLE:
        top = " / ".join(c["term"] for c in cues[g][:8]) or "(特徴語薄い=判定はキャプション内容で)"
        lines.append(f"- `{g}` ({MASTER_NAME[g]}): {top}")
    (OUT / "rubric.md").write_text("\n".join(lines), encoding="utf-8")

    print("\n-- ジャンル別 train特徴語 (上位6) --", flush=True)
    for g in LEARNABLE:
        top = " ".join(c["term"] for c in cues[g][:6])
        print(f"  {g:14s} {top}", flush=True)
    print(f"\nrubric → {OUT/'rubric.md'}  cues → {OUT/'genre-cues.json'}", flush=True)
    print(f"truth → {OUT/'heldout-truth.jsonl'}  batches → {BATCH_DIR} ({nb})", flush=True)


if __name__ == "__main__":
    main()
